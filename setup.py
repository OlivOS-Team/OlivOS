
# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/
@File      :   setup.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''

import setuptools

with open('README.md', 'r', encoding = 'utf-8') as f:
  long_description = f.read()

setuptools.setup(name='olivos',
    version='0.10.1',
    description='OlivOS - Witness Union',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='OlivOS-Team',
    author_email='lunzhipenxil@gmail.com',
    url='https://github.com/OlivOS-Team/OlivOS',
    install_requires=[
        'pyinstaller==3.5',
        'flask',
        'gevent',
        'psutil',
        'requests',
        'pybase64',
        'websockets',
        'websocket-client',
        'pillow',
        'lxml',
        'rsa',
        'requests_toolbelt',
        'pystray'
    ],
    license='AGPLv3 License',
    packages=setuptools.find_packages(),
    classifiers=[
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python :: 3'
    ],
)

