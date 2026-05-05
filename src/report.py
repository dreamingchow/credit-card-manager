"""报表生成 - 月度/季度/年度消费汇总。"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def generate_report(period_type='month', period_value=None):
    """生成报表数据。"""
    from src.db import get_report_data

    rows = get_report_data(period_type, period_value)

    if not rows:
        return None

    # Aggregate by bank
    bank_data = {}
    total_all = 0
    min_all = 0

    for bank, card_last4, month, amount, min_pay in rows:
        if bank not in bank_data:
            bank_data[bank] = {'cards': set(), 'months': {}, 'total': 0, 'min_total': 0}
        bank_data[bank]['cards'].add(card_last4)
        # Store both amount and min_pay per month
        if month not in bank_data[bank]['months']:
            bank_data[bank]['months'][month] = {'amount': 0, 'min_pay': 0}
        bank_data[bank]['months'][month]['amount'] += amount
        bank_data[bank]['months'][month]['min_pay'] = (min_pay or 0)  # keep per-period value
        bank_data[bank]['total'] += amount
        if min_pay:
            bank_data[bank]['min_total'] += min_pay
        total_all += amount
        if min_pay:
            min_all += min_pay

    return {
        'bank_data': bank_data,
        'total': total_all,
        'min_total': min_all,
    }


def format_report(data, period_type='month', period_value=None):
    """格式化为 Markdown。"""
    lines = []

    if period_type == 'month':
        title = f"📊 {period_value} 信用卡消费报告"
    elif period_type == 'quarter':
        year = datetime.now().year
        q = (datetime.now().month - 1) // 3 + 1  # default to current quarter
        if period_value:
            if isinstance(period_value, str) and period_value.isdigit():
                val = int(period_value)
                if val <= 12:
                    q = val  # it's a quarter number
                else:
                    year = val  # it's a year, keep default q
            elif isinstance(period_value, int):
                if period_value <= 12:
                    q = period_value
                else:
                    year = period_value
            else:
                year = int(period_value)
        title = f"📊 {year}年Q{q} 信用卡消费报告"
    elif period_type == 'year':
        title = f"📊 {period_value or datetime.now().year}年 信用卡年度消费报告"
    else:
        title = "📊 信用卡消费报告"

    lines.append(title)
    lines.append("")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    lines.append("## 总览")
    lines.append("")
    lines.append("| 项目 | 金额 |")
    lines.append("|------|------|")
    lines.append(f"| 本期总应还 | ¥{data['total']:,.2f} |")
    lines.append(f"| 最低还款合计 | ¥{data['min_total']:,.2f} |")
    lines.append(f"| 可差额（应还-最低） | ¥{data['total'] - data['min_total']:,.2f} |")
    lines.append("")

    lines.append("## 各卡明细")
    lines.append("")
    lines.append("| 银行 | 卡号 | 期数 | 应还金额 | 最低还款 |")
    lines.append("|------|------|------|----------|----------|")

    for bank in sorted(data['bank_data'].keys()):
        info = data['bank_data'][bank]
        cards = ', '.join(f"****{c}" for c in info['cards'] if c)

        for month in sorted(info['months'].keys()):
            entry = info['months'][month]
            amount = entry['amount']
            min_pay = entry['min_pay'] or 0  # 0 if not parsed from bill
            lines.append(f"| {bank} | {cards} | {month} | ¥{amount:,.2f} | ¥{min_pay:,.2f} |")

    lines.append("")
    lines.append("## 银行汇总")
    lines.append("")
    lines.append("| 银行 | 总应还 | 卡数 |")
    lines.append("|------|--------|------|")

    for bank in sorted(data['bank_data'].keys()):
        info = data['bank_data'][bank]
        lines.append(f"| {bank} | ¥{info['total']:,.2f} | {len(info['cards'])} |")

    lines.append(f"| **合计** | **¥{data['total']:,.2f}** | **{len(data['bank_data'])}** |")
    lines.append("")

    return '\n'.join(lines)


def run(period_type='month', period_value=None):
    """运行报表生成。"""
    data = generate_report(period_type, period_value)
    if not data:
        print(f"没有 {period_type} 的账单数据")
        return

    report = format_report(data, period_type, period_value)

    reports_dir = BASE_DIR / "reports"
    reports_dir.mkdir(exist_ok=True)

    if period_type == 'month':
        filename = f"credit_report_{period_value}.md"
    elif period_type == 'quarter':
        year = datetime.now().year
        q = (datetime.now().month - 1) // 3 + 1
        if period_value:
            if isinstance(period_value, str) and period_value.isdigit():
                val = int(period_value)
                if val <= 12:
                    q = val
                else:
                    year = val
            elif isinstance(period_value, int):
                if period_value <= 12:
                    q = period_value
                else:
                    year = period_value
            else:
                year = int(period_value)
        filename = f"credit_report_{year}_Q{q}.md"
    else:
        filename = f"credit_report_{period_value}_annual.md"

    filepath = reports_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"📄 报告已保存到: {filepath}")
    print()
    print(report)


if __name__ == '__main__':
    import sys

    period_type = 'month'
    period_value = datetime.now().strftime('%Y-%m')

    if '--quarter' in sys.argv:
        period_type = 'quarter'
        year = datetime.now().year
        q = int(sys.argv[sys.argv.index('--quarter') + 1]) if sys.argv.index('--quarter') + 1 < len(sys.argv) else 1
        period_value = str(year)
    elif '--year' in sys.argv:
        period_type = 'year'
        year = int(sys.argv[sys.argv.index('--year') + 1]) if sys.argv.index('--year') + 1 < len(sys.argv) else datetime.now().year
        period_value = str(year)
    elif '--month' in sys.argv:
        period_value = sys.argv[sys.argv.index('--month') + 1]

    run(period_type, period_value)
