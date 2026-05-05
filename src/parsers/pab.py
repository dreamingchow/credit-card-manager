"""平安银行账单解析器。

格式: "本期应还金额 ¥ -2,724.84" (负数=溢缴款)
      "本期最低应还金额 ¥ 0.00"
      到期日从卡片信息中获取
"""

import re
from .base import BillParser


class PABParser(BillParser):
    """平安银行 (Ping An Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还金额 ¥ -X,XXX.XX (可能负数=溢缴款)
        m = re.search(r'本期应还金额\s*[￥¥]\s*(-?[\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = abs(val) if val < 0 else val

        # 2. 最低应还金额
        m = re.search(r'本期最低应还金额\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val and self._safe_amount(val):
                result['min_payment'] = val

        # 3. 到期还款日 (通用提取)
        due_full, due_day = self._extract_due_date(text)
        result['due_date_full'] = due_full
        result['due_day'] = due_day

        # 4. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
