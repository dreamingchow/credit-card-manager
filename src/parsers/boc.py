"""中国银行账单解析器。

中行PDF有特殊格式（已有extract_from_pdf处理）:
"到期还款日 账单日 本期人民币欠款总计
 Payment Due Date Statement Closing Date Current RMB Total Balance Due
 2026-04-30 2026-04-10 3,508.93"

HTML账单用通用pattern: "本期应还款总额 CNY XXXX.XX"
"""

import re
from .base import BillParser


class BOCParser(BillParser):
    """中国银行 (Bank of China)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 本期应还款总额 CNY XXXX.XX
        m = re.search(r'本期应还款总额\s+CNY\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['total_amount'] = val

        # 2. 最低还款额
        result['min_payment'] = self._extract_min_payment(text)

        # 3. 到期日 (YYYY-MM-DD or YYYY/MM/DD)
        due_full, due_day = self._extract_due_date(text)
        result['due_date_full'] = due_full
        result['due_day'] = due_day

        # 3. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
