"""广发银行账单解析器。

支持格式: 表格列名 + 数据行
"本期账单金额 最低还款额 最后还款日 入账货币 存款 卡片消费额度
 7495       14.20       14.20        人民币      0.00    134,000.00"

也支持 "本期应还款总额： ￥237.10" 格式。
"""

import re
from .base import BillParser


class CGBParser(BillParser):
    """广发银行 (China Guangfa Bank)。"""

    def extract(self, text: str) -> dict:
        result = {}

        # 1. 表格格式: "本期账单金额 最低还款额 最后还款日 ... \n 卡号 金额 ..."
        # 列名行 + 数据行，数据行为 "卡号 金额 最低还款 货币 存款 额度"
        m = re.search(
            r'本期账单金额\s+最低还款额\s+最后还款日[^\n\r]*(?:\n|\s{2,})(\d+)\s+([\d,]+\.?\d{2})',
            text
        )
        if m:
            card_val = int(m.group(1))
            amount_val = self._safe_float(m.group(2))
            if amount_val is not None and 0.5 <= amount_val <= 100000 and card_val > 2099:
                result['total_amount'] = amount_val

        # 同段无换行: "本期账单金额 最低还款额 最后还款日 入账货币 存款 卡片消费额度 3637 1.39"
        if 'total_amount' not in result:
            m = re.search(
                r'本期账单金额\s+最低还款额\s+最后还款日\s+入账货币\s+存款\s+卡片消费额度\s+(\d+)\s+([\d,]+\.?\d{2})',
                text
            )
            if m:
                card_val = int(m.group(1))
                amount_val = self._safe_float(m.group(2))
                if amount_val is not None and 0.5 <= amount_val <= 100000 and card_val > 2099:
                    result['total_amount'] = amount_val

        # 2. "本期应还款总额： ￥XXX"
        if 'total_amount' not in result:
            m = re.search(r'本期应还款总额[：:]\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
            if m:
                val = self._safe_float(m.group(1))
                if val is not None:
                    result['total_amount'] = val

        # 3. 最低还款额
        m = re.search(r'最低还款额\s*[￥¥]?\s*([\d,]+\.?\d{2})', text)
        if m:
            val = self._safe_float(m.group(1))
            if val is not None:
                result['min_payment'] = val

        # 4. 到期日
        due_full, due_day = self._extract_due_date(text)
        result['due_date_full'] = due_full
        result['due_day'] = due_day

        # 5. 卡号末四位
        m = re.search(r'\*{4}(\d{4})', text)
        if m:
            result['card_last4'] = m.group(1)

        return result
