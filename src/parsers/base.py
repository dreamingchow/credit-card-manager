"""账单解析器基类。每个银行继承此类实现独立的 extract() 方法。"""

import re
from abc import ABC, abstractmethod
from typing import Optional


class BillParser(ABC):
    """账单解析器基类。"""

    @abstractmethod
    def extract(self, text: str) -> dict:
        """从账单文本中提取数据。

        Returns:
            {
                'total_amount': float | None,
                'min_payment': float | None,
                'due_date_full': str | None,  # YYYY-MM-DD
                'due_day': int | None,        # day of month
                'card_last4': str | None,
            }
        """
        ...

    def extract_all(self, text: str, soup=None) -> list:
        """从一张可能包含多卡的账单中提取所有卡片数据。

        默认实现返回单卡结果（向后兼容）。
        多卡银行（如广发）应覆盖此方法返回 list[dict]，可返回空列表。
        """
        return [self.extract(text)]

    @staticmethod
    def _safe_float(val_str: str) -> Optional[float]:
        """安全转换金额为float。"""
        try:
            return float(val_str.replace(',', ''))
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _extract_due_date(text: str) -> tuple:
        """通用到期日提取，返回 (due_date_full, due_day)。"""
        # YYYY-MM-DD or YYYY/MM/DD
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", int(d)

        # YYYY年MM月DD日
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            y, mo, d = m.group(1), m.group(2), m.group(3)
            return f"{y}-{mo.zfill(2)}-{d.zfill(2)}", int(d)

        # MM月DD日（需从上下文找年份）
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{1,2})月(\d{1,2})日', text)
        if m:
            mo, d = int(m.group(1)), int(m.group(2))
            year_m = re.search(r'(\d{4})年', text[:500])
            year = year_m.group(1) if year_m else None
            if year:
                return f"{year}-{mo:02d}-{d:02d}", d

        return None, None

    @staticmethod
    def _extract_holder_name_from_text(text: str, card_last4: str) -> Optional[str]:
        """尝试从文本中提取持卡人姓名。"""
        # 匹配常见模式: 尊敬的 XXX 先生/女士
        m = re.search(r'尊敬的\s*(\S+?)\s*(?:先生|女士|小姐)', text)
        if m:
            return m.group(1)
        return None


class MultiCardParser(BillParser):
    """多卡账单解析器基类（一封邮件含多张卡）的标记类。

    子类应实现 extract_all() 返回多个 dict。
    """
    pass
