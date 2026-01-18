import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# 构建命令 - 与平台无关
cmd = [sys.executable, '-m', 'flake8', './']


def main():
    parser = argparse.ArgumentParser(description='运行Flake8检查')
    parser.add_argument('--exit-zero', action='store_true', help='无退出模式')
    args = parser.parse_args()
    log_file = Path('flake8_output.log')
    if args.exit_zero:
        cmd.append('--exit-zero')
    try:
        print(f'[{datetime.now().isoformat()}] 开始Flake8检查...')
        # 执行，捕获所有输出
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        # 准备要写入的内容
        with open(log_file, 'w', encoding='utf-8') as f:
            if result.stdout:
                f.write(result.stdout)
                print(result.stdout, end='')

            # if result.stderr:
            #     f.write("\n[标准错误输出]\n")
            #     f.write(result.stderr)

        if result.returncode == 0:
            print(f'检查完成。详细结果已输出至: {log_file.absolute()}')
        else:
            print(f'检查异常，返回码: {result.returncode}')
        return result.returncode
    except FileNotFoundError:
        print('错误: 未找到flake8。请确保已在当前Python环境中安装。')
        return 1
    except Exception as e:
        print(f'执行过程中发生未知错误: {e}')
        return 1


if __name__ == '__main__':
    returncode = main()
    sys.exit(returncode)
