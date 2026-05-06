"""数据库初始化、连接和查询封装。"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "db" / "cards.db"


def get_connection():
    """获取数据库连接（自动初始化表结构）。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    _init_db(conn)
    return conn


def _init_db(conn):
    """创建表结构（幂等）。"""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank TEXT NOT NULL,
        card_last4 TEXT,
        due_date_full TEXT,
        card_number TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS bills (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER REFERENCES cards(id),
        bank TEXT NOT NULL,
        bill_month TEXT NOT NULL,
        total_amount REAL,
        min_payment REAL,
        due_date TEXT,
        due_date_full TEXT,
        paid INTEGER DEFAULT 0,
        pay_date TEXT,
        source_file TEXT,
        raw_data TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        parsed_at TEXT DEFAULT (datetime('now'))
    )''')

    # 迁移：如果 pay_date 列不存在则添加
    try:
        c.execute("SELECT pay_date FROM bills LIMIT 1")
    except sqlite3.OperationalError:
        c.execute("ALTER TABLE bills ADD COLUMN pay_date TEXT")

    conn.commit()


def get_unpaid_bills():
    """获取所有未还款账单。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT id, bank, bill_month, total_amount, due_date_full, pay_date
                 FROM bills WHERE paid = 0 AND total_amount IS NOT NULL
                 ORDER BY due_date_full''')
    rows = c.fetchall()
    conn.close()
    return rows


def mark_bill_paid(bill_id, pay_date=None):
    """标记账单已还款。"""
    conn = get_connection()
    c = conn.cursor()
    if pay_date is None:
        from datetime import datetime
        pay_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    c.execute('UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?', (pay_date, bill_id))
    conn.commit()
    conn.close()
    return c.rowcount > 0


def get_card_due_dates():
    """获取所有卡片的到期日信息。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, bank, card_last4, due_date_full FROM cards WHERE due_date_full IS NOT NULL')
    rows = c.fetchall()
    conn.close()
    return rows


def get_unpaid_amount_by_card(card_id):
    """获取某卡最近一期未还款金额。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT total_amount FROM bills WHERE card_id = ?
                 AND total_amount IS NOT NULL AND paid = 0
                 ORDER BY bill_month DESC LIMIT 1''', (card_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


def get_report_data(period_type='month', period_value=None):
    """获取报表数据。"""
    conn = get_connection()
    c = conn.cursor()

    # card_last4 is in cards table, join to get it
    base_query = '''SELECT b.bank, c.card_last4, b.bill_month, b.total_amount, b.min_payment
                    FROM bills b LEFT JOIN cards c ON b.card_id = c.id'''

    if period_type == 'month':
        if not period_value:
            from datetime import datetime
            period_value = datetime.now().strftime('%Y-%m')
        query = f"{base_query} WHERE b.bill_month = ? AND b.total_amount IS NOT NULL ORDER BY b.bank"
        params = (period_value,)
    elif period_type == 'quarter':
        from datetime import datetime
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
        start = f"{year}-{(q-1)*3+1:02d}"
        end = f"{year}-{min(q*3, 12):02d}"
        query = f"{base_query} WHERE b.bill_month >= ? AND b.bill_month <= ? AND b.total_amount IS NOT NULL ORDER BY b.bank"
        params = (start, end)
    elif period_type == 'year':
        year = int(period_value) if period_value else datetime.now().year
        query = f"{base_query} WHERE b.bill_month LIKE ? AND b.total_amount IS NOT NULL ORDER BY b.bank, b.bill_month"
        params = (f"{year}-%",)
    else:
        raise ValueError(f"Unknown period type: {period_type}")

    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return rows


def get_calendar_data(year=None, month=None):
    """获取日历视图数据。

    Returns list of dicts: {bank, card_last4, due_date (original), amount, is_today, days_until, is_overdue}
    """
    from datetime import datetime, timedelta

    if year is None:
        year = datetime.now().year
    if month is None:
        month = datetime.now().month

    conn = get_connection()
    c = conn.cursor()

    # Get all unpaid bills with due dates
    c.execute('''SELECT b.id, b.bank, c.card_last4, c.holder_name, b.due_date_full, b.total_amount
                 FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                 WHERE b.paid = 0 AND b.due_date_full IS NOT NULL AND b.total_amount IS NOT NULL
                 ORDER BY b.due_date_full''')
    rows = c.fetchall()
    conn.close()

    today = datetime.now().date()
    # Target month range: show bills due in target month + next month for context
    target_start = datetime(year, month, 1).date()
    target_end = datetime(year, min(month + 2, 12), 1).date() - timedelta(days=1)

    # Also collect overdue bills (due before target_start but still unpaid)
    overdue_entries = []

    calendar_entries = []
    for bill_id, bank, card_last4, holder_name, due_date_full, amount in rows:
        original_due = datetime.strptime(due_date_full, '%Y-%m-%d').date()

        # If overdue (before today), add to overdue list — show all unpaid overdue bills
        if original_due < today:
            days_past = (today - original_due).days
            overdue_entries.append({
                'bank': bank,
                'holder_name': holder_name or '',
                'card_last4': card_last4 or '?',
                'due_date': original_due,
                'amount': amount,
                'is_today': False,
                'days_until': -days_past,  # negative = overdue by N days
                'is_overdue': True,
            })
        elif target_start <= original_due <= target_end:
            days_until = (original_due - today).days
            calendar_entries.append({
                'bank': bank,
                'holder_name': holder_name or '',
                'card_last4': card_last4 or '?',
                'due_date': original_due,
                'amount': amount,
                'is_today': original_due == today,
                'days_until': days_until,
                'is_overdue': False,
            })

    # Overdue first (sorted by most overdue), then upcoming
    all_entries = sorted(overdue_entries + calendar_entries, key=lambda e: (e['due_date'], e['bank']))
    return all_entries


def get_unpaid_summary():
    """获取未还款总览数据。"""
    conn = get_connection()
    c = conn.cursor()

    # Total unpaid
    c.execute('SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM bills WHERE paid = 0 AND total_amount IS NOT NULL')
    count, total = c.fetchone()

    # By card (latest unpaid per card)
    c.execute('''SELECT b.bank, c.card_last4, b.due_date_full, b.total_amount, b.bill_month
                 FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                 WHERE b.paid = 0 AND b.total_amount IS NOT NULL
                 ORDER BY b.due_date_full''')
    cards = c.fetchall()

    # Monthly spending trend (last 6 months)
    c.execute('''SELECT bill_month, SUM(total_amount) FROM bills
                 WHERE total_amount IS NOT NULL AND paid = 1
                 GROUP BY bill_month ORDER BY bill_month DESC LIMIT 6''')
    monthly_trend = c.fetchall()

    # All bills (paid + unpaid) for spending analysis
    c.execute('''SELECT bank, bill_month, total_amount, paid FROM bills
                 WHERE total_amount IS NOT NULL ORDER BY bill_month DESC''')
    all_bills = c.fetchall()

    conn.close()

    return {
        'unpaid_count': count,
        'unpaid_total': total,
        'unpaid_cards': cards,
        'monthly_trend': monthly_trend,
        'all_bills': all_bills,
    }


def get_payment_history(bank=None, year=None, month=None):
    """获取历史还款记录。"""
    conn = get_connection()
    c = conn.cursor()

    if bank:
        sql = '''SELECT b.bank, b.bill_month, b.total_amount, b.pay_date, c.card_last4
                     FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                     WHERE b.paid = 1 AND b.bank = ?'''
        params = [bank]
    else:
        sql = '''SELECT b.bank, b.bill_month, b.total_amount, b.pay_date, c.card_last4
                     FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                     WHERE b.paid = 1'''
        params = []

    if year:
        sql += ' AND b.bill_month LIKE ?'
        params.append(f'{year}%')
    if month:
        sql += ' AND b.bill_month LIKE ?'
        params.append(f'%-{month.zfill(2)}')

    sql += ' ORDER BY b.bill_month DESC'
    c.execute(sql, params)

    rows = c.fetchall()
    conn.close()
    return rows


def get_spending_by_bank():
    """获取各银行消费统计（用于还款建议）。"""
    conn = get_connection()
    c = conn.cursor()

    # Per bank: total paid, avg monthly, latest unpaid
    c.execute('''SELECT b.bank,
                        COUNT(CASE WHEN b.paid = 1 THEN 1 END) as paid_count,
                        COALESCE(SUM(CASE WHEN b.paid = 1 THEN b.total_amount ELSE 0 END), 0) as total_paid,
                        AVG(CASE WHEN b.paid = 1 THEN b.total_amount ELSE NULL END) as avg_monthly,
                        MAX(CASE WHEN b.paid = 1 THEN b.bill_month END) as last_paid_month
                 FROM bills b WHERE b.total_amount IS NOT NULL
                 GROUP BY b.bank
                 ORDER BY avg_monthly DESC''')

    rows = c.fetchall()
    conn.close()

    result = []
    for bank, paid_count, total_paid, avg_monthly, last_paid_month in rows:
        # Handle negative amounts (overpayment/溢缴款) — treat as 0 for suggestions
        avg_val = round(avg_monthly, 2) if avg_monthly and avg_monthly > 0 else 0
        result.append({
            'bank': bank,
            'paid_count': paid_count,
            'total_paid': total_paid,
            'avg_monthly': avg_val,
            'last_paid_month': last_paid_month,
        })

    return result
