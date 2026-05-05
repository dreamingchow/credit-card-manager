"""还款标记 - 记录已还款。"""

from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent


def mark_paid(bank, bill_month):
    """标记账单已还款，记录还款日期。"""
    from src.db import get_connection

    conn = get_connection()
    c = conn.cursor()

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

    c.execute('UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?', (pay_date, bill_id))
    conn.commit()

    print(f"✅ {bank} {bill_month} 已标记还款")
    print(f"   金额: ¥{amount:,.2f}")
    print(f"   还款日期: {pay_date}")

    conn.close()
    return True


def main():
    import sys
    if len(sys.argv) != 3:
        print("用法: python mark_paid.py <银行名> <账单月份>")
        print("示例: python mark_paid.py 邮储银行 2026-04")
        sys.exit(1)

    bank = sys.argv[1]
    bill_month = sys.argv[2]
    mark_paid(bank, bill_month)


if __name__ == '__main__':
    main()
