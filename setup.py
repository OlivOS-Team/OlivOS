# -*- encoding: utf-8 -*-
'''
   ____  _   ____________  ________________
  / __ \/ | / / ____/ __ \/  _/ ____/ ____/
 / / / /  |/ / __/ / / / // // /   / __/   
/ /_/ / /|  / /___/ /_/ // // /___/ /___   
\____/_/ |_/_____/_____/___/\____/_____/   

@File      :   setup.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2021, OlivOS-Team
@Desc      :   None
'''
import setuptools

with open('README.md', 'r') as f:
  long_description = f.read()
with open('requirements.txt', 'r') as f:
  install_requires = f.read().split('\n')

setuptools.setup(name='olivos',
    version='0.9.3-fix1',
    description='OlivOS - Witness Union',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='OlivOS-Team',
    author_email='lunzhipenxil@gmail.com',
    url='https://github.com/OlivOS-Team/OlivOS',
    install_requires=[],
    license='AGPLv3 License',
    packages=setuptools.find_packages(),
    classifiers=[
        'Operating System :: OS Independent',
        'License :: OSI Approved :: GNU Affero General Public License v3',
        'Programming Language :: Python :: 3'
    ],
)

