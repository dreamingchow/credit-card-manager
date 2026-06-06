"""光大银行账单解析器。

格式: 表格列名 + 数据行
"到期还款日 Payment Due Date 信用额度 Credit Limit
 人民币本期账单金额 RMB Statement Balance 人民币本期最低还款额 RMB Minimum Payment Due
 2026/04/18 2026/05/07 ￥82,800.00 ￥3,903.59 ￥3,615.18"

数据行: 到期日 还款日 额度 账单金额 最低还款额
所以账单金额是倒数第二个，最低还款额是最后一个。
"""

import re
from .base import BillParser


class CEBParser(BillParser):
    """光大银行 (China Everbright Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. "人民币本期账单金额 RMB Statement Balance ... \n 到期日 还款日 额度 账单金额 最低还款额"
        # 数据行: 2026/04/18 2026/05/07 ￥82,800.00 ￥3,903.59 ￥3,615.18
        # 对应: 到期日 还款日 额度 账单金额 最低还款额
        m = re.search(
            r'人民币本期账单金额\s+RMB Statement Balance\s+人民币本期最低还款额\s+RMB Minimum Payment Due\s*\n?\s*(?:\S+\s+){2,3}[￥¥]\s*[\d,]+\.[\d]+\s*[￥¥]?\s*([\d,]+\.?\d{2})\s+[￥¥]?\s*([\d,]+\.?\d{2})',
            text
        )
        if m:
            # group(1) = 账单金额, group(2) = 最低还款额
            val = self._safe_float(m.group(1))
            if val is not None and 0 <= val <= 50000:
                result['total_amount'] = val
            # group(2) = 最低还款额
            min_val = self._safe_float(m.group(2))
            if min_val is not None and 0 <= min_val:
                result['min_payment'] = min_val

        # 4. 到期还款日
        # 从表格中提取两个日期，第一个是账单日，第二个是还款日
        # 格式: 账单日期<br/>Statement Date</td>...<br/>Payment Due Date</td>...<td>2026/05/18</td><td>2026/06/06</td>
        m = re.search(r'账单日期.*?Statement Date.*?Payment Due Date.*?(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})', text, re.S)
        if m:
            # 取第二个日期作为到期还款日
            date_str = m.group(2)
            result['due_date_full'] = date_str.replace('/', '-')
            result['due_day'] = int(date_str.split('/')[2])
        else:
            # 备选：查找第一个日期对（账单日+还款日）
            m2 = re.search(r'(\d{4}/\d{2}/\d{2})\s+(\d{4}/\d{2}/\d{2})', text)
            if m2:
                date_str = m2.group(2)
                result['due_date_full'] = date_str.replace('/', '-')
                result['due_day'] = int(date_str.split('/')[2])

        # 5. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        # 6. 检测年费（特殊提醒）
        fee_patterns = [
            r'息费\s*年费\s*[￥¥]?\s*([,\d]+\.?\d{2})',
            r'年费\s*[￥¥]?\s*([,\d]+\.?\d{2})',
            r'年费\s+([￥¥]\s*[\d,]+\.?\d{2})',
        ]
        for pat in fee_patterns:
            m = re.search(pat, text)
            if m:
                fee_val = self._safe_float(m.group(1).replace('￥', '').replace('¥', '').strip())
                if fee_val is not None and fee_val > 0:
                    result['annual_fee'] = fee_val
                break

        return result
