import re
import os
import pickle
import time
import uuid
from .. import API

'''
                        _               _  __    _
        /\             | |             | |/ /   | |
       /  \   _ __ ___ | |__   ___ _ __| ' / ___| |_ ___ _ __
      / /\ \ | '_ ` _ \| '_ \ / _ \ '__|  < / _ \ __/ _ \ '__|
     / ____ \| | | | | | |_) |  __/ |  | . \  __/ ||  __/ |
    /_/    \_\_| |_| |_|_.__/ \___|_|  |_|\_\___|\__\___|_|
    IO流包 by Dr.Amber
    问题反馈请加QQ：1761089294
    Email：amberketer@outlook.com

函数：IO_construct(self:API.Event,input_list:'list|tuple',plugin_name,default_mode:int = 2,default_max_time:int = 30,default_func:'function|None' = None)
入参               说明             默认值  默认值说明
self            -> 传入Event对象
input_list      -> 输入流列表
plugin_name     -> 插件名
mode            -> 匹配模式         2       全局模式
default_max_time-> 默认等候时间     30      30秒
default_func    -> 默认函数         None    无

mode：标识信息匹配模式
1   -> 群聊模式，接收同一群聊的所有信息
2   -> 全局模式，接收同一用户的群私聊信息
3   -> 群聊指定模式，接收同一群聊同一用户的信息

input_list：输入流集，元素为输入流单元

input_order：输入流单元，格式如下
{
    're':'此处为正则表达式',
    'max_time':'此处为数字',
    'function':'此处为函数'
}
键值对说明：
re：      标识输入流单元信息匹配格式，为正则表达式

max_time：标识输入流最高等待时间，单位为秒（second）

function：标识数据处理函数，为用户自定义函数，需自己编写。

'''


#此处以下定义IO流方法
def IO_construct(self:API.Event,input_list:'list|tuple',plugin_name,mode:int = 2,default_max_time:int = 30,default_func:'function|None' = None):
    mode = mode
    string:str = self.data.message
    user_id:str = str(self.data.user_id)
    platform = self.platform['platform']
    group = None
    if 'host_id' in self.data.__dict__:            
        group = str(self.data.host_id)
    if 'group_id' in self.data.__dict__ :
        group = str(self.data.group_id)
    data_path = 'plugin/tmp/Input/{}_input_log.pickle'.format(plugin_name)
    if not os.path.exists("plugin/tmp/Input"):  #检验数据文件与目录是否存在
        os.mkdir("plugin/tmp/Input")
    if not os.path.exists("plugin/tmp/Input/input_data"):
        os.mkdir("plugin/tmp/Input/input_data")
    if not os.path.exists(data_path):   
        init_data = {}
        with open(data_path,"wb",encoding="utf-8") as file:
            pickle.dump(init_data, file ,indent=4 ,ensure_ascii=False)     
    with open(data_path,"rb",encoding='utf8') as f:      #导入输入流缓存数据
        input_log:dict = pickle.load(f)
    if input_log.get(platform,None) == None:    #检查文件结构
        input_log[platform] = {}
    if input_log[platform].get('group',None) == None:
        input_log[platform]['group'] = {}
    if input_log[platform].get('private',None) == None:
        input_log[platform]['private'] = {}
    if input_log[platform]['private'].get(user_id,None) == None:
        input_log[platform]['private'][user_id] = {}
    if input_log[platform]['group'].get(group,None) == None:
        input_log[platform]['group'][group] = {}
    if input_log[platform]['group'][group].get(user_id,None) == None:
        input_log[platform]['group'][group][user_id] = {}
    if input_log[platform]['group'][group].get('all',None) == None:
        input_log[platform]['group'][group]['all'] = {}
    input_log_data = input_log.get(platform,{})
    #获取输入流缓存数据
    if mode == 1 and group:         #群，接收群内所有人的信息
        input_log_data = input_log_data.get('group',{}).get(group,{}).get("all",{})
    elif mode == 2:                 #User，接收指定用户的信息，可理解为全局接收
        if group:
            input_log_data = input_log_data.get('group',{}).get(group,{})
        else:
            input_log_data = input_log_data.get('private',{})
        input_log_data = input_log_data.get(user_id,None)
    elif mode == 3 and group:       #群内User，接收群内指定用户信息，可理解为群聊接收
        input_log_data = input_log_data.get('group',{}).get(group,{}).get(user_id,{})
    else:
        return
    if input_log_data == {}:      #如果不存在缓存记录，则执行首条输入流指令
        input_index = 0
    else:                         #如果存在，则执行相应索引对应的输入流指令
        input_index = input_log_data.get('index',0)       
    #执行输入流语句
    if input_index < len(input_list):
        input_order:dict = input_list[input_index]
        re_construct = input_order.get('re','')
        if re_construct != '':   #如果可作为正则表达式，则对传入数据进行匹配，否则，直接进入函数
            re_construct = re.compile(re_construct).match(string)
            if re_construct:
                if re_construct.end() == len(string):
                    re_string = re_construct.groups()
                else:
                    return
            else:
                return
        else:
            re_string = None
        input_func = input_order.get('function',default_func)
        max_time = input_order.get('max_time',default_max_time)
        last_time = input_log_data.get('time',time.time())
        dealt_time = time.time() - last_time
        cache_file_name = input_log_data.get('cache_file_name',str(uuid.uuid4()))
        cache_path = 'plugin/tmp/Input/input_data/{}.pickle'.format(cache_file_name)
        if dealt_time > max_time:    #检验是否超时
            return
        if not os.path.exists(cache_path):   
            init_data = {}
            with open(cache_path,"wb",encoding="utf-8") as file:
                pickle.dump(init_data, file,indent=4,ensure_ascii=False)     
        with open(cache_path,"rb",encoding='utf8') as f:      #导入输入流变量缓存数据
            input_cache_data:dict = pickle.load(f)
        if input_cache_data.get('input_history_data',None) == None:
            input_cache_data['input_history_data'] = []
        #将数据传入回调函数运算
        cache_data,new_index = input_func(plugin_event=self,string=string,re_string=re_string,cache_data=input_cache_data)
        this_input_data = {         #构建此次输入流数据
            'id':user_id,
            'group':group,
            'platform':platform,
            'string':string,
            're_string':re_string,
            'time':time.time()
        }                           #加入历史输入流数据序列
        cache_data['input_history_data'].append(this_input_data)
        if type(new_index) is not int:
            new_index = input_index + 1
        if 0 <= new_index < len(input_list):    #新序列合法，不结束输入流，缓存数据
                input_log_data['time'] = time.time()
                input_log_data['index'] = new_index
                input_log_data['cache_file_name'] = cache_file_name
                with open(data_path, "wb", encoding='utf8') as f:
                    pickle.dump(input_log, f, indent=4, ensure_ascii=False)
                with open(cache_path, "wb", encoding='utf8') as f:
                    pickle.dump(cache_data, f, indent=4, ensure_ascii=False)
                return
        #新序列不合法，结束输入流，删除缓存数据
        if mode == 1 and group:         #群，接收群内所有人的信息
            input_log[platform]['group'][group]['all'] = {}
        elif mode == 2:                 #User，接收指定用户的信息，可理解为全局接收
            if group:
                input_log[platform]['group'][group][user_id] = {}
            else:
                input_log[platform]['private'][user_id] = {}
        elif mode == 3 and group:       #群内User，接收群内指定用户信息，可理解为群聊接收
            input_log[platform]['group'][group][user_id] = {}
        with open(data_path, "wb", encoding='utf8') as f:
            pickle.dump(input_log, f, indent=4, ensure_ascii=False)
        os.remove(cache_path)
        return
    else:       #终止输入流并删除缓存
        if mode == 1 and group:         #群，接收群内所有人的信息
            input_log[platform]['group'][group]['all'] = {}
        elif mode == 2:                 #User，接收指定用户的信息，可理解为全局接收
            if group:
                input_log[platform]['group'][group][user_id] = {}
            else:
                input_log[platform]['private'][user_id] = {}
        elif mode == 3 and group:       #群内User，接收群内指定用户信息，可理解为群聊接收
            input_log[platform]['group'][group][user_id] = {}
        with open(data_path, "wb", encoding='utf8') as f:
            pickle.dump(input_log, f, indent=4, ensure_ascii=False)
        os.remove(cache_path)
        return
