# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Credit Card Management System** written in Python with a Vue 3 frontend. It automatically fetches credit card bills from email (Sina IMAP), parses them from 13+ Chinese banks, stores them in SQLite, and provides a web dashboard for tracking bills, calendars, reports, and repayment reminders.

## Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Configure email password (required)
# Edit .env file: SINA_EMAIL_PASSWORD=your_password

# Run full pipeline (fetch → parse → check reminders)
python main.py run

# Web interface (Flask + Vue SPA)
cd api && python app.py
# Visit http://localhost:5000
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `python main.py fetch` | Download bill emails from Sina IMAP |
| `python main.py parse` | Parse all unprocessed bill files |
| `python main.py check [days]` | Check due dates (default: 5 days) |
| `python main.py report [month]` | Generate report (add `--quarter` or `--year`) |
| `python main.py calendar [year] [month]` | View repayment calendar |
| `python main.py dashboard` | Show total liabilities dashboard |
| `python main.py history [bank]` | View repayment history |
| `python main.py suggest` | Get repayment suggestions |
| `python main.py pay <bank> <month>` | Mark bill as paid |

## Architecture

```
main.py                    # CLI entry point with 10+ subcommands
src/
├── fetcher.py             # IMAP email downloading (增量下载)
├── parser.py              # Main parser router → src/parsers/
├── parsers/               # 13 bank-specific parsers (cgb, spdb, bocom, etc.)
│   ├── base.py            # BillParser base class
│   ├── cgb.py             #广发银行
│   ├── spdb.py            #浦发银行
│   ├── bocom.py           #交通银行
│   ├── psbc.py            #邮储银行
│   ├── cmb.py             #招商银行
│   ├── ccb.py             #建设银行
│   ├── ceb.py             #光大银行
│   ├── boc.py             #中国银行 (PDF support)
│   ├── citic.py           #中信银行
│   ├── abc.py             #农业银行
│   ├── pab.py             #平安银行
│   ├── cmbc.py            #民生银行
│   └── bos.py             #上海银行
├── db.py                  # SQLite utils & query helpers
├── reminder.py            # Due date checking + WeChat push
├── report.py              # Monthly/quarterly/yearly reports
├── calendar.py            # Repayment calendar data
├── dashboard.py           # Dashboard summary data
├── history.py             # Payment history
├── suggestions.py         # Repayment plan suggestions
└── mark_paid.py           # Mark bills as paid
api/
└── app.py                 # Flask API + Vue SPA static files
web/                       # Vue 3 + Element Plus frontend
├── src/
│   ├── main.js
│   ├── router.js          # Vue Router config
│   ├── api.js             # API client
│   ├── views/             # Dashboard, Calendar, Report, History, etc.
│   └── components/
db/cards.db                # SQLite database
bills/                     # Raw HTML/PDF bill files
```

## Database Schema

**cards**: id, bank, card_last4, due_date_full, card_number, holder_name, created_at, updated_at

**bills**: id, card_id, bank, bill_month, total_amount, min_payment, due_date_full, paid, pay_date, source_file, raw_data, created_at

**processed_files**: filename, parsed_at

## Key Patterns

1. **Parser Routing**: `src/parsers/__init__.py` maps bank names to parser classes
2. **Email Processing**: HTML emails stored in `bills/`, PDFs extracted from email attachments
3. **Amount Extraction**: Multiple regex patterns with fallback strategies (see `parser.py` lines 119-213)
4. **Holder Name**: Extracted from emails with fallback rules for masked names (周*明 → 周君明)
5. **Thread-Safe DB**: `src/db.py` uses thread-local connection pooling
6. **SPA Routing**: Vue Router with history mode, Flask serves both API (`/api/*`) and static files

## Dependencies

- **Python**: bs4, lxml, pdfplumber, pyyaml, flask, flask-cors
- **Frontend**: Vue 3, Element Plus, ECharts, Vue Router, Axios

## Web Interface

- Run `python api/app.py` to start Flask server on port 5000
- Frontend built with Vue 3 + Element Plus
- API endpoints: `/api/dashboard`, `/api/calendar`, `/api/report`, `/api/history`, `/api/suggestions`, `/api/pay`
