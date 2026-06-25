"""总负债仪表盘 — 实时汇总当前信用卡状况。"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def format_dashboard():
    """生成仪表盘视图。"""
    from src.db import get_unpaid_summary, get_spending_by_bank

    summary = get_unpaid_summary()
    spending = get_spending_by_bank()

    lines = []
    now = datetime.now().strftime('%m月%d日 %H:%M')

    # Header
    lines.append(f"💳 **信用卡总负债仪表盘** — {now}\n")

    # Section 1: Unpaid summary
    lines.append("## 🚨 待还总览")
    lines.append("")
    lines.append(f"| 项目 | 数值 |")
    lines.append(f"|------|------|")
    lines.append(f"| 待还笔数 | {summary['unpaid_count']} 笔 |")
    lines.append(f"| 待还总额 | ¥{summary['unpaid_total']:,.2f} |")

    # Top 3 biggest
    unpaid_sorted = sorted(summary['unpaid_cards'], key=lambda x: abs(x[3] or 0), reverse=True)
    if unpaid_sorted:
        lines.append(f"\n**Top 3 最大待还:**")
        for bank, card_last4, due_date, amount, *rest in unpaid_sorted[:3]:
            card = f"****{card_last4}" if card_last4 else "无卡号"
            due = due_date or "—"
            amt = f"¥{amount:,.2f}" if amount else "—"
            lines.append(f"  • {bank} {card} — {amt}（到期日 {due}）")

    # Section 2: Monthly spending trend
    lines.append(f"\n## 📈 近6月消费趋势")
    lines.append("")

    if summary['monthly_trend']:
        # Calculate MoM change
        trend = list(summary['monthly_trend'])  # already DESC (newest first)
        lines.append("| 月份 | 总消费 | 环比变化 |")
        lines.append("|------|--------|----------|")

        prev_total = None
        for bill_month, total in trend:
            amt = f"¥{total:,.2f}"
            if prev_total is not None and prev_total > 0:
                change = ((total - prev_total) / prev_total) * 100
                arrow = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                change_str = f"{arrow} {abs(change):.1f}%"
            else:
                change_str = "—"
            lines.append(f"| {bill_month} | {amt} | {change_str} |")
            prev_total = total
    else:
        lines.append("暂无数据\n")

    # Section 3: Spending by bank (avg monthly)
    lines.append(f"\n## 🏦 各银行月均消费")
    lines.append("")
    lines.append("| 银行 | 月均消费 | 历史还款次数 | 累计已还 |")
    lines.append("|------|----------|-------------|----------|")

    for s in spending:
        avg = f"¥{s['avg_monthly']:,.2f}" if s['avg_monthly'] > 0 else "—"
        lines.append(f"| {s['bank']} | {avg} | {s['paid_count']} | ¥{s['total_paid']:,.2f} |")

    # Section 4: Upcoming (next 30 days)
    from src.db import get_card_due_dates, get_unpaid_amount_by_card

    cards = get_card_due_dates()
    upcoming_30 = []
    today = datetime.now().date()

    for card_id, bank, card_last4, due_date_full in cards:
        try:
            candidate = datetime.strptime(due_date_full, '%Y-%m-%d').date()
            while candidate < today:
                if candidate.month == 12:
                    candidate = datetime(candidate.year + 1, 1, candidate.day).date()
                else:
                    import calendar as cal
                    max_day = cal.monthrange(candidate.year, candidate.month + 1)[1]
                    d = min(candidate.day, max_day)
                    candidate = datetime(candidate.year, candidate.month + 1, d).date()

            days_until = (candidate - today).days
            if 0 <= days_until <= 30:
                amt = get_unpaid_amount_by_card(card_id)
                upcoming_30.append({
                    'bank': bank,
                    'card_last4': card_last4 or '?',
                    'due_date': candidate,
                    'days_until': days_until,
                    'amount': amt,
                })
        except Exception:
            pass

    upcoming_30.sort(key=lambda x: x['days_until'])

    if upcoming_30:
        lines.append(f"\n## ⏰ 未来30天到期")
        lines.append("")
        for u in upcoming_30:
            card = f"****{u['card_last4']}" if u['card_last4'] else "无卡号"
            amt = f"¥{u['amount']:,.2f}" if u['amount'] else "—"
            urgency = "🔴" if u['days_until'] == 0 else "🟡" if u['days_until'] <= 7 else "🟢"
            lines.append(f"  {urgency} {u['bank']} {card} — {amt}（{u['due_date'].strftime('%m/%d')}，{u['days_until']}天后）")

    return '\n'.join(lines)


def run():
    """运行仪表盘。"""
    report = format_dashboard()
    print(report)
