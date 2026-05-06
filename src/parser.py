"""信用卡账单解析器 - 使用 BeautifulSoup 渲染 HTML。

支持多银行HTML和PDF账单解析，结果存入数据库。
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

from src.parsers import get_parser
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

BASE_DIR = Path(__file__).parent.parent
BILLS_DIR = BASE_DIR / "bills"


def decode_email(filepath):
    """解码邮件，返回纯文本和soup。"""
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
                    except Exception:
                        html_raw = payload.decode('utf-8', errors='replace')
                    break
    else:
        payload = msg.get_payload(decode=True)
        if payload and isinstance(payload, bytes):
            charset = msg.get_content_charset() or 'utf-8'
            try:
                html_raw = payload.decode(charset, errors='replace')
            except Exception:
                html_raw = payload.decode('utf-8', errors='replace')
        elif payload and isinstance(payload, str):
            html_raw = payload

    if not html_raw:
        for enc in ['gbk', 'utf-8', 'gb2312', 'gb18030']:
            try:
                html_raw = raw.decode(enc, errors='replace')
                if '\ufffd' not in html_raw:
                    break
            except Exception:
                continue

    if not html_raw:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            html_raw = f.read()

    soup = BeautifulSoup(html_raw, 'lxml')
    text = soup.get_text(separator=' ', strip=True)

    for tag in soup(['script', 'style']):
        tag.decompose()

    return text, soup, html_raw


def extract_pdf_from_email(filepath):
    """从邮件中提取PDF附件并返回路径。"""
    with open(filepath, 'rb') as f:
        raw = f.read()

    msg = email.message_from_bytes(raw, policy=default)
    
    if not msg.is_multipart():
        return None
    
    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()
        
        if filename and content_type in ('application/pdf', 'application/octet-stream'):
            # Check if it's actually a PDF
            payload = part.get_payload(decode=True)
            if payload and isinstance(payload, bytes):
                # Verify PDF magic number
                if payload[:4] == b'%PDF':
                    # Save to bills directory with same name as email file
                    import os
                    base = Path(filepath).stem
                    # Remove .html extension from stem if present
                    if base.endswith('.html'):
                        base = base[:-5]
                    pdf_name = f"{base}.pdf"
                    out_path = BILLS_DIR / pdf_name
                    
                    with open(out_path, 'wb') as pf:
                        pf.write(payload)
                    return str(out_path)
    
    return None



def extract_amount(text):
    """从文本中提取应还金额。"""
    # 上海银行特殊处理: "本期余额" + 数字+/-
    m = re.search(r'本期余额\s+([\d,]+\.?\d{2})\+', text)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except Exception:
            pass

    m = re.search(r'本期余额\s+([\d,]+\.?\d{2})-', text)
    if m:
        return 0.0

    # 浦发特殊处理: "本期应还款总额： ￥237.10"
    m = re.search(r'本期应还款总额[：:]\s*[￥¥]\s*([\d,]+\.?\d{2})', text)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except Exception:
            pass

    # 交行特殊处理: "本期应还款 ￥7128.11"
    m = re.search(r'本期应还款[\s:：]*[￥¥]\s*([\d,]+\.?\d{2})', text)
    if m:
        try:
            val = float(m.group(1).replace(',', ''))
            if 5 <= val <= 100000:
                return val
        except Exception:
            pass

    # 广发特殊处理: "本期账单金额 最低还款额 最后还款日 入账货币 存款 卡片消费额度\n7495 14.20 14.20 人民币 0.00 134,000.00"
    # 表格格式: 列名行 + 数据行，数据行为 "卡号 金额 最低还款 货币 存款 额度"
    # 列名后可能有额外列(入账货币/存款/卡片消费额度)，数字在下一行或同段
    m = re.search(r'本期账单金额\s+最低还款额\s+最后还款日[^\n\r]*(?:\n|\s{2,})(\d+)\s+([\d,]+\.?\d{2})', text)
    if m:
        try:
            card_val = int(m.group(1))
            amount_val = float(m.group(2).replace(',', ''))
            # 确认是金额列而非卡号或额度: 金额应在5-100000之间，且不是卡号末四位(通常<2000)
            if 5 <= amount_val <= 100000 and card_val > 2099:
                return amount_val
        except Exception:
            pass

    # 广发另一种情况: 列名和数字在同一行(无换行)
    m = re.search(r'本期账单金额\s+最低还款额\s+最后还款日\s+入账货币\s+存款\s+卡片消费额度\s+(\d+)\s+([\d,]+\.?\d{2})', text)
    if m:
        try:
            card_val = int(m.group(1))
            amount_val = float(m.group(2).replace(',', ''))
            if 5 <= amount_val <= 100000 and card_val > 2099:
                return amount_val
        except Exception:
            pass

    # 通用模式
    patterns = [
        r'本期应还款总额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'本期应还[额]?\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'本期应还金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'本期账单金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'账单金额\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'应还款\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'应还[额]?\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'本期应还款总额\s*CNY\s*(-?[\d,]+\.?\d{2})',
        r'本期最低还款额\s*CNY\s*(-?[\d,]+\.?\d{2})',
        r'New\s+Balance\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'Credit\s+Balance\s*(?:CNY|人民币)?\s*(-?[\d,]+\.?\d{2})',
        r'New\s+Balance.{0,30}人民币.{0,15}CNY.{0,15}-?[\d,]+\.?\d{2}\s+(-?[\d,]+\.?\d{2})',
        r'New\s+Balance.{0,30}CNY.{0,15}-?[\d,]+\.?\d{2}\s+(-?[\d,]+\.?\d{2})',
        r'本期全部应还款额.{0,50}人民币.{0,15}CNY.{0,15}-?[\d,]+\.?\d{2}\s+(-?[\d,]+\.?\d{2})',
        r'本期全部应还款额.{0,50}(-?[\d,]+\.?\d{2})',
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except Exception:
                pass

    # 兜底 - 排除利率、客服电话等干扰项
    # 先过滤掉含"年利率"、"日利率"、"热线"、"服务号"的行
    lines = text.split('\n')
    for line in lines:
        if any(kw in line for kw in ['额度', 'Credit Limit', 'Available Limit', 'Cash Advance',
                                       '年利率', '日利率', '热线', '服务号', '客服热线']):
            continue
        m = re.search(r'[¥￥]\s*([\d,]+\.?\d{2})', line)
        if m:
            try:
                val = float(m.group(1).replace(',', ''))
                if 5 <= val <= 50000:
                    return val
            except Exception:
                pass

    # 兜底2 - 没有¥符号时，跳过含"卡号"、"末四位"的行
    for line in lines:
        if any(kw in line for kw in ['额度', 'Credit Limit', 'Available Limit', 'Cash Advance',
                                       '年利率', '日利率', '热线', '服务号', '客服热线',
                                       '卡号', '末四位']):
            continue
        m = re.search(r'([\d,]+\.?\d{2})', line)
        if m:
            try:
                val = float(m.group(1).replace(',', ''))
                if 5 <= val <= 50000:
                    return val
            except Exception:
                pass

    # 全局匹配 - 排除利率和客服电话中的数字
    # 先移除含"年利率"、"热线"的片段
    cleaned = re.sub(r'.{0,20}年利率.{0,5}', '', text)
    cleaned = re.sub(r'.{0,20}热线.{0,5}', '', cleaned)
    # 优先匹配带¥符号的金额
    amounts = re.findall(r'[¥￥]\s*([\d,]+\.?\d{2})', cleaned)
    if amounts:
        parsed = []
        for a in amounts:
            try:
                val = float(a.replace(',', ''))
                if 5 <= val <= 50000:
                    parsed.append(val)
            except Exception:
                pass
        return max(parsed) if parsed else None

    # 没有¥符号时，排除含"卡号"、"末四位"的行
    cleaned_lines = [l for l in text.split('\n') if not any(kw in l for kw in ['卡号', '末四位'])]
    cleaned_text = '\n'.join(cleaned_lines)
    amounts = re.findall(r'([\d,]+\.?\d{2})', cleaned_text)
    parsed = []
    for a in amounts:
        try:
            val = float(a.replace(',', ''))
            if 5 <= val <= 50000:
                parsed.append(val)
        except Exception:
            pass

    return max(parsed) if parsed else None


def extract_min_payment(text):
    """提取最低还款额。"""
    patterns = [
        r'最低应还[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.?\d{2})',
        r'最低还款[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.?\d{2})',
        r'Min\. Payment\s*(?:CNY|人民币)?\s*([\d,]+\.?\d{2})',
        r'最低还款额\s*CNY\s*([\d,]+\.?\d{2})',
        r'最低[额]?\s*(?:CNY|人民币)?\s*([\d,]+\.?\d{2})',
    ]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                return float(m.group(1).replace(',', ''))
            except Exception:
                pass

    return None


def extract_due_info(text, soup=None):
    """提取还款日信息。"""
    result = {'due_day': None, 'due_date_full': None}

    # HTML表格结构（光大银行等）
    if soup:
        tds = soup.find_all('td')
        for i, td in enumerate(tds):
            t = td.get_text(strip=True)
            if 'Due Date' in t or '到期还款日' in t or '最后还款日' in t:
                dates = []
                for j in range(i, min(i + 10, len(tds))):
                    dt = tds[j].get_text(strip=True)
                    if re.match(r'\d{4}/\d{2}/\d{2}$', dt):
                        dates.append(dt)
                    if len(dates) == 2:
                        break
                if len(dates) >= 2:
                    result['due_date_full'] = dates[1].replace('/', '-')
                    parts = dates[1].split('/')
                    result['due_day'] = int(parts[2])
                elif len(dates) == 1:
                    result['due_date_full'] = dates[0].replace('/', '-')
                    parts = dates[0].split('/')
                    result['due_day'] = int(parts[2])
                break

    # 纯文本正则
    if not result['due_date_full']:
        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result

        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{4})年(\d{1,2})月(\d{1,2})日', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result

        m = re.search(r'(?:到期|最后)?还款日.{0,150}(\d{1,2})月(\d{1,2})日', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            result['due_day'] = day
            year_m = re.search(r'(\d{4})年', text[:500])
            if year_m:
                result['due_date_full'] = f"{year_m.group(1)}-{month:02d}-{day:02d}"
            return result

        m = re.search(r'还款日.{0,150}(\d{4})[/-](\d{1,2})[/-](\d{1,2})', text)
        if m:
            year, month, day = m.group(1), m.group(2), m.group(3)
            result['due_date_full'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            result['due_day'] = int(day)
            return result

    # 仅提取每月几号
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
                    except Exception:
                        pass
                break

        if not result['due_day']:
            m = re.search(r'还款.*?(\d{2}月\d{1,2}日)', text)
            if m:
                dm = re.search(r'(\d{1,2})月(\d{1,2})日', m.group(1))
                if dm:
                    result['due_day'] = int(dm.group(2))

    return result


def extract_card_last4(text, soup):
    """提取卡号后4位。"""
    m = re.search(r'\*{4,}(\d{4})', text)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)

    candidates = {}
    for m in re.finditer(r'([\d,]+\.?\d{2})[+-]?\s+(\d{4})\s+中国', text):
        amount_val = float(m.group(1).replace(',', ''))
        card_val = int(m.group(2))
        if not (2020 <= card_val <= 2099) and amount_val < 1000:
            candidates[card_val] = candidates.get(card_val, 0) + 1

    if candidates:
        best_card = max(candidates, key=candidates.get)
        return str(best_card).zfill(4)

    m = re.search(r'卡号末四位.{0,200}(\d{4})', text)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)

    m = re.search(r'卡号.{0,200}(\d{4})', text)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099) and val < 1000:
            return m.group(1)

    m = re.search(r'Card.{0,150}(\d{4})', text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if not (2020 <= val <= 2099):
            return m.group(1)

    if soup:
        for td in soup.find_all('td'):
            td_text = td.get_text(strip=True).lower()
            if 'card' in td_text or '卡号' in td_text:
                next_td = td.find_next_sibling('td')
                if next_td:
                    next_text = next_td.get_text(strip=True)
                    dm = re.search(r'(\d{4})', next_text)
                    if dm:
                        val = int(dm.group(1))
                        if not (2020 <= val <= 2099):
                            return dm.group(1)

    return None


def extract_from_pdf(filepath):
    """从PDF账单中提取数据。"""
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

    # 卡号
    m = re.search(r'\*{4}\s*(\d{4})', full_text)
    if m:
        info['card_last4'] = m.group(1)

    # 中国银行PDF特殊格式:
    #   到期还款日 账单日 本期人民币欠款总计 ...
    #   Payment Due Date Statement Closing Date Current RMB Total Balance Due ...
    #   2026-04-30 2026-04-10 3,508.93
    m = re.search(r'到期还款日.{0,200}(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+([\d,]+\.?\d{2})', full_text)
    if m:
        info['due_date_full'] = m.group(1)
        info['due_day'] = int(m.group(1).split('-')[2])
        info['total_amount'] = float(m.group(3).replace(',', ''))

    if not info.get('total_amount'):
        m = re.search(r'本期人民币欠款总计.{0,200}(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})\s+([\d,]+\.?\d{2})', full_text, re.DOTALL)
        if m:
            try:
                info['total_amount'] = float(m.group(3).replace(',', ''))
            except Exception:
                pass

    if not info.get('due_day'):
        m = re.search(r'到期还款日.+?(\d{4}-\d{2}-\d{2})', full_text, re.DOTALL)
        if m:
            info['due_date_full'] = m.group(1)
            dm = re.search(r'(\d{2})-(\d{2})$', m.group(1))
            if dm:
                info['due_day'] = int(dm.group(2))

    # 农业银行PDF格式 (slash date format):
    #   本期应还款额(欠款为-) New Balance
    #   人民币(CNY)
    #   (sometimes amount is missing here due to PDF layout)
    #   到期还款日 Payment Due Date 2026/05/02
    #   最低还款额(欠款为-) Min Payment
    #   -12.00   <-- this is actually New Balance value (溢缴款)
    #   人民币(CNY)
    #   0.00     <-- this is the real min payment
    if not info.get('total_amount'):
        # Try to find amount after 人民币(CNY) following New Balance
        m = re.search(r'本期应还款额[^\n]*New Balance[\s\S]*?人民币\s*\(CNY\)\s*(-?[\d,]+\.?\d{2})', full_text)
        if m:
            val = float(m.group(1).replace(',', ''))
            info['total_amount'] = abs(val) if val < 0 else val
        else:
            # Fallback: the amount might appear after Min Payment line (ABC PDF layout quirk)
            m = re.search(r'最低还款额[^\n]*Min Payment\s*(-?[\d,]+\.?\d{2})', full_text)
            if m:
                val = float(m.group(1).replace(',', ''))
                info['total_amount'] = abs(val) if val < 0 else val

    if not info.get('min_payment'):
        # Find the number AFTER 人民币(CNY) in the Min Payment section
        m = re.search(r'最低还款额[^\n]*Min Payment[\s\S]*?人民币\s*\(CNY\)\s*(\d[\d,]*\.?\d*)', full_text)
        if m:
            info['min_payment'] = float(m.group(1).replace(',', ''))

    if not info.get('due_date_full'):
        # ABC PDF: date appears before "Payment Due Date" label in table row
        m = re.search(r'(\d{4})/(\d{2})/(\d{2})[\s\S]*?Payment Due Date', full_text)
        # The first date matched is the statement cycle start, not due date.
        # Find the LAST date before Payment Due Date in the table row:
        #   625998******0301 2026/03/08-2026/04/07 2026/05/02\nCard No Statement Cycle Payment Due Date
        # Match the date right before \nCard No (the third column)
        m2 = re.search(r'\d{4}/\d{2}/\d{2}-\d{4}/\d{2}/\d{2}\s+(\d{4})/(\d{2})/(\d{2})[\s\S]*?Payment Due Date', full_text)
        if m2:
            m = m2
        if m:
            info['due_date_full'] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            info['due_day'] = int(m.group(3))

    return info



def extract_holder_name_from_email(filepath, html_raw, bank):
    """从邮件原始内容提取持卡人姓名。

    支持多种编码和格式:
    - 浦发 HTML: base64 编码 body → 解码后搜索 "尊敬的 XXX"
    - 中信 HTML: quoted-printable + UTF-8 → 搜索 <span data-key="customerName">姓名</span>
    - 民生 HTML: gb18030 编码 → 搜索 "尊敬的 XXX"
    - 交通 HTML: GBK 编码 → 搜索 "尊敬的 XXX"
    - 浦发 PDF: 直接提取 "尊敬的 XXX 先生/女士"
    """
    if not html_raw:
        return None

    # Try multiple encodings for the raw content
    texts_to_try = []

    # 1. Try decoding as-is (UTF-8)
    try:
        texts_to_try.append(('utf-8', html_raw))
    except Exception:
        pass

    # 2. Try common Chinese encodings on raw bytes
    if isinstance(html_raw, str):
        # If it's already a string, try re-encoding/decoding with different encodings
        for enc in ['gbk', 'gb2312', 'gb18030']:
            try:
                raw_bytes = html_raw.encode('utf-8', errors='replace')
                decoded = raw_bytes.decode(enc, errors='replace')
                texts_to_try.append((enc, decoded))
            except Exception:
                continue
    else:
        # html_raw is bytes, decode with various encodings
        for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
            try:
                texts_to_try.append((enc, html_raw.decode(enc, errors='replace')))
            except Exception:
                continue

    # 3. Also try decoding the raw file bytes directly with all encodings
    try:
        with open(filepath, 'rb') as f:
            raw_file = f.read()
        msg = email.message_from_bytes(raw_file, policy=default)
        for part in msg.walk():
            if part.get_content_type() == 'text/html':
                payload = part.get_payload(decode=True)
                if payload and isinstance(payload, bytes):
                    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030']:
                        try:
                            texts_to_try.append((enc, payload.decode(enc, errors='replace')))
                        except Exception:
                            continue
                    break
    except Exception:
        pass

    # Search for name patterns in all decoded texts (order matters: more specific first)
    for enc, text in texts_to_try:
        # Pattern 2: <span data-key="customerName">姓名</span> (中信 format) - most specific
        m = re.search(r'<[^>]*data-key\s*=\s*["\']customerName["\'][^>]*>([^<]+)</', text)
        if m:
            name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if name and len(name) >= 2:
                return _clean_holder_name(name)

        # Pattern 3: 尊敬的 <font>...</font> (浦发 base64 decoded format)
        m = re.search(r'尊敬的\s*<[^>]*>([^<]+)</', text)
        if m:
            raw_name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            # Handle "姓名先生/女士" without space (e.g., 周君明先生)
            m2 = re.match(r'([\u4e00-\u9fff]{2,6})(先生|女士)', raw_name)
            if m2:
                name = m2.group(1) + ' ' + m2.group(2)
            else:
                name = raw_name
            if name and len(name) >= 2:
                return _clean_holder_name(name)

        # Pattern 4: "尊敬的 XXX 先生/女士" (with space between name and gender)
        m = re.search(r'尊敬的\s*([^\s<\r\n&：:，,]{2,6})\s+(先生|女士)', text)
        if m:
            name = m.group(1).replace('&nbsp;', '').strip() + ' ' + m.group(2)
            if name and len(name) >= 3:
                return _clean_holder_name(name)

        # Pattern 6: "尊敬的 XXX先生/女士" (no space between name and gender)
        m = re.search(r'尊敬的\s*([^\s<\r\n&：:，,]{2,6})(先生|女士)', text)
        if m:
            name = m.group(1).replace('&nbsp;', '').strip() + ' ' + m.group(2)
            if name and len(name) >= 3:
                return _clean_holder_name(name)

        # Pattern 1: "尊敬的 XXX" (plain text, no gender suffix) - least specific
        m = re.search(r'尊敬的\s*([^\s<\r\n&：:，,先生女士]{2,6})', text)
        if m:
            name = m.group(1).replace('&nbsp;', '').strip()
            if name and len(name) >= 2:
                return _clean_holder_name(name)

    return None


def _clean_holder_name(name):
    """清理持卡人姓名: 去掉'先生/女士'后缀，尝试补全带*的名字。"""
    # Strip 先生/女士 suffix
    name = re.sub(r'\s*(先生|女士)$', '', name)
    
    # Try to fill in masked names based on known data
    # 周*明 / 周**明 -> 周君明
    if re.match(r'^周\*+明$', name):
        return '周君明'
    # 石* -> 石磊
    if re.match(r'^石\*+$', name):
        return '石磊'
    # 周** (浦发卡) -> 周君明 (全局数据推断)
    if re.match(r'^周\*\*+$', name):
        return '周君明'
    
    return name


def extract_holder_name_from_pdf(filepath):
    """从PDF账单提取持卡人姓名。"""
    if not HAS_PDFPLUMBER:
        return None

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                # Pattern: "尊敬的周君明 先生" (浦发 PDF format)
                m = re.search(r'尊敬的\s*([\u4e00-\u9fff]{2,6})\s*(先生|女士)', text)
                if m:
                    return _clean_holder_name(m.group(1) + ' ' + m.group(2))

                # Pattern: "尊敬的 XXX" (without gender)
                m = re.search(r'尊敬的\s*([\u4e00-\u9fff]{2,6})', text)
                if m:
                    return _clean_holder_name(m.group(1))
    except Exception:
        pass

    return None


def extract_bank_from_filename(filename):
    """从文件名提取银行名。"""
    parts = Path(filename).stem.split('_', 1)
    if len(parts) >= 2:
        return parts[1].split('_', 1)[0]
    return None


def extract_month_from_filename(filename):
    """从文件名提取月份。"""
    stem = Path(filename).stem
    m = re.search(r'(\d{4})年(\d{1,2})月', stem)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    m = re.search(r'(\d{4})[-](\d{1,2})', stem)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    return None


def process_file(conn, filepath):
    """解析单个账单文件。"""
    from src.db import get_unpaid_amount_by_card

    filename = filepath.name
    bank = extract_bank_from_filename(filename)
    month = extract_month_from_filename(filename)

    if not bank:
        print(f"  ⚠️  无法识别银行: {filename}")
        return None

    if not month:
        try:
            with open(filepath, 'rb') as fh:
                msg = email.message_from_bytes(fh.read(), policy=default)
            date_str = msg.get('Date', '')
            if date_str:
                dt = datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')
                month = f"{dt.year}-{dt.month:02d}"
        except Exception:
            pass

        if not month:
            month = datetime.now().strftime('%Y-%m')

    # Try PDF first (standalone .pdf file next to .html)
    pdf_path = str(filepath).replace('.html', '.pdf')
    if not os.path.exists(pdf_path):
        pdf_path2 = str(filepath).replace('.html', '.PDF')
        if os.path.exists(pdf_path2):
            pdf_path = pdf_path2

    # Also search for PDF in bills directory
    if not os.path.exists(pdf_path):
        import glob as _glob
        pdf_matches = _glob.glob(f'bills/*{bank}*{month.replace("-","年")}月*.PDF')
        if not pdf_matches:
            pdf_matches = _glob.glob(f'bills/*{bank}*账单*.PDF')
        if pdf_matches:
            for pm in pdf_matches:
                if month.replace('-','年') in pm or f'{month.split("-")[1]}月' in pm:
                    pdf_path = pm
                    break
            else:
                pdf_path = pdf_matches[0]

        if os.path.exists(pdf_path):
            pdf_info = extract_from_pdf(pdf_path)
            if pdf_info and (pdf_info.get('card_last4') or pdf_info.get('total_amount')):
                info = pdf_info
                print(f"  ✓ PDF解析 {bank} {month}")
                return _save_and_report(conn, bank, month, info, filename)

    # Decode email and extract text
    text, soup, html_raw = decode_email(filepath)

    # If HTML text is empty (email contains only PDF attachment),
    # try extracting PDF from the email itself
    if not text.strip():
        pdf_from_email = extract_pdf_from_email(filepath)
        if pdf_from_email:
            pdf_info = extract_from_pdf(pdf_from_email)
            if pdf_info and (pdf_info.get('card_last4') or pdf_info.get('total_amount')):
                info = pdf_info
                # Extract holder name from PDF
                holder_name = extract_holder_name_from_pdf(pdf_from_email)
                if holder_name:
                    info['holder_name'] = holder_name
                print(f"  ✓ PDF解析 {bank} {month}")
                return _save_and_report(conn, bank, month, info, filename)

    # Try bank-specific parser first
    parser = get_parser(bank)
    if parser:
        info = parser.extract(text)
        # Fallback card_last4 from generic function if parser didn't find it
        if not info.get('card_last4'):
            info['card_last4'] = extract_card_last4(text, soup)
    else:
        # Fallback to generic extraction (for unknown banks)
        info = {
            'card_last4': extract_card_last4(text, soup),
            'total_amount': extract_amount(text),
            'min_payment': extract_min_payment(text),
            'due_day': None,
            'due_date_full': None,
        }
        due_info = extract_due_info(text, soup)
        if due_info.get('due_day'):
            info['due_day'] = due_info['due_day']
        if due_info.get('due_date_full'):
            info['due_date_full'] = due_info['due_date_full']

    # Extract holder name from HTML email
    if not info.get('holder_name'):
        info['holder_name'] = extract_holder_name_from_email(filepath, html_raw, bank)

    return _save_and_report(conn, bank, month, info, filename)


def _save_and_report(conn, bank, month, info, filename):
    """保存解析结果到数据库并输出。"""
    c = conn.cursor()

    # Upsert card info
    card_id = None
    if info.get('card_last4'):
        c.execute('SELECT id FROM cards WHERE card_last4 = ?', (info['card_last4'],))
        row = c.fetchone()
        if row:
            card_id = row[0]

    if card_id is None:
        c.execute('SELECT id FROM cards WHERE bank = ?', (bank,))
        row = c.fetchone()
        if row:
            card_id = row[0]

    if card_id is None:
        c.execute('''INSERT INTO cards (bank, card_last4, due_date_full, card_number)
                     VALUES (?, ?, ?, ?)''',
                  (bank, info.get('card_last4'), info.get('due_date_full'), info.get('card_number')))
        card_id = c.lastrowid

    updates = []
    params = []
    if info.get('card_last4'):
        c.execute('SELECT card_last4 FROM cards WHERE id = ?', (card_id,))
        existing = c.fetchone()
        if not existing or not existing[0]:
            updates.append('card_last4 = ?')
            params.append(info['card_last4'])
    if info.get('due_date_full'):
        c.execute('SELECT due_date_full FROM cards WHERE id = ?', (card_id,))
        existing = c.fetchone()
        if not existing or not existing[0]:
            updates.append('due_date_full = ?')
            params.append(info['due_date_full'])

    if updates:
        params.extend([card_id])
        c.execute(f"UPDATE cards SET {', '.join(updates)}, updated_at = datetime('now') WHERE id = ?", params)

    # Also update holder_name if extracted
    if info.get('holder_name'):
        clean_name = _clean_holder_name(info['holder_name'])
        c.execute('''UPDATE cards SET holder_name = ?, updated_at = datetime('now') WHERE id = ?''',
                  (clean_name, card_id))

    # Insert bill record
    c.execute('''INSERT INTO bills (card_id, bank, bill_month, total_amount, min_payment,
                 due_date, due_date_full, paid, source_file) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)''',
              (card_id, bank, month,
               info.get('total_amount'), info.get('min_payment'),
               None, info.get('due_date_full'), filename))

    c.execute('INSERT OR IGNORE INTO processed_files (filename) VALUES (?)', (filename,))
    conn.commit()

    # Print summary
    parts = [f"{bank} {month}"]
    if info.get('holder_name'):
        parts.append(f"持卡人: {info['holder_name']}")
    if info.get('card_last4'):
        parts.append(f"****{info['card_last4']}")
    if info.get('total_amount'):
        parts.append(f"¥{info['total_amount']:,.2f}")
    if info.get('min_payment'):
        parts.append(f"最低¥{info['min_payment']:,.2f}")
    if info.get('due_date_full'):
        parts.append(f"到期{info['due_date_full']}")

    print(f"  ✓ {' | '.join(parts)}")

    # 年费提醒
    if info.get('annual_fee'):
        print(f"  ⚠️  年费提醒: {bank} {month} 账单含年费 ¥{info['annual_fee']:,.2f}")

    return info


def parse_all():
    """解析所有未处理的账单文件。"""
    from src.db import get_connection

    conn = get_connection()

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
    if '--file' in sys.argv:
        idx = sys.argv.index('--file')
        if idx + 1 < len(sys.argv):
            target = Path(sys.argv[idx + 1])
            if not target.exists():
                print(f"文件不存在: {target}")
                sys.exit(1)

            from src.db import get_connection
            conn = get_connection()
            process_file(conn, target)
            conn.close()
        else:
            print("用法: python parser.py --file <path>")
    else:
        parse_all()
