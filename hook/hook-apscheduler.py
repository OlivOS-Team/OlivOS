from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

# APScheduler 3.10.1 运行时通过 pkg_resources 读取入口点及依赖元数据。
datas = copy_metadata('APScheduler', recursive=True) + collect_data_files('pytz') + collect_data_files('tzdata')
# zoneinfo 通过 importlib.resources 动态导入各地区的数据包。
hiddenimports = ['apscheduler.jobstores.memory', 'apscheduler.triggers.date'] + collect_submodules('tzdata')
