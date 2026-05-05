# 信用卡管理系统

从新浪邮箱自动获取各银行信用卡账单，解析后存入本地数据库，提供还款提醒和消费报表。

## 安装

```bash
pip install -r requirements.txt
```

## 配置

1. 编辑 `.env`，填入邮箱密码：
   ```
   SINA_EMAIL_PASSWORD=你的邮箱密码
   ```

2. `config.yaml` 中配置邮件过滤、提醒天数等（不含敏感信息）。

## 使用

### 完整流程
```bash
python main.py run
```

### 分步执行
```bash
python main.py fetch              # 下载账单邮件
python main.py parse              # 解析所有未解析的账单
python main.py check              # 检查还款日（并推送微信提醒）
python main.py report             # 生成本月消费报表
```

### 标记账单已还
```bash
python src/mark_paid.py 邮储银行 2026-04
```

## 数据库

SQLite 数据库位于 `db/cards.db`，包含：
- `cards` — 卡片信息（银行、卡号后4位、到期日）
- `bills` — 账单记录（月份、金额、还款状态、还款日期）
- `processed_files` — 已解析的文件记录

## 定时任务

配合 cron 自动运行：
```bash
# 每天早上9点执行完整流程
0 9 * * * cd ~/projects/credit_card_manager && python main.py run >> logs/cron.log 2>&1
```
