"""中信银行账单解析器。

格式: "本期应还款总额 CNY 11.98"
      "本期最低还款额 CNY 0.60"
      "到期还款日 2026年05月20日 Payment Due Date"
"""

import re
from .base import BillParser


class CITICParser(BillParser):
    """中信银行 (CITIC Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还款总额 CNY XXXX.XX (允许0元账单)
        m = re.search(r'本期应还款总额\s+CNY\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None and 0 <= val <= 100000:
                result['total_amount'] = val

        # 2. 最低还款额 (支持空格变化)
        m = re.search(r'本期最低还款额\s+CNY\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None and 0 <= val <= 50000:
                result['min_payment'] = val

        # 3. 到期还款日 (YYYY年MM月DD日)
        m = re.search(r'到期还款日\s+(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            result['due_date_full'] = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            result['due_day'] = int(m.group(3))

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
