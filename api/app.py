"""Flask REST API — 信用卡管理系统后端。"""

import sys
import os
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, make_response
from flask_cors import CORS

# Add project root to path so we can import src.db
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.db import (
    get_unpaid_summary,
    get_calendar_data,
    get_report_data,
    get_payment_history,
    get_spending_by_bank,
    mark_bill_paid,
    get_connection,
)

WEB_DIR = BASE_DIR / 'web' / 'dist'
app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path='')
CORS(app)


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
            {'bank': r[0], 'card_last4': r[1], 'due_date_full': r[2], 'amount': r[3], 'bill_month': r[4]}
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
                'card_last4': e['card_last4'],
                'due_date': e['due_date'].strftime('%Y-%m-%d'),
                'day': e['due_date'].day,
                'month': e['due_date'].month,
                'amount': e['amount'],
                'is_today': e['is_today'],
                'days_until': e['days_until'],
            }
            for e in entries
        ]
    })


# ── Report / 报表 ───────────────────────────────────

@app.route('/api/report')
def api_report():
    """报表数据。"""
    period_type = request.args.get('type', 'month')  # month / quarter / year
    period_value = request.args.get('value')  # e.g. '2026-05' or '1' (Q) or '2026'

    rows = get_report_data(period_type, period_value)

    # Aggregate by bank
    bank_data = {}
    total_all = 0
    min_all = 0

    for bank, card_last4, month, amount, min_pay in rows:
        if bank not in bank_data:
            bank_data[bank] = {'cards': set(), 'months': {}, 'total': 0, 'min_total': 0}
        bank_data[bank]['cards'].add(card_last4)
        if month not in bank_data[bank]['months']:
            bank_data[bank]['months'][month] = {'amount': 0, 'min_pay': 0}
        bank_data[bank]['months'][month]['amount'] += amount
        bank_data[bank]['months'][month]['min_pay'] = (min_pay or 0)
        bank_data[bank]['total'] += amount
        if min_pay:
            bank_data[bank]['min_total'] += min_pay
        total_all += amount
        if min_pay:
            min_all += min_pay

    # Format months as sorted list
    formatted_months = {}
    for bank, info in bank_data.items():
        formatted_months[bank] = []
        for month in sorted(info['months'].keys()):
            entry = info['months'][month]
            formatted_months[bank].append({
                'month': month,
                'amount': entry['amount'],
                'min_pay': entry['min_pay'],
            })

    # Bank summary
    bank_summary = []
    for bank in sorted(bank_data.keys()):
        info = bank_data[bank]
        cards_str = ', '.join(f"****{c}" for c in info['cards'] if c) or '—'
        bank_summary.append({
            'bank': bank,
            'total': info['total'],
            'min_total': info['min_total'],
            'cards': cards_str,
        })

    return jsonify({
        'bank_months': formatted_months,
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

    # Format bank suggestions with unpaid info
    from src.db import get_connection
    bank_suggestions = []
    for s in spending:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''SELECT bill_month, total_amount FROM bills
                     WHERE bank = ? AND paid = 0 AND total_amount IS NOT NULL
                     ORDER BY bill_month DESC''', (s['bank'],))
        unpaid = c.fetchall()
        conn.close()

        bank_suggestions.append({
            'bank': s['bank'],
            'avg_monthly': max(0, s['avg_monthly']),
            'paid_count': s['paid_count'],
            'total_paid': s['total_paid'],
            'unpaid': [{'month': r[0], 'amount': r[1]} for r in unpaid],
            'has_unpaid': len(unpaid) > 0,
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

    if not bank or not bill_month:
        return jsonify({'error': '缺少参数'}), 400

    conn = get_connection()
    c = conn.cursor()
    c.execute('''SELECT id, total_amount FROM bills
                 WHERE bank = ? AND bill_month = ? AND paid = 0
                 ORDER BY bill_month DESC LIMIT 1''', (bank, bill_month))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({'error': f'未找到 {bank} {bill_month} 的未还款账单'}), 404

    bill_id, amount = row
    from datetime import datetime
    pay_date = datetime.now().strftime('%Y-%m-%d %H:%M')
    c.execute('UPDATE bills SET paid = 1, pay_date = ? WHERE id = ?', (pay_date, bill_id))
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'bank': bank,
        'bill_month': bill_month,
        'amount': amount,
        'pay_date': pay_date,
    })


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
    return jsonify({'status': 'ok', 'cards': 13, 'bills': 47})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
