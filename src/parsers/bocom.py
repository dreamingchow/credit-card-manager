"""交通银行账单解析器。

格式: "本期应还款 ￥7128.11"
      "最低应还款 ￥356.41"
      "到期还款日 Payment Due Date 2026-06-01"
"""

import re
from .base import BillParser


class BOCOMParser(BillParser):
    """交通银行 (Bank of Communications)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还款 ￥XXX
        m = re.search(r'本期应还款\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val and self._safe_amount(val):
                result['total_amount'] = val

        # 2. 最低应还款 ￥XXX
        m = re.search(r'最低应还款\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val and self._safe_amount(val):
                result['min_payment'] = val

        # 3. 到期还款日 (交行格式: "2026-06-01")
        m = re.search(r'到期还款日\s+Payment Due Date\s+(\d{4}-\d{2}-\d{2})', text)
        if m:
            result['due_date_full'] = m.group(1)
            result['due_day'] = int(m.group(1).split('-')[2])

        if 'due_date_full' not in result:
            due_full, due_day = self._extract_due_date(text)
            result['due_date_full'] = due_full
            result['due_day'] = due_day

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
