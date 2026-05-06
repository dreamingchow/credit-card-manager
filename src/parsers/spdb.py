"""浦发银行账单解析器。

格式: "本期应还款总额： ￥237.10"
      "到期还款日：   2026/05/09"
"""

import re
from .base import BillParser


class SPDBParser(BillParser):
    """浦发银行 (SPDB)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还款总额
        m = re.search(r'本期应还款总额[：:]\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = val

        # 2. 最低还款额
        m = re.search(r'本期最低还款额[：:]\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['min_payment'] = val

        # 3. 到期还款日
        due_full, due_day = self._extract_due_date(text)
        result['due_date_full'] = due_full
        result['due_day'] = due_day

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
