"""还款提醒 - 检查到期日并通过微信推送。"""

from datetime import datetime, timedelta
import yaml
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "config.yaml"


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def check_due(days_before=5):
    """检查还款日，返回提醒列表。

    Args:
        days_before: 提前 N 天开始提醒（默认5天）
    """
    from src.db import get_unpaid_bills

    unpaid = get_unpaid_bills()
    if not unpaid:
        print("没有未还款单，无需提醒")
        return []

    today = datetime.now()
    reminders = []

    for bill_id, bank, bill_month, total_amount, due_date_full, pay_date in unpaid:
        candidate = datetime.strptime(due_date_full, '%Y-%m-%d')

        # 如果已过期，加一个月找下一次
        while candidate.date() < today.date():
            if candidate.month == 12:
                candidate = datetime(candidate.year + 1, 1, candidate.day)
            else:
                import calendar as _cal
                max_day = _cal.monthrange(candidate.year, candidate.month + 1)[1]
                day = min(candidate.day, max_day)
                candidate = datetime(candidate.year, candidate.month + 1, day)

        due_str = candidate.strftime('%Y-%m-%d')
        days_until = (candidate.date() - today.date()).days

        if 0 <= days_until <= days_before:
            reminders.append({
                'bank': bank,
                'card_last4': '未知',
                'due_date': due_str,
                'days_until': days_until,
                'today_amount': total_amount if total_amount and total_amount > 0 else None,
            })

    # Sort by days until due
    reminders.sort(key=lambda r: r['days_until'])
    return reminders


def format_reminder(reminders):
    """格式化提醒消息。"""
    if not reminders:
        return None

    today = datetime.now().strftime('%m月%d日')
    lines = [f"📅 {today} 信用卡还款提醒\n"]

    # Group by urgency
    today_cards = [r for r in reminders if r['days_until'] == 0]
    soon_cards = [r for r in reminders if 1 <= r['days_until'] <= 3]
    later_cards = [r for r in reminders if r['days_until'] > 3]

    if today_cards:
        lines.append("🔴 **今天到期:**")
        for r in today_cards:
            amt = f"¥{r['today_amount']:,.2f}" if r['today_amount'] else "金额未定"
            lines.append(f"  {r['bank']} ****{r['card_last4']} — {amt}")

    if soon_cards:
        lines.append("🟡 **未来3天内到期:**")
        for r in soon_cards:
            amt = f"¥{r['today_amount']:,.2f}" if r['today_amount'] else "金额未定"
            lines.append(f"  {r['bank']} ****{r['card_last4']} — {amt}（{r['days_until']}天后）")

    if later_cards:
        lines.append("🟢 **5天内到期:**")
        for r in later_cards:
            amt = f"¥{r['today_amount']:,.2f}" if r['today_amount'] else "金额未定"
            lines.append(f"  {r['bank']} ****{r['card_last4']} — {amt}（{r['days_until']}天后）")

    total = sum(r['today_amount'] for r in reminders if r['today_amount'])

    if total > 0:
        lines.append(f"\n💰 近期合计待还: ¥{total:,.2f}")

    lines.append(f"\n共 {len(reminders)} 张卡需要还款")
    return '\n'.join(lines)


def run(days_before=5):
    """运行提醒检查。"""
    reminders = check_due(days_before)

    if not reminders:
        print("✅ 近期没有需要还款的卡片")
        return

    message = format_reminder(reminders)
    print(message)

    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"reminders_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(message)

    print(f"\n📝 已保存到 {log_file}")


if __name__ == '__main__':
    run()
