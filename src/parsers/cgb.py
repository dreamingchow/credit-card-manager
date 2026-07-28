"""广发银行账单解析器。

支持格式: 表格列名 + 多数据行
"本期账单金额 最低还款额 最后还款日 入账货币 存款 卡片消费额度
 0556       21.00      21.00       人民币     0.00    53,000.00
 3637       9.99       9.99        人民币     0.00    53,000.00"

同一封邮件可包含多张卡。
"""

import re
from .base import BillParser


class CGBParser(BillParser):
    """广发银行 (China Guangfa Bank)。支持多卡同账单。"""

    # 匹配行: "卡号 金额 最低还款 YYYY/MM/DD ..."
    _CARD_LINE_RE = re.compile(
        r'(\d{4})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})\s+(\d{4})/(\d{1,2})/(\d{1,2})'
    )

    # 表头后的连续数据行（同段落）
    _TABLE_RE = re.compile(
        r'本期账单金额\s+最低还款额\s+最后还款日\s+入账货币\s+存款\s+卡片消费额度'
        r'\s+((?:\d{4}\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}\s+[\d/]+\s+\S+\s+[\d,]+\.?\d*\s+[\d,]+\.?\d*\s*)+)'
    )

    # 表头行（用于定位扫描起点）
    _HEADER_RE = re.compile(r'本期账单金额\s+最低还款额\s+最后还款日[^\n\r]*')

    def extract(self, text: str) -> dict:
        """向后兼容：返回第一个匹配到的卡片数据。"""
        results = self.extract_all(text)
        return results[0] if results else {}

    def extract_all(self, text: str) -> list:
        """提取广发银行账单中所有卡片的还款信息。"""

        # 预处理: 将"无欠款"替换为 0.00，使正则能匹配
        text = text.replace('无欠款', '0.00')

        # 策略1a: 表头后紧跟换行 + 数据行
        results = self._find_card_rows(text, newline=True)
        if results:
            return results

        # 策略1b: 表头与数据同行
        results = self._find_card_rows(text, newline=False)
        if results:
            return results

        # 策略1c: 通用模式 - 扫描全账单中所有 "卡号 金额 最低还款 日期" 行
        results = self._find_card_rows_generic(text)
        if results:
            return results

        # 策略2: "本期应还款总额： ￥XXX"（兜底单卡）
        m = re.search(r'本期应还款总额[：:]\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                due_full, due_day = self._extract_due_date(text)
                card_last4 = self._extract_card_last4(text)
                return [{
                    'total_amount': val,
                    'min_payment': val,
                    'due_date_full': due_full,
                    'due_day': due_day,
                    'card_last4': card_last4,
                }]

        return []

    def _find_card_rows(self, text, newline=True):
        """从表头附近扫描完整数据行。"""
        results = []
        for block in self._HEADER_RE.finditer(text):
            if newline:
                scan_start = block.end()
            else:
                scan_start = block.start()
            scan_end = min(scan_start + 800, len(text))
            scan_text = text[scan_start:scan_end]
            for m in self._CARD_LINE_RE.finditer(scan_text):
                row = self._make_row(m)
                if row:
                    results.append(row)
        return self._dedup(results)

    def _find_card_rows_generic(self, text):
        """通用模式：扫描全账单中所有数据行。"""
        results = []
        for m in self._CARD_LINE_RE.finditer(text):
            row = self._make_row(m)
            if row:
                results.append(row)
        return self._dedup(results)

    def _make_row(self, m):
        """从正则匹配构造结果 dict。"""
        last4_str = m.group(1)
        amount_val = self._safe_float(m.group(2))
        min_pay_val = self._safe_float(m.group(3))
        if amount_val is None:
            return None
        y, mo, d = m.group(4), m.group(5), m.group(6)
        due_full = f"{y}-{mo.zfill(2)}-{d.zfill(2)}"
        return {
            'total_amount': amount_val,
            'min_payment': min_pay_val if min_pay_val and min_pay_val > 0 else amount_val,
            'due_date_full': due_full,
            'due_day': int(d),
            'card_last4': last4_str,
        }

    @staticmethod
    def _dedup(results):
        """按 card_last4 去重。"""
        seen = set()
        unique = []
        for r in results:
            if r['card_last4'] not in seen:
                seen.add(r['card_last4'])
                unique.append(r)
        return unique

    @staticmethod
    def _extract_card_last4(text):
        """提取卡号末四位（掩码格式）。"""
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            return m.group(1)
        return None
