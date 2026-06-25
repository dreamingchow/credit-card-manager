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

        # 优先使用支付表格格式：48959203****5200  人民币(CNY)  20.96  20.96
        # 这个表格同时包含卡号和金额，更准确
        # 1-3. 从支付表格提取卡号、金额、最低还款额
        m = re.search(r'\*{4}(\d{4}).*?CNY.{0,100}?([\d,]+\.?\d{2}).{0,100}?([\d,]+\.?\d{2})', text, re.DOTALL)
        if m:
            result['card_last4'] = m.group(1)
            val = self._safe_float(m.group(2))
            if val is not None:
                result['total_amount'] = val
            min_val = self._safe_float(m.group(3))
            if min_val is not None:
                result['min_payment'] = min_val

        # 如果支付表格没匹配到，尝试上期+本期表格 (老账单格式)
        if not result.get('total_amount'):
            # 格式: New Balance 人民币(CNY) 10.97 0.00 10.97 0.00 美元
            # 第一个金额就是应还款额
            m = re.search(r'CNY.{0,100}?(\d+\.\d{2}).*?美元', text, re.DOTALL)
            if m:
                val = self._safe_float(m.group(1))
                if val is not None:
                    result['total_amount'] = val

        # 4. 到期还款日 (YYYY/MM/DD) - 中英文间可能无空格
        m = re.search(r'到期还款日\s*Payment Due Date\s*(\d{4})/(\d{2})/(\d{2})', text)
        if m:
            result['due_date_full'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            result['due_day'] = int(m.group(3))

        # 5. 卡号兜底方案
        if not result.get('card_last4'):
            m = re.search(r'\*{4}(\d{4})', text)
            if m:
                result['card_last4'] = m.group(1)

        return result
