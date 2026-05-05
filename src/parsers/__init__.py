"""账单解析器注册表。

每个银行对应一个 parser 类，通过 bank_name 路由。
"""

from .cgb import CGBParser        # 广发银行
from .spdb import SPDBParser      # 浦发银行
from .bocom import BOCOMParser    # 交通银行
from .psbc import PSBCParser      # 邮储银行
from .cmb import CMBParser        # 招商银行
from .ccb import CCBParser        # 建设银行
from .ceb import CEBParser        # 光大银行
from .boc import BOCParser        # 中国银行
from .citic import CITICParser    # 中信银行
from .abc import ABCParser        # 农业银行
from .pab import PABParser        # 平安银行
from .cmbc import CMBCParser      # 民生银行
from .bos import BOCOM_SHParser   # 上海银行

# 银行名 -> 解析器类映射
PARSER_MAP = {
    '广发银行': CGBParser,
    '浦发银行': SPDBParser,
    '交通银行': BOCOMParser,
    '邮储银行': PSBCParser,
    '招商银行': CMBParser,
    '建设银行': CCBParser,
    '光大银行': CEBParser,
    '中国银行': BOCParser,
    '中信银行': CITICParser,
    '农业银行': ABCParser,
    '平安银行': PABParser,
    '民生银行': CMBCParser,
    '上海银行': BOCOM_SHParser,
}


def get_parser(bank_name: str):
    """根据银行名获取解析器实例。"""
    parser_cls = PARSER_MAP.get(bank_name)
    if parser_cls:
        return parser_cls()
    return None
