"""招商银行账单解析器。

格式: "本期应还金额 New Balance ¥ 11,545.32"
      "最低还款额 Min. Payment ¥ 3,768.48"
      "最后还款日(Payment Due Date) 05月03日"
"""

import re
from .base import BillParser


class CMBParser(BillParser):
    """招商银行 (China Merchants Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还金额 New Balance ¥ XXX,XXX.XX
        m = re.search(r'本期应还金额\s+New\s+Balance\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = val

        # 2. 最低还款额
        m = re.search(r'最低还款额\s+Min\.?\s*Payment\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['min_payment'] = val

        # 3. 最后还款日 (MM月DD日格式)
        m = re.search(r'最后还款日\s*\(Payment Due Date\)\s*(\d{1,2})月(\d{1,2})日', text)
        if m:
            mo, d = int(m.group(1)), int(m.group(2))
            year_m = re.search(r'(\d{4})年', text[:500])
            year = year_m.group(1) if year_m else None
            if year:
                result['due_date_full'] = f"{year}-{mo:02d}-{d:02d}"
            result['due_day'] = d

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
