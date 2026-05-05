"""还款日历视图 — 按月展示所有到期日。"""

from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def get_month_name(month):
    months = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二']
    return months[month]


def format_calendar(year=None, month=None):
    """生成日历视图。"""
    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month

    from src.db import get_calendar_data

    entries = get_calendar_data(year, month)
    if not entries:
        return f"📅 {year}年{get_month_name(month)}月 — 暂无到期账单\n"

    today = datetime.now().date()
    month_name = f"{year}年{get_month_name(month)}月"

    lines = [f"📅 **{month_name} 还款日历**\n"]

    # Group by day
    from collections import defaultdict
    by_day = defaultdict(list)
    for e in entries:
        by_day[e['due_date'].day].append(e)

    # Show days that have entries, plus today highlight
    sorted_days = sorted(by_day.keys())

    for day in sorted_days:
        date_str = f"{month}月{day}日"
        if day == today.day:
            date_str = f"**🔴 {date_str} (今天)**"

        day_entries = by_day[day]
        lines.append(f"\n**{date_str}**")

        for e in sorted(day_entries, key=lambda x: x['bank']):
            amt = f"¥{e['amount']:,.2f}" if e['amount'] else "—"
            days_label = ""
            if e['is_today']:
                days_label = " 🔴今天"
            elif e['days_until'] <= 3:
                days_label = f" 🟡{e['days_until']}天后"
            else:
                days_label = f" 🟢{e['days_until']}天后"

            card = f"****{e['card_last4']}" if e['card_last4'] else "无卡号"
            lines.append(f"  {e['bank']} {card} — {amt}{days_label}")

    # Summary
    total = sum(e['amount'] for e in entries if e['amount'])
    lines.append(f"\n---")
    lines.append(f"💰 本月到期总额: ¥{total:,.2f}")
    lines.append(f"📋 共 {len(entries)} 笔待还")

    return '\n'.join(lines)


def run(year=None, month=None):
    """运行日历视图。"""
    report = format_calendar(year, month)
    print(report)
