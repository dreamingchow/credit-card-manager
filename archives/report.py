#!/usr/bin/env python3
"""
信用卡消费分析报告。

生成月度/季度/年度消费汇总，输出 Markdown 格式。

用法:
    python report.py --month 2026-05      # 指定月份
    python report.py --quarter 2           # 指定季度（1-4）
    python report.py --year 2026           # 指定年度
    python report.py                     # 默认本月
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime


DB_PATH = Path(__file__).parent / "db" / "cards.db"
REPORTS_DIR = Path(__file__).parent / "reports"


def generate_report(conn, period_type='month', period_value=None):
    """生成消费分析报告"""
    c = conn.cursor()

    if period_type == 'month':
        if not period_value:
            period_value = datetime.now().strftime('%Y-%m')
        query = '''SELECT bank, card_last4, bill_month, total_amount, min_payment
                   FROM bills WHERE bill_month = ? AND total_amount IS NOT NULL
                   ORDER BY bank'''
        params = (period_value,)
    elif period_type == 'quarter':
        year = int(period_value) if period_value else datetime.now().year
        q = int(sys.argv[sys.argv.index('--quarter')] + 1) if '--quarter' in sys.argv else 1
        start = f"{year}-{(q-1)*3+1:02d}-01"
        end = f"{year}-{min(q*3, 12):02d}-28"
        query = '''SELECT bank, card_last4, bill_month, total_amount, min_payment
                   FROM bills WHERE bill_month >= ? AND bill_month <= ? AND total_amount IS NOT NULL
                   ORDER BY bank'''
        params = (start, end)
    elif period_type == 'year':
        year = int(period_value) if period_value else datetime.now().year
        query = '''SELECT bank, card_last4, bill_month, total_amount, min_payment
                   FROM bills WHERE bill_month LIKE ? AND total_amount IS NOT NULL
                   ORDER BY bank, bill_month'''
        params = (f"{year}-%",)
    else:
        raise ValueError(f"Unknown period type: {period_type}")

    c.execute(query, params)
    rows = c.fetchall()

    if not rows:
        print(f"没有 {period_type} 的账单数据")
        return None

    # Aggregate by bank
    bank_data = {}
    total_all = 0
    min_all = 0

    for bank, card_last4, month, amount, min_pay in rows:
        if bank not in bank_data:
            bank_data[bank] = {'cards': set(), 'months': {}, 'total': 0, 'min_total': 0}
        bank_data[bank]['cards'].add(card_last4)
        bank_data[bank]['months'][month] = amount
        bank_data[bank]['total'] += amount
        bank_data[bank]['min_total'] += (min_pay or 0)
        total_all += amount
        min_all += (min_pay or 0)

    return {
        'bank_data': bank_data,
        'total': total_all,
        'min_total': min_all,
        'rows': rows,
    }


def format_report(data, period_type='month', period_value=None):
    """格式化为 Markdown"""
    lines = []

    if period_type == 'month':
        title = f"📊 {period_value} 信用卡消费报告"
    elif period_type == 'quarter':
        year = period_value or datetime.now().year
        q = sys.argv[sys.argv.index('--quarter')] + 1 if '--quarter' in sys.argv else '1'
        title = f"📊 {year}年Q{q} 信用卡消费报告"
    elif period_type == 'year':
        title = f"📊 {period_value or datetime.now().year}年 信用卡年度消费报告"
    else:
        title = "📊 信用卡消费报告"

    lines.append(title)
    lines.append("")
    lines.append(f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")

    # Summary table
    lines.append("## 总览")
    lines.append("")
    lines.append("| 项目 | 金额 |")
    lines.append("|------|------|")
    lines.append(f"| 本期总应还 | ¥{data['total']:,.2f} |")
    lines.append(f"| 最低还款合计 | ¥{data['min_total']:,.2f} |")
    lines.append(f"| 可差额（应还-最低） | ¥{data['total'] - data['min_total']:,.2f} |")
    lines.append("")

    # Per bank breakdown
    lines.append("## 各卡明细")
    lines.append("")
    lines.append("| 银行 | 卡号 | 期数 | 应还金额 | 最低还款 |")
    lines.append("|------|------|------|----------|----------|")

    for bank in sorted(data['bank_data'].keys()):
        info = data['bank_data'][bank]
        cards = ', '.join(f"****{c}" for c in info['cards'])

        for month, amount in sorted(info['months'].items()):
            min_pay = info['min_total'] / len(info['months']) if info['months'] else 0
            lines.append(f"| {bank} | {cards} | {month} | ¥{amount:,.2f} | ¥{min_pay:,.2f} |")

    lines.append("")

    # Bank summary
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


def main():
    import argparse
    parser = argparse.ArgumentParser(description='信用卡消费分析报告')
    parser.add_argument('--month', help='月份 (YYYY-MM)')
    parser.add_argument('--quarter', type=int, help='季度 (1-4)')
    parser.add_argument('--year', type=int, help='年度')
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))

    if args.month:
        period_type, period_value = 'month', args.month
    elif args.quarter is not None:
        period_type, period_value = 'quarter', str(args.year or datetime.now().year)
    elif args.year:
        period_type, period_value = 'year', str(args.year)
    else:
        period_type, period_value = 'month', datetime.now().strftime('%Y-%m')

    data = generate_report(conn, period_type, period_value)
    if not data:
        conn.close()
        return

    report = format_report(data, period_type, period_value)

    # Save to file
    REPORTS_DIR.mkdir(exist_ok=True)

    if period_type == 'month':
        filename = f"credit_report_{period_value}.md"
    elif period_type == 'quarter':
        year = period_value or datetime.now().year
        q = sys.argv[sys.argv.index('--quarter')] + 1 if '--quarter' in sys.argv else '1'
        filename = f"credit_report_{year}_Q{q}.md"
    else:
        filename = f"credit_report_{period_value}_annual.md"

    filepath = REPORTS_DIR / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"📄 报告已保存到: {filepath}")
    print()
    print(report)

    conn.close()


if __name__ == '__main__':
    main()
