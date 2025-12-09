# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   main.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2025, OlivOS-Team
@Desc      :   None
'''

# here put the import lib

import os

import OlivOS

if __name__ == '__main__':
    if not os.path.exists('./conf'):
        os.makedirs('./conf')
    OlivOS.bootAPI.Entity(
        basic_conf = './conf/basic.json',
        patch_conf = './conf/config.json'
    ).start()
