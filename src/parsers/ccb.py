"""中国建设银行账单解析器。

格式: "本期全部应还款额 New Balance 最低还款额 Min.Payment
       人民币 （CNY） 10.97 10.97"
"""

import re
from .base import BillParser


class CCBParser(BillParser):
    """建设银行 (China Construction Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期全部应还款额 New Balance (CNY后，支持括号格式)
        m = re.search(r'本期全部应还款额\s+New Balance\s+人民币\s*[（(]CNY[)）]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = val

        # 2. 最低还款额
        m = re.search(r'最低还款额\s+Min\.Payment\s+CNY\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['min_payment'] = val

        # 3. 到期还款日 (YYYY/MM/DD)
        m = re.search(r'本期到期还款日\s+Payment Due Date\s+(\d{4})/(\d{2})/(\d{2})', text)
        if m:
            result['due_date_full'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            result['due_day'] = int(m.group(3))

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
