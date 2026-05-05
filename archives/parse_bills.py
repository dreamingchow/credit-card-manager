#!/usr/bin/env python3
"""
信用卡账单解析器 v2 - 使用 BeautifulSoup 渲染 HTML。

比正则更可靠，能处理各种银行复杂的 HTML 结构。

用法:
    python parse_bills_v2.py              # 解析所有未解析的账单
"""

import os
import re
import sys
import sqlite3
import email
from email.policy import default
from pathlib import Path
from datetime import datetime
from bs4 import BeautifulSoup

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


BILLS_DIR = Path(__file__).parent / "bills"
DB_PATH = Path(__file__).parent / "db" / "cards.db"


def init_db():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bank TEXT NOT NULL,
        card_last4 TEXT,
        stmt_day INTEGER,
        due_day INTEGER,
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
        source_file TEXT,
        raw_data TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS processed_files (
        filename TEXT PRIMARY KEY,
        parsed_at TEXT DEFAULT (datetime('now'))
    )''')

    conn.commit()
    return conn


def decode_email(filepath):
    """解码邮件，返回纯文本"""
    with open(filepath, 'rb') as f:
        raw = f.read()

    msg = email.message_from_bytes(raw, policy=default)
    html_raw = ""

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or 'utf-8'
                    try:
                        html_raw = payload.decode(charset, errors='replace')
                    except:
                        html_raw = payload.decode('utf-8', errors='replace')
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload and isinstance(payload, bytes):
            charset = msg.get_content_charset() or 'utf-8'
            try:
                html_raw = payload.decode(charset, errors='replace')
            except:
                html_raw = payload.decode('utf-8', errors='replace')
        elif payload and isinstance(payload, str):
            html_raw = payload

    if not html_raw:
        for enc in ['gbk', 'utf-8', 'gb2312']:
            try:
                html_raw = raw.decode(enc, errors='replace')
                if '\ufffd' not in html_raw:
                    break
            except:
                continue

    if not html_raw:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            html_raw = f.read()

    # 用 BeautifulSoup 渲染 HTML → 提取纯文本
    soup = BeautifulSoup(html_raw, 'lxml')
    
    # 获取所有文本，清理空白
    text = soup.get_text(separator=' ', strip=True)
    
    # 也保留一些 HTML 结构用于查找特定模式
    # 去除 script/style 内容
    for tag in soup(['script', 'style']):
        tag.decompose()
    
    return text, soup


def extract_amount(text):
    """从文本中提取应还金额"""
    # 多种模式匹配（精确标签优先）
    patterns = [
        r'本期应还[额]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'应还[额]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'New\s+Balance\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'本期账单金额\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'账单金额\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'应还款\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'Credit\s+Balance\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'本期应还款总额\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'本期应还金额\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'本期账单金额\s*[¥￥]?\s*([\d,]+\.\d{2})',
        # 建设银行特殊格式: "New Balance 人民币 （CNY） 10.96 10.97"
        # 匹配 "New Balance ... CNY) ..." 后的两个数字，取第二个（本期）
        r'New\s+Balance.{0,30}人民币.{0,15}CNY.{0,15}[\d,]+\.\d{2}\s+([\d,]+\.\d{2})',
        r'New\s+Balance.{0,30}CNY.{0,15}[\d,]+\.\d{2}\s+([\d,]+\.\d{2})',
        r'本期全部应还款额.{0,50}人民币.{0,15}CNY.{0,15}[\d,]+\.\d{2}\s+([\d,]+\.\d{2})',
        r'本期全部应还款额.{0,50}([\d,]+\.\d{2})',
    ]
    
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except:
                pass
    
    # 兜底：找合理的总金额范围（5-50000），排除交易明细中的单笔
    # 关键：排除"额度"、"Credit Limit"附近的金额
    lines = text.split('\n')
    for line in lines:
        # 跳过包含"额度"的行（包括可用额度、信用额度等）
        if any(kw in line for kw in ['额度', 'Credit Limit', 'Available Limit', 'Cash Advance']):
            continue
        m = re.search(r'[¥￥]?\s*([\d,]+\.\d{2})', line)
        if m:
            try:
                val = float(m.group(1).replace(',', ''))
                if 5 <= val <= 50000:
                    return val
            except:
                pass
    
    # 最后一招：找最大的合理金额（排除额度）
    amounts = re.findall(r'[¥￥]?\s*([\d,]+\.\d{2})', text)
    parsed = []
    for a in amounts:
        try:
            val = float(a.replace(',', ''))
            if 5 <= val <= 50000:
                parsed.append(val)
        except:
            pass
    
    if parsed:
        return max(parsed)
    
    return None


def extract_min_payment(text):
    """提取最低还款额"""
    patterns = [
        r'最低应还[额]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'最低还款[额]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'Min\.\w+\s*[¥￥]?\s*([\d,]+\.\d{2})',
        r'最低[额]?\s*[¥￥]?\s*([\d,]+\.\d{2})',
    ]
    
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except:
                pass
    
    return None


def extract_due_day(text):
    """提取还款日（每月几号）"""
    patterns = [
        r'最后还款[日]?\s*(?:\(Payment\s+Due\s+Date\))?\s*(\d{2}月\d{1,2}日)',
        r'到期还款[日]?\s*(?:\(Payment\s+Due\s+Date\))?\s*(\d{2}月\d{1,2}日)',
        r'还款日[:：]\s*(\d{1,2})',
    ]
    
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            date_str = m.group(1)
            if '月' in date_str and '日' in date_str:
                dm = re.search(r'(\d{1,2})月(\d{1,2})日', date_str)
                if dm:
                    return int(dm.group(2))
            else:
                try:
                    return int(m.group(1))
                except:
                    pass
    
    # 兜底：查找 "还款" + 日期模式
    m = re.search(r'还款.*?(\d{2}月\d{1,2}日)', text)
    if m:
        dm = re.search(r'(\d{1,2})月(\d{1,2})日', m.group(1))
        if dm:
            return int(dm.group(2))
    
    return None


def extract_card_last4(text, soup):
    """提取卡号后4位"""
    # 方法1: 查找 "****NNNN" 模式（最可靠）
    m = re.search(r'\*{4,}(\d{4})', text)
    if m:
        val = int(m.group(1))
        # 排除年份（2024-2099）
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法2: "卡号" + 4位数字，但排除年份
    m = re.search(r'卡号.{0,150}(\d{4})', text)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法3: "Card Number" + 4位数字，排除年份
    m = re.search(r'Card.{0,150}(\d{4})', text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法4: 查找包含 "card" 或 "卡号" 的表格行
    if soup:
        for td in soup.find_all('td'):
            td_text = td.get_text(strip=True).lower()
            if 'card' in td_text or '卡号' in td_text:
                # 看相邻的 TD 是否有数字
                next_td = td.find_next_sibling('td')
                if next_td:
                    next_text = next_td.get_text(strip=True)
                    dm = re.search(r'(\d{4})', next_text)
                    if dm:
                        val = int(dm.group(1))
                        if not (2020 <= val <= 2099):
                            return dm.group(1)
    
    return None


def extract_month_from_filename(filename):
    """从文件名提取月份"""
    stem = Path(filename).stem
    m = re.search(r'(\d{4})年(\d{1,2})月', stem)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r'(\d{4})[-](\d{1,2})', stem)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return None


def extract_bank_from_filename(filename):
    """从文件名提取银行名"""
    parts = Path(filename).stem.split('_', 1)
    if len(parts) >= 2:
        return parts[1].split('_', 1)[0]
    return None


def extract_from_pdf(filepath):
    """从 PDF 账单中提取数据"""
    if not HAS_PDFPLUMBER:
        return None

    info = {}
    full_text = ""
    
    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
    except Exception as e:
        print(f"  ✗ PDF 解析失败: {e}")
        return None

    if not full_text.strip():
        return None

    # 卡号: "4096 7031 **** 9440"
    m = re.search(r'\*{4}\s*(\d{4})', full_text)
    if m:
        info['card_last4'] = m.group(1)

    # 应还金额: "3,508.93" 是第三行的第一个数字（在两个日期之后）
    # 结构: "到期还款日 账单日 本期人民币欠款总计\n2026-04-30 2026-04-10 3,508.93"
    m = re.search(r'本期人民币欠款总计.{0,200}(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+([\d,]+\.\d{2})', full_text, re.DOTALL)
    if m:
        try:
            info['total_amount'] = float(m.group(3).replace(',', ''))
        except:
            pass

    # 还款日: "到期还款日" + date (跨多行，用 DOTALL)
    # 结构: "到期还款日...2026-04-30 2026-04-10" — 第一个日期是还款日
    # 用非贪婪匹配 + 更精确的日期模式
    m = re.search(r'到期还款日.+?(\d{4}-\d{2}-\d{2})', full_text, re.DOTALL)
    if m:
        info['due_date'] = m.group(1)
        dm = re.search(r'(\d{2})-(\d{2})$', m.group(1))
        if dm:
            info['due_day'] = int(dm.group(2))

    # 如果还款日没找到，从 "本期人民币欠款总计" 行提取
    if not info.get('due_day'):
        m = re.search(r'本期人民币欠款总计.+?(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})', full_text, re.DOTALL)
        if m:
            info['due_date'] = m.group(1)  # 第一个日期是还款日
            info['due_day'] = int(m.group(1).split('-')[2])

    return info


def process_file(conn, filepath):
    """解析单个账单文件"""
    filename = filepath.name
    bank = extract_bank_from_filename(filename)
    month = extract_month_from_filename(filename)

    if not bank:
        print(f"  ⚠️  无法识别银行: {filename}")
        return None

    if not month:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        m = re.search(r'(\d{4})年(\d{1,2})月', content)
        if m:
            month = f"{m.group(1)}-{int(m.group(2)):02d}"
        else:
            month = datetime.now().strftime('%Y-%m')

    # Try PDF first (for banks like BOC that send PDF attachments)
    pdf_path = str(filepath).replace('.html', '.pdf')
    if os.path.exists(pdf_path):
        pdf_info = extract_from_pdf(pdf_path)
        if pdf_info and (pdf_info.get('card_last4') or pdf_info.get('total_amount')):
            info = pdf_info
            print(f"  ✓ PDF解析 {bank} {month}")
            # Skip HTML parsing for PDF documents
            return _save_and_report(conn, bank, month, info, filename)

    # Decode email and extract text
    text, soup = decode_email(filepath)

    # Extract data using BeautifulSoup + regex
    info = {
        'card_last4': extract_card_last4(text, soup),
        'total_amount': extract_amount(text),
        'min_payment': extract_min_payment(text),
        'due_day': extract_due_day(text),
    }

    return _save_and_report(conn, bank, month, info, filename)


def _save_and_report(conn, bank, month, info, filename):
    """保存解析结果到数据库并输出"""

    # Upsert card info
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO cards (bank, card_last4, stmt_day, due_day)
                 VALUES (?, ?, ?, ?)''',
              (bank, info.get('card_last4'), None, info.get('due_day')))

    # Update card if we have more data
    c.execute('''SELECT id FROM cards WHERE bank = ?''', (bank,))
    row = c.fetchone()
    if row:
        card_id = row[0]
        updates = []
        params = []
        if info.get('card_last4'):
            updates.append('card_last4 = ?')
            params.append(info['card_last4'])
        if info.get('due_day'):
            updates.append('due_day = ?')
            params.append(info['due_day'])

        if updates:
            params.extend([bank, card_id])
            c.execute(f'''UPDATE cards SET {', '.join(updates)}, updated_at = datetime('now')
                         WHERE bank = ? AND id = ?''', params)

    # Insert bill record
    c.execute('''INSERT INTO bills (card_id, bank, bill_month, total_amount, min_payment,
                 due_date, source_file) VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (row[0] if row else None, bank, month,
               info.get('total_amount'), info.get('min_payment'),
               None, filename))

    # Mark as processed
    c.execute('''INSERT OR IGNORE INTO processed_files (filename) VALUES (?)''', (filename,))

    conn.commit()

    # Print summary
    parts = [f"{bank} {month}"]
    if info.get('card_last4'):
        parts.append(f"****{info['card_last4']}")
    if info.get('total_amount'):
        parts.append(f"¥{info['total_amount']:,.2f}")
    if info.get('min_payment'):
        parts.append(f"最低¥{info['min_payment']:,.2f}")
    if info.get('due_day'):
        parts.append(f"还款日{info['due_day']}号")

    print(f"  ✓ {' | '.join(parts)}")
    return info


def main():
    conn = init_db()

    # Find files to process
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        if idx + 1 < len(sys.argv):
            target = Path(sys.argv[idx + 1])
            files = [target] if target.exists() else []
        else:
            print("用法: python parse_bills_v2.py --file <path>")
            return
    else:
        c = conn.cursor()
        c.execute('SELECT filename FROM processed_files')
        processed = set(row[0] for row in c.fetchall())

        files = [f for f in BILLS_DIR.glob("*.html") if f.name not in processed]
        files.sort()

    if not files:
        print("没有需要解析的账单文件")
        conn.close()
        return

    print(f"开始解析 {len(files)} 个账单文件...\n")

    parsed = 0
    skipped = 0

    for filepath in files:
        result = process_file(conn, filepath)
        if result:
            parsed += 1
        else:
            skipped += 1

    conn.close()

    print(f"\n{'='*50}")
    print(f"  解析完成:")
    print(f"  ✅ 成功: {parsed}")
    print(f"  ⏭️  跳过: {skipped}")
    print(f"{'='*50}")


if __name__ == '__main__':
    main()
