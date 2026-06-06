"""上海银行账单解析器。

格式: "本期余额 9.65+" (带+/-后缀)
      "到期还款日 Payment Due Date 2026年04月30日"
"""

import re
from .base import BillParser


class BOCOM_SHParser(BillParser):
    """上海银行 (Bank of Shanghai)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期余额 XXXX.XX+ (正数=欠款)
        m = re.search(r'本期余额\s+([\d,]+\.?\d{2})\+', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = val

        # 负数表示有存款
        m = re.search(r'本期余额\s+Total Balance\s+([\d,]+\.?\d{2})-', text)
        if m:
            result['total_amount'] = 0.0

        # 2. 最低还款额
        result['min_payment'] = self._extract_min_payment(text)

        # 3. 到期日 (YYYY年MM月DD日)
        due_full, due_day = self._extract_due_date(text)
        result['due_date_full'] = due_full
        result['due_day'] = due_day

        # 3. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
