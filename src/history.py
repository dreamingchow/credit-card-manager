"""历史还款记录查询。"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def format_history(bank=None):
    """格式化历史还款记录。"""
    from src.db import get_payment_history

    rows = get_payment_history(bank)

    if not rows:
        return "没有历史还款记录。\n"

    lines = []
    if bank:
        lines.append(f"📋 **{bank} 还款历史**\n")
    else:
        lines.append(f"📋 **全部还款历史**\n")

    # Group by bank
    from collections import defaultdict
    by_bank = defaultdict(list)
    for row in rows:
        by_bank[row[0]].append(row)

    for bank_name in sorted(by_bank.keys()):
        records = by_bank[bank_name]
        lines.append(f"\n### {bank_name}（共 {len(records)} 笔）")
        lines.append("")
        lines.append("| 账单月份 | 金额 | 还款时间 |")
        lines.append("|----------|------|----------|")

        total_paid = 0
        for b_bank, bill_month, amount, pay_date, paid in records:
            amt = f"¥{amount:,.2f}" if amount else "—"
            pay_time = pay_date.split(' ')[1][:5] if pay_date and ' ' in pay_date else pay_date or "—"
            lines.append(f"| {bill_month} | {amt} | {pay_time} |")
            if amount:
                total_paid += amount

        lines.append(f"\n💰 累计还款: ¥{total_paid:,.2f}")

    return '\n'.join(lines)


def run(bank=None):
    """运行历史记录查询。"""
    report = format_history(bank)
    print(report)
