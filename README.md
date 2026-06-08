# 信用卡管理系统

从邮箱自动获取各银行信用卡账单，解析后存入 SQLite，提供 Web 仪表盘、还款日历、消费报表和微信提醒。

## 功能

- **自动拉取** — 通过 IMAP 从新浪邮箱获取银行电子账单邮件
- **13 家银行解析** — 广发、浦发、交行、邮储、招商、建行、光大、中行、中信、农行、平安、民生、上海银行
- **Web 仪表盘** — Flask + Vue SPA，总负债概览、还款日历、历史还款、消费报表
- **还款提醒** — 到期前推送微信提醒（文本）
- **手动记账** — 支持口头告知已还，一键标记

## 安装

```bash
pip install -r requirements.txt
```

依赖：`bs4`, `lxml`, `pdfplumber`, `pyyaml`

## 配置

1. 编辑 `.env`（不提交到 git），填入邮箱密码和服务器信息：
   ```env
   # 邮箱登录
   SINA_EMAIL_PASSWORD=你的邮箱密码
   EMAIL_IMAP_HOST=imap.example.com
   EMAIL_IMAP_PORT=993
   EMAIL_USERNAME=you@example.com
   EMAIL_FOLDER=INBOX

   # 持卡人姓名补全规则（JSON，key=正则 pattern, value=补全后的名字）
   HOLDER_NAME_FALLBACK={"某*":"某君","某*某":"某君某"}
   ```

2. `config.yaml` 中配置服务地址、端口、邮件过滤规则、提醒天数等（不含敏感信息，可公开提交）：
   ```yaml
   server:
     host: 127.0.0.1    # 监听地址
     port: 5001          # 监听端口
   filters:
     subjects: ["电子账单", "对账单", ...]
     exclude_subjects: ["礼品", "优惠", ...]
   reminder:
     days_before: [1, 0]
   report:
     months_to_keep: 12
   ```

## 使用

### CLI 命令

```bash
python main.py fetch              # 下载账单邮件
python main.py parse              # 解析所有未解析的账单
python main.py check [days]       # 检查还款日（默认 5 天内）
python main.py report [month]     # 生成报表，加 --quarter / --year 切换周期
python main.py calendar [year] [month]   # 还款日历视图
python main.py dashboard          # 总负债仪表盘
python main.py history [bank]     # 历史还款记录
python main.py suggest            # 还款计划建议
python main.py pay <bank> <month> # 标记账单已还（如：pay 邮储银行 2026-04）
python main.py run                # 完整流程：fetch + parse + check
```

### Web 界面

```bash
cd ~/projects/credit_card_manager && python3 api/app.py
# 访问 http://127.0.0.1:5001（端口可在 config.yaml 的 server.port 修改）
```

Flask 同时提供 API（`/api/*`）和 Vue SPA 静态文件。

## 架构

```
main.py              # CLI 入口（10+ 子命令）
src/
├── fetcher.py       # IMAP 拉取邮件，增量下载
├── parser.py        # 主解析流程，路由到各银行 parser
├── parsers/         # 13 家银行独立解析器
│   ├── base.py      # BillParser 基类（日期提取、安全转换）
│   ├── cgb.py       # 广发银行
│   ├── spdb.py      # 浦发银行
│   ├── bocom.py     # 交通银行
│   ├── psbc.py      # 邮储银行
│   ├── cmb.py       # 招商银行
│   ├── ccb.py       # 建设银行
│   ├── ceb.py       # 光大银行
│   ├── boc.py       # 中国银行（支持 PDF 附件）
│   ├── citic.py     # 中信银行
│   ├── abc.py       # 农业银行
│   ├── pab.py       # 平安银行（含溢缴款处理）
│   ├── cmbc.py      # 民生银行
│   └── bos.py       # 上海银行
├── reminder.py      # 还款日检查 + 微信推送
├── report.py        # 月/季/年度消费报表
├── calendar.py      # 还款日历数据
├── dashboard.py     # 仪表盘数据
├── history.py       # 历史还款记录
├── suggestions.py   # 还款计划建议
└── mark_paid.py     # 标记账单已还
api/app.py           # Flask API + SPA 服务
web/                 # Vue 3 + Element Plus 前端
db/cards.db          # SQLite 数据库
bills/               # 原始账单 HTML/PDF 文件
.env                 # 敏感配置（不上传 git）
config.yaml          # 公开配置（上传 git）
```

## 数据库

SQLite `db/cards.db`：

| 表 | 字段 |
|---|---|
| `cards` | id, bank, card_last4, due_date_full, card_number, created_at, updated_at |
| `bills` | id, card_id, bank, bill_month, total_amount, min_payment, due_date, due_date_full, paid, pay_date, source_file, raw_data, created_at |
| `processed_files` | filename, parsed_at |

## 定时任务

配合 cron 自动运行：

```bash
# 每 6 小时执行一次完整流程
0 */6 * * * cd ~/projects/credit_card_manager && python main.py run >> logs/cron.log 2>&1
```

或配合 Hermes Agent cron job（每 6 小时自动拉取 + 解析 + 检查还款日）。

## 支持的银行

| 银行 | 解析器 |
|---|---|
| 广发银行 | `cgb.py` |
| 浦发银行 | `spdb.py` |
| 交通银行 | `bocom.py` |
| 邮储银行 | `psbc.py` |
| 招商银行 | `cmb.py` |
| 建设银行 | `ccb.py` |
| 光大银行 | `ceb.py` |
| 中国银行 | `boc.py` (含 PDF) |
| 中信银行 | `citic.py` |
| 农业银行 | `abc.py` |
| 平安银行 | `pab.py` |
| 民生银行 | `cmbc.py` |
| 上海银行 | `bos.py` |
