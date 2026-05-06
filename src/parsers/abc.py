"""中国农业银行账单解析器。

格式: "本期应还款额(欠款为-) New Balance 人民币(CNY) -23.90"
      "最低还款额(欠款为-) Min Payment 人民币(CNY) 0.00"
      "到期还款日 Payment Due Date 2026/04/01"
"""

import re
from .base import BillParser


class ABCParser(BillParser):
    """农业银行 (Agricultural Bank of China)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还款额 New Balance 人民币(CNY) XXXX.XX
        m = re.search(r'本期应还款额\s*\(欠款为-\)\s+New Balance\s+人民币\s*\(CNY\)\s+(-?[\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                # 农行负数是溢缴款，取绝对值
                result['total_amount'] = abs(val) if val < 0 else val

        # 2. 最低还款额
        m = re.search(r'最低还款额\s*\(欠款为-\)\s+Min Payment\s+人民币\s*\(CNY\)\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['min_payment'] = val

        # 3. 到期还款日 (YYYY/MM/DD)
        m = re.search(r'到期还款日\s+Payment Due Date\s+(\d{4})/(\d{2})/(\d{2})', text)
        if m:
            result['due_date_full'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            result['due_day'] = int(m.group(3))

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
