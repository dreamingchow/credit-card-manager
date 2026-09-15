"""中国工商银行账单解析器。

ICBC 合并账单格式:
  - 还款日: "贷记卡到期还款日 2026年8月5日"
  - 需还款明细表: 卡号后四位 | 币种 | 应还款额 | 最低还款额 | 信用额度
    (仅当本期有应还金额时出现；卡号格式如 "9268(牡丹贷记卡)")
  - 交易汇总表: 卡号后四位 | 上期余额 | 本期收入 | 本期支出 | 本期余额
    (只列出有余额变动的卡；已还清或无交易的卡可能不出现)
  - 交易明细表: 主卡明细（列出所有有交易的卡）
  - 工银i豆表: 列出所有卡号 (联名卡-XXXX)

一张账单一个还款日，多卡共享。
金额优先级: 需还款明细.应还款额 > 交易汇总表.本期支出(当余额<=0时) > 0
"""

import re
from .base import MultiCardParser


class ICBCParser(MultiCardParser):
    """中国工商银行 (Industrial and Commercial Bank of China)。

    多卡合并账单，一张账单一个还款日。
    使用 HTML 表格结构提取（纯文本正则不够可靠）。
    """

    def extract(self, text: str, soup=None) -> dict:
        """向后兼容：返回第一个匹配到的卡片数据。"""
        results = self.extract_all(text, soup=soup)
        return results[0] if results else {}

    def extract_all(self, text: str, soup=None) -> list:
        """提取工行合并账单中所有卡片的还款信息。

        金额优先级:
          1. 需还款明细表.应还款额（最权威，银行直接给出的应还金额）
          2. 交易明细表.记账金额(支出)累加（兜底，汇总表卡号不可靠）
        卡号来源: 需还款明细 + 交易明细 + i豆表（三者取并集）
        """
        # 1. 提取还款日
        due_full, due_day = self._extract_due_date(text)

        # 2. 从 HTML 表格提取数据
        cards_seen = set()          # 所有出现过的卡号
        payment_detail = {}         # last4 -> (应还款额, 最低还款额)
        detail_expend = {}          # last4 -> 交易明细支出累加

        if soup:
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if not rows:
                    continue
                header_text = rows[0].get_text(strip=True)

                # 需还款明细表: "卡号后四位 币种 应还款额 最低还款额 信用额度"
                if '应还款额' in header_text:
                    for row in rows[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cells) >= 4:
                            m = re.match(r'(\d{4})', cells[0])
                            if m:
                                last4 = m.group(1)
                                amount = self._parse_amount(cells[2])
                                min_pay = self._parse_amount(cells[3])
                                if amount is not None:
                                    payment_detail[last4] = (amount, min_pay or 0.0)
                                cards_seen.add(last4)

                # 交易明细表: "主卡明细" — 累加记账金额(支出)，记录卡号
                elif '主卡明细' in header_text or '交易类型' in header_text:
                    for row in rows[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cells) >= 2:
                            m = re.match(r'(\d{4})', cells[0])
                            if not m:
                                continue
                            last4 = m.group(1)
                            cards_seen.add(last4)
                            # 累加记账金额（最后一列，格式如 "6.08/RMB(支出)"）
                            if len(cells) >= 7:
                                booked = self._parse_amount(cells[6])
                                if booked is not None and booked > 0:
                                    detail_expend[last4] = detail_expend.get(last4, 0.0) + booked

                # 工银i豆表: 含卡号引用
                elif '工银i豆' in header_text or '联名卡' in header_text:
                    table_text = table.get_text()
                    for m in re.finditer(r'联名卡-(\d{4})', table_text):
                        cards_seen.add(m.group(1))

        # 3. 纯文本兜底（如果 soup 解析失败）
        if not cards_seen:
            text_cards = self._extract_from_text(text)
            detail_expend.update(text_cards)
            cards_seen.update(text_cards.keys())

        # 4. 组装结果
        results = []
        for last4 in sorted(cards_seen):
            # 金额优先级: 需还款明细 > 交易明细支出累加 > 0
            if last4 in payment_detail:
                amount, min_pay = payment_detail[last4]
            elif last4 in detail_expend:
                amount = round(detail_expend[last4], 2)
                min_pay = round(amount * 0.1, 2) if amount > 0 else 0.0
            else:
                amount = 0.0
                min_pay = 0.0

            results.append({
                'card_last4': last4,
                'total_amount': amount,
                'min_payment': min_pay,
                'due_date_full': due_full,
                'due_day': due_day,
            })

        return results

    @staticmethod
    def _extract_due_date(text: str):
        """提取 ICBC 贷记卡到期还款日。

        HTML 中格式: <td>贷记卡到期还款日</td></tr></table></td><td>2026年10月5日</td>
        标签和日期之间可能有 </tr></table></td><td> 等 HTML 结构，
        所以用宽松的匹配（标签和日期之间允许任意字符）。
        """
        # 先尝试严格匹配（纯文本）
        m = re.search(r'贷记卡到期还款日\s*(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", int(d)
        # 宽松匹配（HTML 结构中间隔了标签）
        m = re.search(r'贷记卡到期还款日.{0,100}?(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", int(d)
        return None, None

    def _extract_from_text(self, text: str) -> dict:
        """从纯文本提取卡片数据（兜底）。返回 last4 -> 本期支出。"""
        cards = {}
        pattern = re.compile(
            r'(\d{4})\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)'
        )
        for m in pattern.finditer(text):
            last4 = m.group(1)
            # 第4列是本期支出
            expend = self._parse_amount(m.group(4))
            if expend is not None:
                cards[last4] = expend
        return cards

    @staticmethod
    def _parse_amount(val_str: str):
        """解析金额字符串（带 /RMB 后缀），负数或零返回 0.0。"""
        try:
            val = float(val_str.replace('/RMB', '').replace(',', ''))
            if val <= 0:
                return 0.0
            return val
        except (ValueError, AttributeError):
            return None
