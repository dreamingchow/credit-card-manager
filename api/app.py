"""Flask REST API — 信用卡管理系统后端。"""

import sys
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, make_response
from flask_cors import CORS
import sys
import os

# Add project root to path so we can import src.db
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

# Add health project to path
health_path = Path(__file__).parent.parent.parent / 'health'
if health_path.exists():
    sys.path.insert(0, str(health_path))

from src.db import (
    get_unpaid_summary,
    get_calendar_data,
    get_report_data,
    get_payment_history,
    get_spending_by_bank,
    mark_bill_paid,
    get_connection,
    close_connection,
    get_annual_fees,
    get_upcoming_annual_fees,
    create_annual_fee,
    add_new_card,
    update_annual_fee,
    delete_annual_fee,
    get_all_cards,
)

# Import health database functions (if available)
HEALTH_DB_AVAILABLE = False
_health_db_module = None

try:
    import importlib.util
    health_db_path = '/Users/dreaming/projects/health/db.py'
    spec = importlib.util.spec_from_file_location("health_db", health_db_path)
    if spec and spec.loader:
        _health_db_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_health_db_module)
        HEALTH_DB_AVAILABLE = True
    else:
        print("Health DB: Failed to load module")
except Exception as e:
    print(f"Health DB import failed: {e}")

# Helper to get health DB functions
def _health_func(name):
    if not _health_db_module:
        return None
    return getattr(_health_db_module, name, None)

WEB_DIR = BASE_DIR / 'web' / 'dist'
app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='')
CORS(app)

# 请求结束时清理数据库连接（复用线程本地连接，避免关闭问题）
@app.teardown_appcontext
def teardown_db(exception=None):
    close_connection()


@app.after_request
def add_cache_headers(response):
    if request.path.endswith(('.js', '.css')):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# ── Dashboard / 仪表盘 ──────────────────────────────

@app.route('/api/dashboard')
def api_dashboard():
    """仪表盘数据。"""
    summary = get_unpaid_summary()
    spending = get_spending_by_bank()

    # Format monthly trend with MoM change
    trend = []
    prev_total = None
    for bill_month, total in summary['monthly_trend']:
        entry = {'month': bill_month, 'total': total}
        if prev_total is not None and prev_total > 0:
            change = ((total - prev_total) / prev_total) * 100
            entry['change_pct'] = round(change, 1)
        else:
            entry['change_pct'] = None
        trend.append(entry)
        prev_total = total

    # Format spending by bank (negative avg → 0)
    bank_stats = []
    for s in spending:
        bank_stats.append({
            'bank': s['bank'],
            'avg_monthly': max(0, s['avg_monthly']),
            'paid_count': s['paid_count'],
            'total_paid': s['total_paid'],
        })

    return jsonify({
        'unpaid_count': summary['unpaid_count'],
        'unpaid_total': summary['unpaid_total'],
        'unpaid_cards': [
            {'bank': r[0], 'card_last4': r[1], 'due_date_full': r[2], 'amount': r[3], 'bill_month': r[4], 'bill_id': r[5], 'holder_name': r[6]}
            for r in summary['unpaid_cards']
        ],
        'monthly_trend': trend,
        'bank_stats': bank_stats,
    })


# ── Calendar / 日历 ─────────────────────────────────

@app.route('/api/calendar')
def api_calendar():
    """日历视图数据。"""
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)

    entries = get_calendar_data(year, month)
    return jsonify({
        'entries': [
            {
                'bank': e['bank'],
                'holder_name': e.get('holder_name', ''),
                'card_last4': e['card_last4'],
                'due_date': e['due_date'].strftime('%Y-%m-%d'),
                'day': e['due_date'].day,
                'month': e['due_date'].month,
                'amount': e['amount'],
                'is_today': e['is_today'],
                'days_until': e['days_until'],
                'is_overdue': e.get('is_overdue', False),
            }
            for e in entries
        ]
    })


# ── Report / 报表 ───────────────────────────────────

@app.route('/api/report')
def api_report():
    """报表数据。"""
    period_type = request.args.get('type', 'month')  # month / quarter / year
    period_value = request.args.get('value')  # e.g. '2026-05' or '2026' (year)
    period_q = request.args.get('q', type=int)  # quarter number (1-4), for quarter type

    # For quarter type, if q is provided, pass (year, q) as tuple
    if period_type == 'quarter' and period_q is not None and period_value:
        period_value = f"{period_value}|{period_q}"

    rows = get_report_data(period_type, period_value)

    # Aggregate by bank + card_last4 for detail, and by bank for summary
    card_data = {}  # (bank, card_last4) -> { months, total, min_total }
    bank_data = {}  # bank -> { total, min_total }
    total_all = 0
    min_all = 0

    for bank, card_last4, holder_name, month, amount, min_pay in rows:
        is_overpay = amount < 0
        key = (bank, card_last4)
        if key not in card_data:
            card_data[key] = {'months': {}, 'total': 0, 'min_total': 0, 'holder_name': holder_name or ''}
        if month not in card_data[key]['months']:
            card_data[key]['months'][month] = {'amount': 0, 'min_pay': 0, 'is_overpayment': False}
        card_data[key]['months'][month]['amount'] += amount
        card_data[key]['months'][month]['min_pay'] = (min_pay or 0)
        if is_overpay:
            card_data[key]['months'][month]['is_overpayment'] = True
        if not is_overpay:
            card_data[key]['total'] += amount
            if min_pay:
                card_data[key]['min_total'] += min_pay

        if bank not in bank_data:
            bank_data[bank] = {'total': 0, 'min_total': 0}
        if not is_overpay:
            bank_data[bank]['total'] += amount
            if min_pay:
                bank_data[bank]['min_total'] += min_pay

        if not is_overpay:
            total_all += amount
            if min_pay:
                min_all += min_pay

    # Format card detail rows: bank + holder_name + card_last4 + months
    card_detail = {}  # "bank|||holder_name|||card_label" -> [{ month, amount, min_pay }]
    def sort_key(item):
        bank, card_last4 = item[0]
        return (bank, card_last4 or '')
    for (bank, card_last4), info in sorted(card_data.items(), key=sort_key):
        label = f"****{card_last4}" if card_last4 else '—'
        months_list = []
        for month in sorted(info['months'].keys()):
            entry = info['months'][month]
            months_list.append({
                'month': month,
                'amount': entry['amount'],
                'min_pay': entry['min_pay'],
                'is_overpayment': entry.get('is_overpayment', False),
            })
        card_detail[f"{bank}|||{info.get('holder_name', '') or ''}|||{label}"] = months_list

    # Bank summary (no card number column)
    bank_summary = []
    for bank in sorted(bank_data.keys()):
        info = bank_data[bank]
        bank_summary.append({
            'bank': bank,
            'total': info['total'],
            'min_total': info['min_total'],
        })

    return jsonify({
        'card_detail': card_detail,
        'bank_summary': bank_summary,
        'total': total_all,
        'min_total': min_all,
    })


# ── History / 历史还款 ─────────────────────────────

@app.route('/api/history')
def api_history():
    """历史还款记录。"""
    bank = request.args.get('bank')
    year = request.args.get('year')
    month = request.args.get('month')
    rows = get_payment_history(bank, year, month)

    # Group by bank
    from collections import defaultdict
    by_bank = defaultdict(list)
    for row in rows:
        by_bank[row[0]].append({
            'bank': row[0],
            'bill_month': row[1],
            'amount': row[2],
            'pay_date': row[3],
            'card_last4': row[4],
            'holder_name': row[5] or '',
        })

    result = {}
    grand_total = 0
    for bank_name in sorted(by_bank.keys()):
        records = by_bank[bank_name]
        bank_total = sum(r['amount'] for r in records if r['amount'] and r['amount'] > 0)
        grand_total += bank_total
        result[bank_name] = {
            'records': records,
            'count': len(records),
            'total': bank_total,
        }

    return jsonify({
        'by_bank': result,
        'grand_total': grand_total,
    })


# ── Suggestions / 建议 ─────────────────────────────

@app.route('/api/suggestions')
def api_suggestions():
    """还款建议数据。"""
    spending = get_spending_by_bank()
    summary = get_unpaid_summary()

    # Calculate overall avg
    avg_totals = [s['avg_monthly'] for s in spending if s['avg_monthly'] > 0]
    overall_avg = sum(avg_totals) / len(avg_totals) if avg_totals else 0

    # Format bank suggestions with unpaid info (batch query instead of N+1)
    # Batch query all unpaid bills (N+1 query fixed)
    # Only positive amounts (overpayments/negative = 溢缴款, not owed)
    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT bank, bill_month, total_amount FROM bills
                 WHERE paid = 0 AND total_amount IS NOT NULL AND total_amount > 0
                 ORDER BY bank, bill_month DESC''')
    all_unpaid = c.fetchall()
    # Don't close here - teardown_appcontext handles it

    # Group unpaid bills by bank
    unpaid_by_bank = {}
    for bank, bill_month, amount in all_unpaid:
        if bank not in unpaid_by_bank:
            unpaid_by_bank[bank] = []
        unpaid_by_bank[bank].append({'month': bill_month, 'amount': amount})

    # Also collect overpayments separately for display
    c.execute('''SELECT bank, bill_month, total_amount FROM bills
                 WHERE paid = 0 AND total_amount < 0
                 ORDER BY bank, bill_month DESC''')
    all_overpay = c.fetchall()
    overpay_by_bank = {}
    for bank, bill_month, amount in all_overpay:
        if bank not in overpay_by_bank:
            overpay_by_bank[bank] = []
        overpay_by_bank[bank].append({'month': bill_month, 'amount': amount})

    bank_suggestions = []
    for s in spending:
        bank_unpaid = unpaid_by_bank.get(s['bank'], [])
        bank_overpay = overpay_by_bank.get(s['bank'], [])
        # Combine unpaid + overpayments for display (frontend handles overpayment display)
        combined = bank_unpaid + bank_overpay
        bank_suggestions.append({
            'bank': s['bank'],
            'avg_monthly': max(0, s['avg_monthly']),
            'paid_count': s['paid_count'],
            'total_paid': s['total_paid'],
            'unpaid': combined,
            'has_unpaid': len(bank_unpaid) > 0,
        })

    return jsonify({
        'overall_avg': round(overall_avg, 2),
        'unpaid_count': summary['unpaid_count'],
        'unpaid_total': summary['unpaid_total'],
        'banks': bank_suggestions,
    })


# ── Mark Paid / 标记还款 ───────────────────────────

@app.route('/api/pay', methods=['POST'])
def api_mark_paid():
    """标记账单已还。"""
    data = request.get_json()
    bank = data.get('bank')
    bill_month = data.get('bill_month')
    bill_id = data.get('bill_id')  # optional — if omitted, marks ALL unpaid bills for this bank+month

    if not bank or not bill_month:
        return jsonify({'error': '缺少参数'}), 400

    conn = get_connection()
    c = conn.cursor()

    from datetime import datetime
    pay_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    if bill_id:
        # Mark a specific bill
        c.execute('''SELECT total_amount FROM bills WHERE id = ? AND paid = 0''', (bill_id,))
        row = c.fetchone()
        if not row:
            conn.close()
            return jsonify({'error': f'未找到 bill_id={bill_id} 的未还款账单'}), 404
        amount = row[0]
        c.execute('UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?', (pay_date, bill_id))
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'bank': bank,
            'bill_month': bill_month,
            'bill_id': bill_id,
            'amount': amount,
            'pay_date': pay_date,
        })
    else:
        # Legacy mode: mark ALL unpaid bills for this bank+month
        c.execute('''SELECT id, total_amount FROM bills
                     WHERE bank = ? AND bill_month = ? AND paid = 0
                     ORDER BY id''', (bank, bill_month))
        rows = c.fetchall()
        if not rows:
            conn.close()
            return jsonify({'error': f'未找到 {bank} {bill_month} 的未还款账单'}), 404
        total = 0
        for bid, amt in rows:
            c.execute('UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?', (pay_date, bid))
            total += amt
        conn.commit()
        conn.close()
        return jsonify({
            'success': True,
            'bank': bank,
            'bill_month': bill_month,
            'count': len(rows),
            'amount': total,
            'pay_date': pay_date,
        })


# ── Cards / 卡片列表 ──────────────────────────────

@app.route('/api/cards')
def api_cards():
    """获取所有卡片列表。"""
    rows = get_all_cards()
    return jsonify({
        'cards': [
            {
                'id': r[0],
                'bank': r[1],
                'card_last4': r[2],
                'holder_name': r[3] or '',
            }
            for r in rows
        ]
    })


# ── Annual Fees / 年费管理 ──────────────────────────

@app.route('/api/annual_fees')
def api_annual_fees():
    """获取年费记录，支持按 card_id 过滤。"""
    card_id = request.args.get('card_id', type=int)
    rows = get_annual_fees(card_id)
    return jsonify({
        'fees': [
            {
                'id': r[0],
                'card_id': r[1],
                'bank': r[2],
                'card_last4': r[3],
                'holder_name': r[4] or '',
                'amount': r[5],
                'waive_condition': r[6],
                'charge_month': r[7],
                'charge_day': r[8],
                'is_first_year': bool(r[9]),
                'is_recurring': bool(r[10]),
                'status': r[11],
                'notes': r[12],
                'created_at': r[13],
                'updated_at': r[14],
            }
            for r in rows
        ]
    })


@app.route('/api/annual_fees/upcoming')
def api_annual_fees_upcoming():
    """获取即将到期的年费（用于提醒）。"""
    days = request.args.get('days', 30, type=int)
    rows = get_upcoming_annual_fees(days)
    return jsonify({
        'fees': [
            {
                'id': r[0],
                'card_id': r[1],
                'bank': r[2],
                'card_last4': r[3],
                'holder_name': r[4] or '',
                'amount': r[5],
                'waive_condition': r[6],
                'charge_month': r[7],
                'charge_day': r[8],
                'is_first_year': bool(r[9]),
                'is_recurring': bool(r[10]),
                'status': r[11],
                'notes': r[12],
            }
            for r in rows
        ]
    })


@app.route('/api/annual_fees', methods=['POST'])
def api_create_annual_fee():
    """创建年费记录。"""
    data = request.get_json()
    card_id = data.get('card_id')
    amount = data.get('amount')
    waive_condition = data.get('waive_condition')
    charge_month = data.get('charge_month')
    charge_day = data.get('charge_day')
    is_first_year = data.get('is_first_year', False)
    is_recurring = data.get('is_recurring', True)
    notes = data.get('notes')
    new_card = data.get('new_card')  # 新卡信息

    # 校验：card_id 可以是 null（新卡时前端会设为 null），但 amount/月/日必须有
    if amount is None or not charge_month or not charge_day:
        return jsonify({'error': '缺少必要参数'}), 400

    # 如果是新卡，先创建
    if new_card:
        card_id = add_new_card(new_card['bank'], new_card.get('card_last4'), new_card.get('holder_name'))

    fee_id = create_annual_fee(card_id, amount, waive_condition, charge_month, charge_day,
                               1 if is_first_year else 0, 1 if is_recurring else 0, notes)
    return jsonify({'success': True, 'id': fee_id}), 201


@app.route('/api/annual_fees/<int:fee_id>', methods=['PUT'])
def api_update_annual_fee(fee_id):
    """更新年费记录。"""
    data = request.get_json()
    result = update_annual_fee(fee_id,
                               status=data.get('status'),
                               amount=data.get('amount'),
                               waive_condition=data.get('waive_condition'),
                               charge_month=data.get('charge_month'),
                               charge_day=data.get('charge_day'),
                               is_first_year=data.get('is_first_year'),
                               is_recurring=data.get('is_recurring'),
                               notes=data.get('notes'))
    if result:
        return jsonify({'success': True})
    return jsonify({'error': '记录不存在'}), 404


@app.route('/api/annual_fees/<int:fee_id>', methods=['DELETE'])
def api_delete_annual_fee(fee_id):
    """删除年费记录。"""
    result = delete_annual_fee(fee_id)
    if result:
        return jsonify({'success': True})
    return jsonify({'error': '记录不存在'}), 404


# ── Health check ────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(str(WEB_DIR), 'index.html')


@app.after_request
def spa_fallback(response):
    # SPA: if the requested path is not an API route and file doesn't exist, serve index.html
    if (response.status_code == 404 
        and not request.path.startswith('/api/')
        and not request.path.startswith('/favicon')
        and not request.path.startswith('/icons')):
        try:
            return make_response(send_from_directory(str(WEB_DIR), 'index.html'), 200)
        except Exception:
            pass
    return response


@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'cards': 13, 'bills': 47, 'health_db': HEALTH_DB_AVAILABLE})


@app.route('/api/health/users')
def api_health_users():
    """获取所有用户列表."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    try:
        get_all_users = _health_func('get_all_users')
        if not get_all_users:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        users = get_all_users()
        return jsonify({
            'users': users,
            'count': len(users),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/users', methods=['POST'])
def api_health_create_user():
    """创建新用户."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    data = request.get_json()
    try:
        create_user = _health_func('create_user')
        if not create_user:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        if not data.get('name'):
            return jsonify({'error': '缺少用户名'}), 400
        
        user_id = create_user(
            name=data['name'],
            phone=data.get('phone'),
            birthdate=data.get('birthdate'),
            gender=data.get('gender', 0),
            notes=data.get('notes'),
        )
        return jsonify({'success': True, 'user_id': user_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/blood-pressure')
def api_blood_pressure():
    """获取血压记录数据（从数据库读取，支持按用户筛选）."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    try:
        get_all_users = _health_func('get_all_users')
        get_bp = _health_func('get_blood_pressure')
        if not get_all_users or not get_bp:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        # 获取查询参数
        user_id = request.args.get('user_id', type=int)
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = request.args.get('limit', 100, type=int)
        
        # 如果没有指定用户，默认使用第一个用户
        if not user_id and HEALTH_DB_AVAILABLE:
            users = get_all_users()
            if users:
                user_id = users[0]['id']
        
        records = get_bp(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        
        # 转换为前端兼容格式
        result = []
        for r in records:
            result.append({
                'id': r['id'],
                'user_id': r['user_id'],
                'user_name': r['user_name'],
                'date': r['date'],
                'time': r['time'],
                'period': r['period'],
                'systolic': r['systolic'],
                'diastolic': r['diastolic'],
                'pulse': r['pulse_rate'],
                'status': r.get('medication_status') or r.get('notes', ''),
            })
        
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/health/blood-pressure', methods=['POST'])
def api_blood_pressure_create():
    """创建血压记录."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    data = request.get_json()
    try:
        create_bp = _health_func('create_blood_pressure')
        if not create_bp:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        required = ['user_id', 'date', 'period', 'systolic', 'diastolic']
        for field in required:
            if field not in data:
                return jsonify({'error': f'缺少必要字段: {field}'}), 400
        
        record_id = create_bp(
            user_id=data['user_id'],
            date=data['date'],
            time=data.get('time'),
            period=data['period'],
            systolic=data['systolic'],
            diastolic=data['diastolic'],
            pulse_rate=data.get('pulse_rate'),
            notes=data.get('notes'),
            medication_status=data.get('medication_status'),
        )
        
        return jsonify({'success': True, 'record_id': record_id}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/blood-pressure/<int:record_id>', methods=['DELETE'])
def api_blood_pressure_delete(record_id):
    """删除血压记录."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    try:
        delete_bp = _health_func('delete_blood_pressure')
        if delete_bp:
            delete_bp(record_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/blood-pressure/summary')
def api_blood_pressure_summary():
    """获取血压统计摘要."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    try:
        get_summary = _health_func('get_blood_pressure_summary')
        if not get_summary:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400
        
        summary = get_summary(user_id)
        
        # 计算百分比
        if summary['total_records'] > 0:
            summary['high_bp_rate'] = round(
                summary['high_bp_count'] / summary['total_records'] * 100, 1
            )
            summary['low_bp_rate'] = round(
                summary['low_bp_count'] / summary['total_records'] * 100, 1
            )
        
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/health/blood-pressure/trend')
def api_blood_pressure_trend():
    """获取血压趋势数据."""
    if not HEALTH_DB_AVAILABLE:
        return jsonify({'error': '健康数据库不可用'}), 500
    try:
        get_trend = _health_func('get_blood_pressure_trend')
        if not get_trend:
            return jsonify({'error': '健康数据库函数不可用'}), 500
        user_id = request.args.get('user_id', type=int)
        if not user_id:
            return jsonify({'error': '缺少 user_id'}), 400
        
        days = request.args.get('days', 30, type=int)
        trend = get_trend(user_id, days)
        
        return jsonify({
            'trend': trend,
            'days': days,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # 从 config.yaml 读取监听地址和端口
    import yaml
    cfg_path = Path(__file__).parent.parent / 'config.yaml'
    try:
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f)
        svr = cfg.get('server', {})
        host = svr.get('host', '127.0.0.1')
        port = svr.get('port', 5001)
    except Exception:
        host = '127.0.0.1'
        port = 5001
    # 禁用 reloader 避免 macOS SIGKILL (exit code 137)
    app.run(host=host, port=port, debug=True, use_reloader=False)
