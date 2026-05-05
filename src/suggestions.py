"""还款计划建议 — 基于历史数据给出消费和还款建议。"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def format_suggestions():
    """生成还款建议。"""
    from src.db import get_spending_by_bank, get_unpaid_summary

    spending = get_spending_by_bank()
    summary = get_unpaid_summary()

    if not spending:
        return "数据不足，无法生成建议。请先解析更多账单。\n"

    lines = []
    now = datetime.now().strftime('%Y-%m-%d')

    lines.append(f"💡 **还款计划建议** — {now}\n")

    # Section 1: Overall advice
    lines.append("## 📊 总体建议")
    lines.append("")

    avg_total = sum(s['avg_monthly'] for s in spending) / len(spending) if spending else 0
    lines.append(f"- 当前月均消费: **¥{avg_total:,.2f}**")
    lines.append(f"- 待还总额: **¥{summary['unpaid_total']:,.2f}**（{summary['unpaid_count']} 笔）")

    if summary['unpaid_total'] > avg_total * 1.5:
        lines.append(f"- ⚠️ 待还金额超过月均消费 1.5 倍，建议优先处理大额账单")
    elif summary['unpaid_total'] <= avg_total:
        lines.append(f"- ✅ 待还金额在正常范围内")

    # Section 2: Per bank suggestions
    lines.append(f"\n## 🏦 各卡建议")
    lines.append("")

    for s in spending:
        bank = s['bank']
        avg = s['avg_monthly']
        last_paid = s['last_paid_month']

        lines.append(f"### {bank}")
        lines.append(f"- 月均消费: ¥{avg:,.2f}")
        lines.append(f"- 历史还款次数: {s['paid_count']}")

        # Check if this bank has unpaid bills
        from src.db import get_connection
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT bill_month, total_amount FROM bills
                     WHERE bank = ? AND paid = 0 AND total_amount IS NOT NULL
                     ORDER BY bill_month DESC''', (bank,))
        unpaid = c.fetchall()
        conn.close()

        if unpaid:
            for bill_month, amount in unpaid:
                lines.append(f"- ⏳ 待还: {bill_month} — ¥{amount:,.2f}")

            # Suggest full payment vs minimum
            if avg > 1000:
                lines.append(f"- 💡 **建议全额还款**（月均消费 ¥{avg:,.2f}，大额账单避免分期手续费）")
            elif avg > 0:
                lines.append(f"- 💡 可根据现金流选择最低还款或全额还款")
            else:
                lines.append(f"- 💡 金额较小，建议及时还清避免逾期")
        else:
            lines.append(f"- ✅ 无待还账单")

        lines.append("")

    # Section 3: Cash flow planning
    lines.append("## 📅 现金流规划建议")
    lines.append("")

    # Sort spending by avg_monthly descending
    sorted_spending = sorted(spending, key=lambda x: x['avg_monthly'], reverse=True)

    if sorted_spending:
        lines.append("按月均消费排序（优先预留大额卡）:")
        for i, s in enumerate(sorted_spending, 1):
            lines.append(f"  {i}. {s['bank']}: ¥{s['avg_monthly']:,.2f}/月")

        lines.append(f"\n💡 建议每月预留 ¥{sum(s['avg_monthly'] for s in sorted_spending):,.2f} 用于信用卡还款")
        lines.append(f"   （可考虑设置自动还款，避免逾期产生利息）")

    return '\n'.join(lines)


def run():
    """运行建议生成。"""
    report = format_suggestions()
    print(report)
