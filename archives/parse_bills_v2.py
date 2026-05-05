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
        for enc in ['gbk', 'utf-8', 'gb2312', 'gb18030']:
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
    
    return text, soup, html_raw  # also return raw HTML for due date extraction


def extract_amount(text, soup=None):
    """从文本中提取应还金额
    
    优先使用 "本期余额"（上海银行格式），其中 + 表示欠、- 表示溢缴款。
    如果没有 "本期余额"，则回退到通用模式。
    """
    # === 上海银行特殊处理: "本期余额" + 数字+/- ===
    # 在 BeautifulSoup 提取的纯文本中格式为: "本期余额 9.65+"
    m = re.search(r'本期余额\s+([\d,]+\.\d{2})\+', text)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except:
            pass
    
    # 如果找到"本期余额"但后面是负号（溢缴款），应还为0
    m = re.search(r'本期余额\s+([\d,]+\.\d{2})-', text)
    if m:
        return 0.0
    
    # === 通用模式: 本期应还/应还金额等 ===
    # 优先级：精确的"本期"关键词 > 通用应还 > New Balance > 兜底
    patterns = [
        # 精确匹配"本期应还"相关（最高优先级）
        r'本期应还款总额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'本期应还[额]?\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'本期应还金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'本期账单金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'账单金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'应还款\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'应还[额]?\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        # CNY 前缀（中信银行等格式）
        r'本期应还款总额\s*CNY\s*(-?[\d,]+\.\d{2})',
        r'本期最低还款额\s*CNY\s*(-?[\d,]+\.\d{2})',
        # New Balance 可能对应上期余额或本期余额，需要上下文判断
        r'New\s+Balance\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        r'Credit\s+Balance\s*(?:CNY|人民币)?\s*(-?[\d,]+\.\d{2})',
        # 建设银行特殊格式: "New Balance 人民币 （CNY） 10.96 10.97"
        r'New\s+Balance.{0,30}人民币.{0,15}CNY.{0,15}-?[\d,]+\.\d{2}\s+(-?[\d,]+\.\d{2})',
        r'New\s+Balance.{0,30}CNY.{0,15}-?[\d,]+\.\d{2}\s+(-?[\d,]+\.\d{2})',
        r'本期全部应还款额.{0,50}人民币.{0,15}CNY.{0,15}-?[\d,]+\.\d{2}\s+(-?[\d,]+\.\d{2})',
        r'本期全部应还款额.{0,50}(-?[\d,]+\.\d{2})',
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
        r'最低应还[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.\d{2})',
        r'最低还款[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.\d{2})',
        r'Min\. Payment\s*(?:CNY|人民币)?\s*([\d,]+\.\d{2})',
        r'最低还款额\s*CNY\s*([\d,]+\.\d{2})',
        r'最低[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.\d{2})',
    ]
    
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except:
                pass
    
    return None


def extract_due_info(text, html_raw=None, soup=None):
    """提取还款日信息
    
    Returns dict with:
      - due_day: 每月几号（固定还款日的银行）
      - due_date_full: 完整日期字符串（如 '2026/05/07'，非固定还款日的银行）
    """
    result = {'due_day': None, 'due_date_full': None}
    
    # === 优先使用 HTML 表格结构提取（最可靠）===
    # 光大银行等格式：td 中依次包含 "到期还款日Payment Due Date", "信用额度Credit Limit",
    #                   "本期余额RMB Statement Balance", "最低应还额...", 
    #                   "2026/01/18"(账单日), "2026/02/06"(到期还款日)
    if soup:
        tds = soup.find_all('td')
        for i, td in enumerate(tds):
            t = td.get_text(strip=True)
            if 'Due Date' in t or '到期还款日' in t or '最后还款日' in t:
                # 找到表头 td，往后数，跳过所有非日期的 td，找到两个 YYYY/MM/DD
                dates = []
                for j in range(i, min(i + 10, len(tds))):
                    dt = tds[j].get_text(strip=True)
                    if re.match(r'\d{4}/\d{2}/\d{2}$', dt):
                        dates.append(dt)
                    if len(dates) == 2:
                        break
                if len(dates) >= 2:
                    # dates[0] = 账单日, dates[1] = 到期还款日
                    result['due_date_full'] = dates[1].replace('/', '-')
                    parts = dates[1].split('/')
                    result['due_day'] = int(parts[2])
                elif len(dates) == 1:
                    # 只找到账单日，尝试找 "还款日" 后的下一个日期
                    result['due_date_full'] = dates[0].replace('/', '-')
                    parts = dates[0].split('/')
                    result['due_day'] = int(parts[2])
                break
    
    # === 纯文本正则提取（兼容其他银行）===
    if not result['due_date_full']:
        # YYYY/MM/DD or YYYY-MM-DD 格式 - 放宽匹配范围到 150
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result
        
        # 中文日期格式: "2026年04月30日"
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result
        
        # 招商银行特殊格式: "最后还款日(Payment Due Date) 05月03日"
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{1,2})月(\d{1,2})日', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            result['due_day'] = day
            year_m = re.search(r'(\d{4})年', text[:500])
            if year_m:
                result['due_date_full'] = f"{year_m.group(1)}-{month:02d}-{day:02d}"
            return result
        
        # 兜底：从"还款日"附近提取第一个 YYYY/MM/DD
        m = re.search(r'还款日.{0,150}(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result
    
    # === 仅提取每月几号（固定还款日）===
    if not result['due_day']:
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
                        result['due_day'] = int(dm.group(2))
                else:
                    try:
                        result['due_day'] = int(m.group(1))
                    except:
                        pass
                break
        
        # 兜底：查找 "还款" + 日期模式
        if not result['due_day']:
            m = re.search(r'还款.*?(\d{2}月\d{1,2}日)', text)
            if m:
                dm = re.search(r'(\d{1,2})月(\d{1,2})日', m.group(1))
                if dm:
                    result['due_day'] = int(dm.group(2))
    
    return result


def extract_card_last4(text, soup):
    """提取卡号后4位"""
    # 方法1: 查找 "****NNNN" 模式（最可靠）
    m = re.search(r'\*{4,}(\d{4})', text)
    if m:
        val = int(m.group(1))
        # 排除年份（2024-2099）
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法2: 上海银行特殊处理 - 交易明细中每笔都包含卡号末四位
    # 在提取的文本中格式: "...588.00- 3493 中国..." 或 "...1.00+ 3493 中国..."
    # 匹配: 金额 + 4位数字 + "中国"（交易国家）
    # 取出现次数最多的候选作为卡号末四位
    candidates = {}
    for m in re.finditer(r'([\d,]+\.\d{2})[+-]?\s+(\d{4})\s+中国', text):
        amount_val = float(m.group(1).replace(',', ''))
        card_val = int(m.group(2))
        if not (2020 <= card_val <= 2099) and amount_val < 1000:
            candidates[card_val] = candidates.get(card_val, 0) + 1
    
    if candidates:
        # 取出现次数最多的（卡号会在多笔交易中重复出现）
        best_card = max(candidates, key=candidates.get)
        return str(best_card).zfill(4)
    
    # 方法3: "卡号末四位" 表头后面的4位数字
    m = re.search(r'卡号末四位.{0,200}(\d{4})', text)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法4: "卡号" + 4位数字，但排除身份证/长数字中的片段
    # 上海银行格式: "卡号末四位</strong>...3493"
    m = re.search(r'卡号.{0,200}(\d{4})', text)
    if m:
        val = int(m.group(1))
        # 排除年份和身份证号中的片段（3011 是身份证号的一部分）
        if not (2020 <= val <= 2099) and val < 1000:
            return m.group(1)
    
    # 方法5: "Card Number" + 4位数字，排除年份
    m = re.search(r'Card.{0,150}(\d{4})', text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)
    
    # 方法6: 查找包含 "card" 或 "卡号" 的表格行
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

    # 中国银行PDF特殊格式:
    #   到期还款日 账单日 本期人民币欠款总计 ...
    #   Payment Due Date Statement Closing Date Current RMB Total Balance Due ...
    #   2026-04-30 2026-04-10 3,508.93
    # 先尝试匹配这种三行结构
    m = re.search(r'到期还款日.{0,200}(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+([\d,]+\.?\d{2})', full_text)
    if m:
        info['due_date_full'] = m.group(1)
        info['due_day'] = int(m.group(1).split('-')[2])
        info['total_amount'] = float(m.group(3).replace(',', ''))

    # 如果没匹配到，用通用正则
    if not info.get('total_amount'):
        m = re.search(r'本期人民币欠款总计.{0,200}(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+([\d,]+\.?\d{2})', full_text, re.DOTALL)
        if m:
            try:
                info['total_amount'] = float(m.group(3).replace(',', ''))
            except:
                pass

    # 还款日兜底
    if not info.get('due_day'):
        m = re.search(r'到期还款日.+?(\d{4}-\d{2}-\d{2})', full_text, re.DOTALL)
        if m:
            info['due_date_full'] = m.group(1)
            dm = re.search(r'(\d{2})-(\d{2})$', m.group(1))
            if dm:
                info['due_day'] = int(dm.group(2))

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
        # 文件名没有月份 → 直接从邮件 Date 头提取，几月发的就是几月账单
        try:
            with open(filepath, 'rb') as fh:
                msg = email.message_from_bytes(fh.read(), policy=default)
            date_str = msg.get('Date', '')
            if date_str:
                dt = datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')
                month = f"{dt.year}-{dt.month:02d}"
        except:
            pass
        
        if not month:
            # 最后 fallback：用当前月份
            month = datetime.now().strftime('%Y-%m')

    # Try PDF first (for banks like BOC that send PDF attachments)
    # 先尝试用HTML文件名替换为.pdf查找
    pdf_path = str(filepath).replace('.html', '.pdf')
    if not os.path.exists(pdf_path):
        # 如果没找到，尝试大写扩展名
        pdf_path2 = str(filepath).replace('.html', '.PDF')
        if os.path.exists(pdf_path2):
            pdf_path = pdf_path2
    # 再尝试用bank+月份模式查找（如"中国银行信用卡电子合并账单2026年01月账单.PDF"）
    if not os.path.exists(pdf_path):
        import glob as _glob
        pdf_matches = _glob.glob(f'bills/*{bank}*{month.replace("-","年")}月*.PDF')
        if not pdf_matches:
            # 也尝试不带月份的模糊匹配
            pdf_matches = _glob.glob(f'bills/*{bank}*账单*.PDF')
        if pdf_matches:
            # 优先匹配同月份的
            for pm in pdf_matches:
                if month.replace('-','年') in pm or f'{month.split("-")[1]}月' in pm:
                    pdf_path = pm
                    break
            else:
                pdf_path = pdf_matches[0]
        pdf_info = extract_from_pdf(pdf_path)
        if pdf_info and (pdf_info.get('card_last4') or pdf_info.get('total_amount')):
            info = pdf_info
            print(f"  ✓ PDF解析 {bank} {month}")
            # Skip HTML parsing for PDF documents
            return _save_and_report(conn, bank, month, info, filename)

    # Decode email and extract text
    text, soup, html_raw = decode_email(filepath)

    # Extract data using BeautifulSoup + regex
    info = {
        'card_last4': extract_card_last4(text, soup),
        'total_amount': extract_amount(text),
        'min_payment': extract_min_payment(text),
        'due_day': None,
        'due_date_full': None,
    }
    
    # Extract due date info from text + HTML structure (works for all banks)
    due_info = extract_due_info(text, html_raw, soup)
    if due_info.get('due_day'):
        info['due_day'] = due_info['due_day']
    if due_info.get('due_date_full'):
        info['due_date_full'] = due_info['due_date_full']
    
    # If not found, try raw HTML with Chinese encodings (for GBK/gb18030 bills)
    if not info.get('due_day') and not info.get('due_date_full'):
        for enc in ['gbk', 'gb2312', 'gb18030']:
            try:
                raw_decoded = html_raw.encode('latin-1').decode(enc, errors='replace')
                due_info2 = extract_due_info(raw_decoded)
                if due_info2.get('due_day'):
                    info['due_day'] = due_info2['due_day']
                if due_info2.get('due_date_full'):
                    info['due_date_full'] = due_info2['due_date_full']
                break
            except:
                pass
    
    # Also try raw bytes directly
    if not info.get('due_day') and not info.get('due_date_full'):
        with open(filepath, 'rb') as f:
            raw_bytes = f.read()
        for enc in ['gbk', 'gb2312', 'gb18030']:
            try:
                raw_decoded = raw_bytes.decode(enc, errors='replace')
                due_info3 = extract_due_info(raw_decoded)
                if due_info3.get('due_day'):
                    info['due_day'] = due_info3['due_day']
                if due_info3.get('due_date_full'):
                    info['due_date_full'] = due_info3['due_date_full']
                break
            except:
                pass

    return _save_and_report(conn, bank, month, info, filename)


def _save_and_report(conn, bank, month, info, filename):
    """保存解析结果到数据库并输出"""

    # Upsert card info - 按卡号末四位去重，支持同一银行多张卡
    c = conn.cursor()
    
    # 先尝试按卡号末四位查找
    card_id = None
    if info.get('card_last4'):
        c.execute('''SELECT id FROM cards WHERE card_last4 = ?''', (info['card_last4'],))
        row = c.fetchone()
        if row:
            card_id = row[0]
    
    # 如果卡号末四位没找到，按银行名查找（兼容旧数据）
    if card_id is None:
        c.execute('''SELECT id FROM cards WHERE bank = ?''', (bank,))
        row = c.fetchone()
        if row:
            card_id = row[0]
    
    # 如果是新卡，插入
    if card_id is None:
        c.execute('''INSERT INTO cards (bank, card_last4, due_date_full, card_number)
                     VALUES (?, ?, ?, ?)''',
                  (bank, info.get('card_last4'), info.get('due_date_full'), info.get('card_number')))
        card_id = c.lastrowid
    
    # 更新已有卡的信息
    updates = []
    params = []
    if info.get('card_last4'):
        c.execute('''SELECT card_last4 FROM cards WHERE id = ?''', (card_id,))
        existing = c.fetchone()
        if not existing or not existing[0]:
            updates.append('card_last4 = ?')
            params.append(info['card_last4'])
    if info.get('due_date_full'):
        c.execute('''SELECT due_date_full FROM cards WHERE id = ?''', (card_id,))
        existing = c.fetchone()
        if not existing or not existing[0]:
            updates.append('due_date_full = ?')
            params.append(info['due_date_full'])
    if info.get('card_number'):
        c.execute('''SELECT card_number FROM cards WHERE id = ?''', (card_id,))
        existing = c.fetchone()
        if not existing or not existing[0]:
            updates.append('card_number = ?')
            params.append(info['card_number'])
    
    if updates:
        params.extend([card_id])
        c.execute(f'''UPDATE cards SET {', '.join(updates)}, updated_at = datetime('now')
                     WHERE id = ?''', params)

    # Insert bill record
    c.execute('''INSERT INTO bills (card_id, bank, bill_month, total_amount, min_payment,
                 due_date, due_date_full, paid, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)''',
              (card_id, bank, month,
               info.get('total_amount'), info.get('min_payment'),
               None, info.get('due_date_full'), filename))

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
    if info.get('due_date_full'):
        parts.append(f"到期{info['due_date_full']}")

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
