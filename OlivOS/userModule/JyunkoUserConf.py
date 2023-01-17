# -*- encoding: utf-8 -*-
'''
     ██╗██╗   ██╗██╗   ██╗███╗   ██╗██╗  ██╗ ██████╗ 
     ██║╚██╗ ██╔╝██║   ██║████╗  ██║██║ ██╔╝██╔═══██╗
     ██║ ╚████╔╝ ██║   ██║██╔██╗ ██║█████╔╝ ██║   ██║
██   ██║  ╚██╔╝  ██║   ██║██║╚██╗██║██╔═██╗ ██║   ██║
╚█████╔╝   ██║   ╚██████╔╝██║ ╚████║██║  ██╗╚██████╔╝
 ╚════╝    ╚═╝    ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝ ╚═════╝ 
                                                     
    Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    https://www.apache.org/licenses/LICENSE-2.0
    Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
import pickle
import os

FILE_NAME = '.'+os.sep+'user'+os.sep+'UserConf.dat'
        
def writeInto(_file:str,_obj:any,_mode='wb'):  # type: ignore    
    """写入文件"""
    try:
        os.mkdir('user')
    except FileExistsError:
        pass
    file = open(_file,_mode)
    pickle.dump(_obj,file)
    file.close()

def readOut(_file:str,_mode='rb'):
    """读取文件"""
    try:
        os.mkdir('user')
    except FileExistsError:
        pass
    file = open(_file,_mode)
    tmpOut = pickle.load(file)
    file.close()
    return tmpOut

def setUserConf(user_id:'int|str',keyConf:str,val:any):  # type: ignore    
    """写入用户配置
    
    @user_id : int|str
        待传入的用户ID.
    @keyConf : str
        配置项.
    @val : any
        配置项对应值.

    >>> setUserConf(plugin_event.data.user_id,"jrrp",0)
    """
    if not os.path.exists(FILE_NAME):
        originalConf = [{"uid":{}},{"gid":{}}]
        writeInto(FILE_NAME,originalConf)
    tmpConf = readOut(FILE_NAME)
    try:
        tmpLst = tmpConf[0]["uid"][str(user_id)]
    except KeyError:
        tmpLst = tmpConf[0]["uid"][str(user_id)] = {}
    tmpLst[keyConf] = val
    # TODO(简律纯/2022年12月9日): 多配置项的更改.
    writeInto(FILE_NAME,tmpConf)

def getUserConf(user_id:'int|str',keyConf:str,perhapsVal=None) -> any:  # type: ignore
    """获取用户配置
    
    @user_id : int|str
        待传入的用户ID.
    @keyConf : str
        配置项.
    @[opt=perhapsVal] : any
        配置项取None时的备选参数.

    >>> setUserConf(plugin_event.data.user_id,"jrrp",100)
    >>> print(getUserConf(plugin_event.data.user_id,"jrrp",0))
    100
    """
    if not os.path.exists(FILE_NAME):
        originalConf = [{"uid":{}},{"gid":{}}]
        writeInto(FILE_NAME,originalConf)
    tmpConf = readOut(FILE_NAME)
    # TODO(简律纯/2022年12月9日): 多配置项的获取.
    try:
        return tmpConf[0]["uid"][str(user_id)][keyConf]
    except KeyError:
        return perhapsVal
    
def setGroupConf(group_id:'int|str',keyConf:str,val:any):  # type: ignore 
    """写入群配置
    
    @group_id : int|str
        待传入的群组ID.
    @keyConf : str
        配置项.
    @val : any
        配置项对应值.

    >>> setUserConf(plugin_event.data.user_id,"jrrp",0)
    """   
    if not os.path.exists(FILE_NAME):
        originalConf = [{"uid":{}},{"gid":{}}]
        writeInto(FILE_NAME,originalConf)
    tmpConf = readOut(FILE_NAME)
    try:
        tmpLst = tmpConf[0]["gid"][str(group_id)]
    except KeyError:
        tmpLst = tmpConf[0]["gid"][str(group_id)] = {}
    tmpLst[keyConf] = val
    # TODO(简律纯/2022年12月9日): 多配置项的更改.
    writeInto(FILE_NAME,tmpConf)

def getGroupConf(group_id:'int|str',keyConf:str,perhapsVal=None) -> any:  # type: ignore
    """获取群组配置
    
    @group_id : int|str
        待传入的群组ID.
    @keyConf : str
        配置项.
    @[opt=perhapsVal] : any
        配置项取None时的备选参数.

    >>> setGroupConf(plugin_event.data.group_id,"许可",True)
    >>> print(getGroupConf(plugin_event.data.group_id,"许可",0))
    True
    """
    if not os.path.exists(FILE_NAME):
        originalConf = [{"uid":{}},{"gid":{}}]
        writeInto(FILE_NAME,originalConf)
    tmpConf = readOut(FILE_NAME)
    # TODO(简律纯/2022年12月9日): 多配置项的获取.
    try:
        return tmpConf[1]["gid"][str(group_id)][keyConf]
    except KeyError:
        return perhapsVal
