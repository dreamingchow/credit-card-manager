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
    def _extract_min_payment(text: str) -> Optional[float]:
        """提取最低还款额."""
        m = re.search(r'最低还款额\s*[￥¥]?\s*([\d,]+\.?\d{2})', text)
        if m:
            return BillParser._safe_float(m.group(1))
        return None
