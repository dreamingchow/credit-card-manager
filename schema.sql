-- 信用卡账单管理系统 - 数据库建表语句
-- 使用方法: sqlite3 cards.db < schema.sql

CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bank TEXT NOT NULL,
    card_last4 TEXT,
    due_date_full TEXT,
    card_number TEXT,
    holder_name TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bills (
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
);

CREATE TABLE IF NOT EXISTS processed_files (
    filename TEXT PRIMARY KEY,
    parsed_at TEXT DEFAULT (datetime('now'))
);
