"""民生银行账单解析器。

格式: "本期应还款金额 New Balance 本期最低还款金额 Min.Payment
       人民币/美元账户 RMB/USD Account RMB 100.02 RMB 100.00"

也支持: "本期应还款金额 New Balance RMB 100.02"
"""

import re
from .base import BillParser


class CMBCParser(BillParser):
    """民生银行 (China Minsheng Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. "本期应还款金额 New Balance RMB XXXX.XX" (注意\xa0非断空格)
        m = re.search(r'本期应还款金额\s+New[\s\xa0]+Balance\s+RMB\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val and self._safe_amount(val):
                result['total_amount'] = val

        # 2. 表格格式: "本期应还款金额 New Balance 本期最低还款金额 Min.Payment\nRMB/USD Account RMB 100.02 RMB 100.00"
        if 'total_amount' not in result:
            m = re.search(
                r'本期应还款金额\s+New[\s\xa0]+Balance\s+本期最低还款金额\s+Min\.Payment\s+[^\n]*\s+RMB\s+([\d,]+\.?\d{2})',
                text
            )
            if m:
                val = self._safe_float(m.group(1))
                if val and self._safe_amount(val):
                    result['total_amount'] = val

        # 3. 最低还款金额
        m = re.search(r'本期最低还款金额\s+Min\.Payment\s+RMB\s+([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val and self._safe_amount(val):
                result['min_payment'] = val

        # 4. 到期还款日 (YYYY/MM/DD)
        m = re.search(r'本期最后还款日\s+Payment Due Date\s+(\d{4})/(\d{2})/(\d{2})', text)
        if m:
            result['due_date_full'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            result['due_day'] = int(m.group(3))

        # 5. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
