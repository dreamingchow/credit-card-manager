#!/usr/bin/env python3
"""信用卡管理系统 - 主入口。

用法:
    python main.py fetch              # 下载账单邮件
    python main.py parse              # 解析所有未解析的账单
    python main.py check [days]       # 检查还款日（默认5天内）
    python main.py report [month]     # 生成报表（默认本月）
    python main.py calendar [year] [month]  # 还款日历视图
    python main.py dashboard          # 总负债仪表盘
    python main.py history [bank]     # 历史还款记录
    python main.py suggest            # 还款计划建议
    python main.py pay <bank> <month> # 标记账单已还
    python main.py run                # 完整流程：fetch + parse + check
"""

import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]

    if cmd == 'fetch':
        from src.fetcher import download_emails
        since_date = sys.argv[2] if len(sys.argv) > 2 else None
        download_emails(since_date=since_date)

    elif cmd == 'parse':
        from src.parser import parse_all
        parse_all()

    elif cmd == 'check':
        from src.reminder import run as check_run
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        check_run(days_before=days)

    elif cmd == 'report':
        from src.report import run as report_run
        period_type = 'month'
        period_value = None

        if '--quarter' in sys.argv:
            period_type = 'quarter'
            idx = sys.argv.index('--quarter')
            if idx + 1 < len(sys.argv):
                period_value = sys.argv[idx + 1]
            else:
                # default to current quarter
                import datetime as dt
                q = (dt.datetime.now().month - 1) // 3 + 1
                period_value = str(dt.datetime.now().year)
        elif '--year' in sys.argv:
            period_type = 'year'
            idx = sys.argv.index('--year')
            if idx + 1 < len(sys.argv):
                period_value = sys.argv[idx + 1]
            else:
                period_value = str(datetime.now().year)
        elif len(sys.argv) > 2:
            period_value = sys.argv[2]

        report_run(period_type, period_value)

    elif cmd == 'calendar':
        from src.calendar import run as calendar_run
        year = int(sys.argv[2]) if len(sys.argv) > 2 else None
        month = int(sys.argv[3]) if len(sys.argv) > 3 else None
        calendar_run(year, month)

    elif cmd == 'dashboard':
        from src.dashboard import run as dashboard_run
        dashboard_run()

    elif cmd == 'history':
        from src.history import run as history_run
        bank = sys.argv[2] if len(sys.argv) > 2 else None
        history_run(bank)

    elif cmd == 'suggest':
        from src.suggestions import run as suggest_run
        suggest_run()

    elif cmd == 'pay':
        from src.mark_paid import mark_paid
        if len(sys.argv) < 4:
            print("用法: python main.py pay <银行名> <账单月份>")
            print("示例: python main.py pay 邮储银行 2026-04")
        else:
            mark_paid(sys.argv[2], sys.argv[3])

    elif cmd == 'run':
        print("=" * 50)
        print("🔄 开始完整流程...")
        print("=" * 50)

        from src.fetcher import download_emails
        print("\n📧 步骤1/3: 下载账单邮件")
        download_emails()

        from src.parser import parse_all
        print("\n📊 步骤2/3: 解析账单")
        parse_all()

        from src.reminder import run as check_run
        print("\n🔔 步骤3/3: 检查还款日")
        check_run()

    elif cmd == 'help':
        print(__doc__)
    else:
        print(f"未知命令: {cmd}")
        print(__doc__)


if __name__ == '__main__':
    main()
