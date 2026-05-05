#!/usr/bin/env python3
"""
从新浪邮箱下载信用卡账单邮件到本地。

用法:
    python fetch_bills.py              # 拉取所有未下载的账单邮件
    python fetch_bills.py --since 2026-05-01  # 只拉指定日期之后的
"""

import imaplib
import email
from email.parser import BytesParser
from email.policy import default
import os
import sys
import re
import time
import yaml
from datetime import datetime, timedelta
from pathlib import Path


def load_config(config_path=None):
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_bank_name(from_addr, subject):
    """从发件人和主题中提取银行名"""
    banks = {
        '广发银行': ['cgbchina.com.cn', 'cgb_'],
        '招商银行': ['message.cmbchina.com', 'ccsvc@'],
        '交通银行': ['bocomcc.com', 'pccc@'],
        '民生银行': ['cmbc.com.cn', 'master@'],
        '光大银行': ['cebbank.com', 'cebbank@'],
        '浦发银行': ['spdbccc.com', 'estmtservice@'],
        '邮储银行': ['cardmail', 'creditcardcenter@'],
        '平安银行': ['pingan.com', 'creditcard@service'],
        '农业银行': ['abchina.com.cn', 'e-statement@'],
        '中国银行': ['bankofchina.com', 'boczhangdan@'],
        '建设银行': ['ccb.com', 'service@vip.ccb.com'],
        '中信银行': ['citiccard.com', 'citiccard@'],
        '上海银行': ['bosc.cn', 'message@service'],
    }

    from_lower = from_addr.lower()
    subject_lower = subject.lower()

    for bank_name, patterns in banks.items():
        for pattern in patterns:
            if pattern.lower() in from_lower or pattern.lower() in subject_lower:
                return bank_name

    # Fallback: extract from email domain
    if '@' in from_addr:
        domain = from_addr.split('@')[1]
        return domain


def clean_filename(text, max_len=60):
    """清理文件名中的非法字符"""
    text = re.sub(r'[<>:"\\|？*]', '_', text)
    return text[:max_len]


def is_bill_email(subject):
    """判断是否账单邮件（排除营销）"""
    subjects_lower = subject.lower()

    # 排除营销
    for exclude in ['礼品', '优惠', '活动', 'promotion', 'deals', 'gift', 'reward']:
        if exclude in subjects_lower:
            return False

    # 只保留账单相关
    for keyword in ['账单', '对账单', 'statement', 'billing']:
        if keyword in subjects_lower:
            return True

    return False


def download_emails(since_date=None):
    config = load_config()
    email_cfg = config['email']

    # Connect to IMAP
    print(f"📧 连接邮箱 {email_cfg['username']}...")
    mail = imaplib.IMAP4_SSL(email_cfg['imap_host'], email_cfg['imap_port'])
    mail.login(email_cfg['username'], email_cfg['password'])
    mail.select(email_cfg['folder'])

    # Build search criteria
    if since_date:
        # Parse date string (YYYY-MM-DD)
        search_date = datetime.strptime(since_date, '%Y-%m-%d').strftime('%d-%b-%Y')
        status, data = mail.search(None, f'(SINCE "{search_date}")')
    else:
        # Default: last 90 days
        since = (datetime.now() - timedelta(days=90)).strftime('%d-%b-%Y')
        status, data = mail.search(None, f'(SINCE "{since}")')

    if status != 'OK':
        print("✗ 搜索失败")
        return

    email_ids = data[0].split()
    print(f"✓ 找到 {len(email_ids)} 封邮件 (最近90天)")

    # Create output directory
    bills_dir = Path(__file__).parent / "bills"
    bills_dir.mkdir(exist_ok=True)

    # Track downloaded files
    existing_files = set(f.name for f in bills_dir.glob("*.html"))

    downloaded = 0
    skipped = 0
    errors = 0

    for email_id in email_ids:
        try:
            # Fetch the email
            status, msg_data = mail.fetch(email_id, '(RFC822)')
            if status != 'OK':
                continue

            raw_email = msg_data[0][1]
            msg = BytesParser(policy=default).parsebytes(raw_email)

            from_addr = msg.get('From', '')
            subject = msg.get('Subject', '')
            date_str = msg.get('Date', '')

            # Check if it's a bill email
            if not is_bill_email(subject):
                skipped += 1
                continue

            # Extract bank name
            bank = get_bank_name(from_addr, subject)

            # Build filename: {email_id}_{bank}_{subject}.html
            safe_subject = clean_filename(subject, max_len=40)
            filename = f"{email_id.decode()[:12]}_{bank}_{safe_subject}.html"

            # Skip if already downloaded
            if filename in existing_files:
                skipped += 1
                continue

            # Save HTML email as-is
            filepath = bills_dir / filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(raw_email.decode('utf-8', errors='replace'))

            # Extract PDF attachments from multipart emails
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    fn = part.get_filename()
                    if ct == 'application/octet-stream' and fn and fn.lower().endswith('.pdf'):
                        pdf_data = part.get_payload(decode=True)
                        if pdf_data:
                            # Clean PDF filename
                            safe_pdf_name = clean_filename(fn, max_len=60)
                            pdf_path = bills_dir / safe_pdf_name
                            # Avoid overwriting existing PDFs
                            if pdf_path.exists():
                                base, ext = os.path.splitext(safe_pdf_name)
                                i = 1
                                while (bills_dir / f"{base}_{i}{ext}").exists():
                                    i += 1
                                pdf_path = bills_dir / f"{base}_{i}{ext}"
                            with open(pdf_path, 'wb') as pf:
                                pf.write(pdf_data)
                            print(f"  📎 PDF附件: {safe_pdf_name}")

            downloaded += 1
            print(f"  ✓ {bank}: {subject[:50]}")

        except Exception as e:
            errors += 1
            print(f"  ✗ Error: {e}")

    mail.logout()

    print(f"\n{'='*50}")
    print(f"  下载完成:")
    print(f"  ✅ 新下载: {downloaded}")
    print(f"  ⏭️  跳过: {skipped}")
    print(f"  ❌ 错误: {errors}")
    print(f"{'='*50}")

    return downloaded


if __name__ == '__main__':
    since_date = None
    if '--since' in sys.argv:
        idx = sys.argv.index('--since')
        if idx + 1 < len(sys.argv):
            since_date = sys.argv[idx + 1]

    download_emails(since_date=since_date)
