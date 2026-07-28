"""中国工商银行账单解析器。

ICBC 合并账单格式:
  - 还款日: "贷记卡到期还款日 2026年8月5日"
  - 交易汇总表: 卡号后四位 | 上期余额 | 本期收入 | 本期支出 | 本期余额
  - 交易明细表: 主卡明细（可能含汇总表中未出现的卡）
  - 工银i豆表: 列出所有卡号

一张账单一个还款日，多卡共享。
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
        """提取工行合并账单中所有卡片的还款信息。"""
        # 1. 提取还款日
        due_full, due_day = self._extract_due_date(text)

        # 2. 从 HTML 表格提取卡片数据
        cards_balance = {}  # last4 -> balance
        cards_seen = set()

        if soup:
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if not rows:
                    continue
                header_text = rows[0].get_text(strip=True)

                # 交易汇总表: "卡号后四位 上期余额 本期收入 本期支出 本期余额"
                if '本期余额' in header_text and '上期余额' in header_text:
                    for row in rows[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cells) >= 5 and cells[0].isdigit() and len(cells[0]) == 4:
                            last4 = cells[0]
                            balance = self._parse_amount(cells[4])
                            if balance is not None:
                                cards_balance[last4] = balance
                                cards_seen.add(last4)

                # 交易明细表: "主卡明细" — 记录出现的卡号
                elif '主卡明细' in header_text or '交易类型' in header_text:
                    for row in rows[1:]:
                        cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                        if len(cells) >= 2 and cells[0].isdigit() and len(cells[0]) == 4:
                            cards_seen.add(cells[0])

                # 工银i豆表: 含卡号引用
                elif '工银i豆' in header_text or '联名卡' in header_text:
                    table_text = table.get_text()
                    for m in re.finditer(r'联名卡-(\d{4})', table_text):
                        cards_seen.add(m.group(1))

        # 3. 纯文本兜底（如果 soup 解析失败）
        if not cards_seen:
            text_cards = self._extract_from_text(text)
            cards_balance.update(text_cards)
            cards_seen.update(text_cards.keys())

        # 4. 组装结果: 汇总表中的卡用实际余额，其他卡余额为 0
        results = []
        for last4 in sorted(cards_seen):
            amount = cards_balance.get(last4, 0.0)
            results.append({
                'card_last4': last4,
                'total_amount': amount,
                'min_payment': 0.0 if amount == 0 else amount,
                'due_date_full': due_full,
                'due_day': due_day,
            })

        return results

    @staticmethod
    def _extract_due_date(text: str):
        """提取 ICBC 贷记卡到期还款日。"""
        m = re.search(r'贷记卡到期还款日\s*(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", int(d)
        return None, None

    def _extract_from_text(self, text: str) -> dict:
        """从纯文本提取卡片数据（兜底）。"""
        cards = {}
        pattern = re.compile(
            r'(\d{4})\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)\s+(-?[\d,]+\.?\d*/RMB)'
        )
        for m in pattern.finditer(text):
            last4 = m.group(1)
            balance = self._parse_amount(m.group(5))
            if balance is not None:
                cards[last4] = balance
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
