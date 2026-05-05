#!/usr/bin/env python3
"""
还款日检查 + 微信推送。

每天运行，检查未来1天内的还款日，通过 default profile gateway 推送微信提醒。

用法:
    python check_due.py              # 检查今天和明天的还款日
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta


DB_PATH = Path(__file__).parent / "db" / "cards.db"
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    import yaml
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def mark_paid(bank, bill_month):
    """标记账单已还款，记录还款日期"""
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # 查找对应账单
    c.execute('''SELECT id, total_amount FROM bills 
                 WHERE bank = ? AND bill_month = ? AND paid = 0
                 ORDER BY bill_month DESC LIMIT 1''', (bank, bill_month))
    row = c.fetchone()

    if not row:
        print(f"未找到 {bank} {bill_month} 的未还款账单")
        conn.close()
        return False

    bill_id, amount = row
    pay_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    c.execute('''UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?''', (pay_date, bill_id))
    conn.commit()

    print(f"✅ {bank} {bill_month} 已标记还款")
    print(f"   金额: ¥{amount:,.2f}")
    print(f"   还款日期: {pay_date}")

    conn.close()
    return True


def check_due():
    config = load_config()
    reminder_cfg = config['reminder']
    days_before = reminder_cfg.get('days_before', [1, 0])

    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Get all cards with due_day set
    c.execute('SELECT id, bank, card_last4, due_date_full FROM cards WHERE due_date_full IS NOT NULL')
    cards = c.fetchall()

    if not cards:
        print("没有卡片数据，请先运行 parse_bills.py")
        conn.close()
        return []

    today = datetime.now()
    reminders = []

    for card_id, bank, card_last4, due_date_full in cards:
        # Use the full due date directly from the bill
        candidate = datetime.strptime(due_date_full, '%Y-%m-%d')
        due_str = candidate.strftime('%Y-%m-%d')

        # Check if within reminder window
        for r_offset in days_before:
            check_date = today + timedelta(days=r_offset)
            if candidate.date() == check_date.date():
                reminders.append({
                    'bank': bank,
                    'card_last4': card_last4 or '未知',
                    'due_date': due_str,
                    'offset': r_offset,
                    'today_amount': get_today_amount(c, card_id),
                })

    conn.close()
    return reminders


def get_today_amount(cursor, card_id):
    """获取当前待还金额（最近一期未还款的账单）"""
    cursor.execute('''SELECT total_amount FROM bills WHERE card_id = ?
                      AND total_amount IS NOT NULL
                      AND paid = 0
                      ORDER BY bill_month DESC LIMIT 1''', (card_id,))
    row = cursor.fetchone()
    if row and row[0]:
        return row[0]
    return None


def format_reminder(reminders):
    """格式化提醒消息"""
    if not reminders:
        return None

    today = datetime.now().strftime('%m月%d日')
    lines = [f"📅 {today} 信用卡还款提醒\n"]

    # Group by urgency
    today_cards = [r for r in reminders if r['offset'] == 0]
    tomorrow_cards = [r for r in reminders if r['offset'] == 1]

    if today_cards:
        lines.append("🔴 **今天到期:**")
        for r in today_cards:
            amt = f"¥{r['today_amount']:,.2f}" if r['today_amount'] else "金额未定"
            lines.append(f"  {r['bank']} ****{r['card_last4']} — {amt}")

    if tomorrow_cards:
        lines.append("🟡 **明天到期:**")
        for r in tomorrow_cards:
            amt = f"¥{r['today_amount']:,.2f}" if r['today_amount'] else "金额未定"
            lines.append(f"  {r['bank']} ****{r['card_last4']} — {amt}")

    # Summary
    total_today = sum(r['today_amount'] for r in today_cards if r['today_amount'])
    total_tomorrow = sum(r['today_amount'] for r in tomorrow_cards if r['today_amount'])
    total = total_today + total_tomorrow

    if total > 0:
        lines.append(f"\n💰 今日合计待还: ¥{total:,.2f}")

    lines.append(f"\n共 {len(reminders)} 张卡需要还款")
    return '\n'.join(lines)


def main():
    reminders = check_due()

    if not reminders:
        print("✅ 近期没有需要还款的卡片")
        return

    message = format_reminder(reminders)
    print(message)

    # Save reminder to log
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / f"reminders_{datetime.now().strftime('%Y%m%d')}.log"
    with open(log_file, 'w', encoding='utf-8') as f:
        f.write(message)

    print(f"\n📝 已保存到 {log_file}")


if __name__ == '__main__':
    main()
