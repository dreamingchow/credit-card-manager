"""数据库初始化、连接和查询封装。"""

import sqlite3
import threading
from pathlib import Path

# Thread-local connection pool for Reusable connections
_local = threading.local()

DB_PATH = Path(__file__).parent.parent / "db" / "cards.db"


def parse_period_value(period_type, period_value):
    """解析报表周期参数，返回 (year, quarter_or_month)。

    Args:
        period_type: 'month', 'quarter', or 'year'
        period_value: raw string/int from API/CLI

    Returns:
        For 'month': (year_str, None) e.g. ('2026-05', None)
        For 'quarter': (year, quarter_num) e.g. (2026, 2)
        For 'year': (year_int, None) e.g. (2026, None)
    """
    from datetime import datetime

    if period_type == 'month':
        # Already in YYYY-MM format, just validate
        return (period_value, None)

    elif period_type == 'quarter':
        year = datetime.now().year
        q = (datetime.now().month - 1) // 3 + 1  # default to current quarter
        if period_value:
            # Support "year|q" format from frontend
            if isinstance(period_value, str) and '|' in period_value:
                parts = period_value.split('|')
                year = int(parts[0])
                q = int(parts[1])
            elif isinstance(period_value, str) and period_value.isdigit():
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
        return (year, q)

    elif period_type == 'year':
        year = int(period_value) if period_value else datetime.now().year
        return (year, None)

    raise ValueError(f"Unknown period type: {period_type}")


def get_connection():
    """获取数据库连接（自动初始化表结构，复用线程内连接）。"""
    if not hasattr(_local, 'conn') or _local.conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _local.conn = sqlite3.connect(str(DB_PATH))
        _local.conn.execute("PRAGMA foreign_keys = ON")
        _init_db(_local.conn)
    return _local.conn


def close_connection():
    """关闭当前线程的数据库连接。"""
    if hasattr(_local, 'conn') and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def _init_db(conn):
    """创建表结构（幂等）。"""
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank TEXT NOT NULL,
        card_last4 TEXT,
        due_date_full TEXT,
        card_number TEXT,
        holder_name TEXT,
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

    c.execute('''CREATE TABLE IF NOT EXISTS annual_fees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id INTEGER NOT NULL REFERENCES cards(id),
        amount REAL NOT NULL,
        waive_condition TEXT,
        charge_month INTEGER NOT NULL,
        charge_day INTEGER NOT NULL,
        is_first_year INTEGER DEFAULT 0,
        is_recurring INTEGER DEFAULT 1,
        status TEXT DEFAULT 'pending',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now'))
    )''')

    conn.commit()


def get_unpaid_bills():
    """获取所有未还款账单（含卡号信息）。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT b.id, b.bank, c.card_last4, b.bill_month, b.total_amount, b.due_date_full, b.pay_date
                 FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                 WHERE b.paid = 0 AND b.total_amount IS NOT NULL
                 ORDER BY b.due_date_full''')
    rows = c.fetchall()
    close_connection()
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
    close_connection()
    return c.rowcount > 0


def get_card_due_dates():
    """获取所有卡片的到期日信息。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, bank, card_last4, due_date_full FROM cards WHERE due_date_full IS NOT NULL')
    rows = c.fetchall()
    close_connection()
    return rows


def get_all_cards():
    """获取所有卡片列表。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT id, bank, card_last4, holder_name FROM cards ORDER BY bank, card_last4')
    rows = c.fetchall()
    close_connection()
    return rows


def get_unpaid_amount_by_card(card_id):
    """获取某卡最近一期未还款金额。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT total_amount FROM bills WHERE card_id = ?
                 AND total_amount IS NOT NULL AND paid = 0
                 ORDER BY bill_month DESC LIMIT 1''', (card_id,))
    row = c.fetchone()
    close_connection()
    return row[0] if row else None


def get_report_data(period_type='month', period_value=None):
    """获取报表数据。"""
    conn = get_connection()
    c = conn.cursor()

    # card_last4 is in cards table, join to get it
    base_query = '''SELECT b.bank, c.card_last4, c.holder_name, b.bill_month, b.total_amount, b.min_payment
                    FROM bills b LEFT JOIN cards c ON b.card_id = c.id'''

    if period_type == 'month':
        if not period_value:
            period_value = datetime.now().strftime('%Y-%m')
        query = f"{base_query} WHERE b.bill_month = ? AND b.total_amount IS NOT NULL AND b.paid = 0 ORDER BY b.bank"
        params = (period_value,)
    elif period_type == 'quarter':
        year, q = parse_period_value(period_type, period_value)
        start = f"{year}-{(q-1)*3+1:02d}"
        end = f"{year}-{min(q*3, 12):02d}"
        query = f"{base_query} WHERE b.bill_month >= ? AND b.bill_month <= ? AND b.total_amount IS NOT NULL AND b.paid = 0 ORDER BY b.bank"
        params = (start, end)
    elif period_type == 'year':
        year, _ = parse_period_value(period_type, period_value)
        query = f"{base_query} WHERE b.bill_month LIKE ? AND b.total_amount IS NOT NULL AND b.paid = 0 ORDER BY b.bank, b.bill_month"
        params = (f"{year}-%",)
    else:
        raise ValueError(f"Unknown period type: {period_type}")

    c.execute(query, params)
    rows = c.fetchall()
    close_connection()
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

    today = datetime.now().date()
    # Target month range: show bills due in target month + next 2 months for context
    target_start = datetime(year, month, 1).date()
    # Handle year rollover (e.g., Nov -> Jan next year)
    end_month = month + 2
    end_year = year
    if end_month > 12:
        end_month -= 12
        end_year += 1
    target_end = datetime(end_year, end_month, 1).date() - timedelta(days=1)

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
                'card_last4': card_last4 or '',
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
                'card_last4': card_last4 or '',
                'due_date': original_due,
                'amount': amount,
                'is_today': original_due == today,
                'days_until': days_until,
                'is_overdue': False,
            })

    # Overdue first (sorted by most overdue), then upcoming
    # Separate sorting for better performance on large datasets
    overdue_entries.sort(key=lambda e: (e['due_date'], e['bank']))
    calendar_entries.sort(key=lambda e: (e['due_date'], e['bank']))
    all_entries = overdue_entries + calendar_entries
    return all_entries


def get_unpaid_summary():
    """获取未还款总览数据。"""
    conn = get_connection()
    c = conn.cursor()

    # Total unpaid (exclude overpayments/negative amounts)
    c.execute('SELECT COUNT(*), COALESCE(SUM(total_amount), 0) FROM bills WHERE paid = 0 AND total_amount IS NOT NULL AND total_amount > 0')
    count, total = c.fetchone()

    # By card (latest unpaid per card)
    c.execute('''SELECT b.bank, c.card_last4, b.due_date_full, b.total_amount, b.bill_month, b.id, c.holder_name
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
        sql = '''SELECT b.bank, b.bill_month, b.total_amount, b.pay_date, c.card_last4, c.holder_name
                     FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                     WHERE b.paid = 1 AND b.bank = ?'''
        params = [bank]
    else:
        sql = '''SELECT b.bank, b.bill_month, b.total_amount, b.pay_date, c.card_last4, c.holder_name
                     FROM bills b LEFT JOIN cards c ON b.card_id = c.id
                     WHERE b.paid = 1'''
        params = []

    if year:
        sql += ' AND b.bill_month LIKE ?'
        params.append(f'{year}%')
    if month:
        # Use exact match when year is provided to avoid "2026-1" matching "2026-10/11/12"
        if year:
            sql += ' AND b.bill_month = ?'
            params.append(f'{year}-{month.zfill(2)}')
        else:
            # Without year, match any YYYY-MM where MM is zero-padded
            sql += ' AND b.bill_month LIKE ?'
            params.append(f'%-{month.zfill(2)}')

    sql += ' ORDER BY b.bill_month DESC'
    c.execute(sql, params)

    rows = c.fetchall()
    close_connection()
    return rows


def get_spending_by_bank():
    """获取各银行消费统计（用于还款建议）。"""
    conn = get_connection()
    c = conn.cursor()

    # Per bank: total paid, avg monthly, latest unpaid — exclude negative amounts (溢缴款)
    c.execute('''SELECT b.bank,
                        COUNT(CASE WHEN b.paid = 1 AND b.total_amount > 0 THEN 1 END) as paid_count,
                        COALESCE(SUM(CASE WHEN b.paid = 1 AND b.total_amount > 0 THEN b.total_amount ELSE 0 END), 0) as total_paid,
                        AVG(CASE WHEN b.paid = 1 AND b.total_amount > 0 THEN b.total_amount ELSE NULL END) as avg_monthly,
                        MAX(CASE WHEN b.paid = 1 AND b.total_amount > 0 THEN b.bill_month END) as last_paid_month
                 FROM bills b WHERE b.total_amount IS NOT NULL
                 GROUP BY b.bank
                 ORDER BY avg_monthly DESC''')

    rows = c.fetchall()

    result = []
    for bank, paid_count, total_paid, avg_monthly, last_paid_month in rows:
        result.append({
            'bank': bank,
            'paid_count': paid_count,
            'total_paid': total_paid,
            'avg_monthly': round(avg_monthly, 2) if avg_monthly else 0,
            'last_paid_month': last_paid_month,
        })

    close_connection()
    return result


# ── Annual Fees / 年费管理 ──────────────────────────

def get_annual_fees(card_id=None):
    """获取年费记录，可按卡过滤。"""
    conn = get_connection()
    c = conn.cursor()
    if card_id:
        c.execute('''SELECT af.id, af.card_id, c.bank, c.card_last4, c.holder_name,
                            af.amount, af.waive_condition, af.charge_month, af.charge_day,
                            af.is_first_year, af.is_recurring, af.status, af.notes,
                            af.created_at, af.updated_at
                     FROM annual_fees af
                     JOIN cards c ON af.card_id = c.id
                     WHERE af.card_id = ?
                     ORDER BY af.charge_month DESC, af.charge_day DESC''', (card_id,))
    else:
        c.execute('''SELECT af.id, af.card_id, c.bank, c.card_last4, c.holder_name,
                            af.amount, af.waive_condition, af.charge_month, af.charge_day,
                            af.is_first_year, af.is_recurring, af.status, af.notes,
                            af.created_at, af.updated_at
                     FROM annual_fees af
                     JOIN cards c ON af.card_id = c.id
                     ORDER BY af.charge_month DESC, af.charge_day DESC''')
    rows = c.fetchall()
    close_connection()
    return rows


def get_upcoming_annual_fees(days=30):
    """获取即将到期的年费（用于提醒）。"""
    from datetime import datetime, timedelta
    import calendar
    conn = get_connection()
    c = conn.cursor()
    today = datetime.now()
    future = today + timedelta(days=days)
    this_year = today.year
    
    # Build charge dates for this year and next year (for rollover)
    charge_dates = []
    c.execute('''SELECT af.id, af.card_id, c.bank, c.card_last4, c.holder_name,
                        af.amount, af.waive_condition, af.charge_month, af.charge_day,
                        af.is_first_year, af.is_recurring, af.status, af.notes
                 FROM annual_fees af
                 JOIN cards c ON af.card_id = c.id
                 WHERE af.status = 'pending' AND af.is_recurring = 1''')
    all_fees = c.fetchall()
    
    for fee in all_fees:
        fee_id, card_id, bank, card_last4, holder_name, amount, waive_condition, \
            charge_month, charge_day, is_first_year, is_recurring, status, notes = fee
        
        # Try this year first
        try:
            max_day = calendar.monthrange(this_year, charge_month)[1]
            day = min(charge_day, max_day)
            charge_date_this = datetime(this_year, charge_month, day)
            
            # Try next year if this year's date is in the past
            charge_date_next = datetime(this_year + 1, charge_month, day)
            
            if charge_date_this >= today and charge_date_this <= future:
                charge_dates.append((charge_date_this, fee_id, card_id, bank, card_last4, holder_name,
                                   amount, waive_condition, charge_month, charge_day,
                                   is_first_year, is_recurring, status, notes))
            elif charge_date_next >= today and charge_date_next <= future:
                charge_dates.append((charge_date_next, fee_id, card_id, bank, card_last4, holder_name,
                                   amount, waive_condition, charge_month, charge_day,
                                   is_first_year, is_recurring, status, notes))
        except ValueError:
            continue
    
    charge_dates.sort(key=lambda x: x[0])
    
    result = []
    for row in charge_dates:
        result.append(row[1:])  # Exclude the computed date (index 0)
    
    close_connection()
    return result


def create_annual_fee(card_id, amount, waive_condition, charge_month, charge_day,
                      is_first_year, is_recurring, notes=None):
    """创建年费记录。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO annual_fees (card_id, amount, waive_condition, charge_month, charge_day,
                        is_first_year, is_recurring, notes)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
              (card_id, amount, waive_condition, charge_month, charge_day,
               is_first_year, is_recurring, notes))
    conn.commit()
    fee_id = c.lastrowid
    close_connection()
    return fee_id


def add_new_card(bank, card_last4, holder_name):
    """添加新卡片。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('''INSERT INTO cards (bank, card_last4, holder_name)
                 VALUES (?, ?, ?)''', (bank, card_last4, holder_name))
    conn.commit()
    card_id = c.lastrowid
    close_connection()
    return card_id


def update_annual_fee(fee_id, status=None, amount=None, waive_condition=None,
                      charge_month=None, charge_day=None, is_first_year=None,
                      is_recurring=None, notes=None):
    """更新年费记录。"""
    conn = get_connection()
    c = conn.cursor()
    updates = []
    params = []
    if status is not None:
        updates.append('status = ?')
        params.append(status)
    if amount is not None:
        updates.append('amount = ?')
        params.append(amount)
    if waive_condition is not None:
        updates.append('waive_condition = ?')
        params.append(waive_condition)
    if charge_month is not None:
        updates.append('charge_month = ?')
        params.append(charge_month)
    if charge_day is not None:
        updates.append('charge_day = ?')
        params.append(charge_day)
    if is_first_year is not None:
        updates.append('is_first_year = ?')
        params.append(is_first_year)
    if is_recurring is not None:
        updates.append('is_recurring = ?')
        params.append(is_recurring)
    if notes is not None:
        updates.append('notes = ?')
        params.append(notes)
    updates.append("updated_at = datetime('now')")
    params.append(fee_id)
    c.execute(f'''UPDATE annual_fees SET {', '.join(updates)} WHERE id = ?''', params)
    conn.commit()
    affected = c.rowcount
    close_connection()
    return affected > 0


def delete_annual_fee(fee_id):
    """删除年费记录。"""
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM annual_fees WHERE id = ?', (fee_id,))
    conn.commit()
    affected = c.rowcount
    close_connection()
    return affected > 0
