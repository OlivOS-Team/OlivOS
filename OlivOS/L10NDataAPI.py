# -*- encoding: utf-8 -*-
'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/L10NDataAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2023, OlivOS-Team
@Desc      :   None
'''

import OlivOS

formatOffsetLimit = 10
flagL10NSelection = 'zh-CN'
flagL10NSelectionDefault = 'en-US'

dictL10NSTR = {
    'en-US': {
        'diagnoseAPI_0001': 'Welcome to OlivOS {0}',
        'diagnoseAPI_0002': 'OlivOS diagnose logger [{0}] is running',
        'accountAPI_0001': 'init account from default ... done',
        'accountAPI_0002': 'init account from [{0}] ... done',
        'accountAPI_0003': 'init account from [{0}] ... failed',
        'accountAPI_0004': 'generate [{0}] account [{1}] as [{2}] ... done',
        'accountAPI_0005': 'generate account ... all done',
        'pluginAPI_0001': 'OlivOS plugin shallow [{0}] is running',
        'pluginAPI_0002': 'OlivOS plugin shallow [{0}] will restart',
        'pluginAPI_0003': 'OlivOS plugin shallow [{0}] call restart',
        'pluginAPI_0004': 'OlivOS plugin shallow [{0}] call check update',
        'pluginAPI_0005': 'Account [{0}] not found, please check your account config',
        'pluginAPI_0006': 'event [{0}] call plugin [{1}] done',
        'pluginAPI_0007': 'event [{0}] call blocked by plugin [{1}]',
        'pluginAPI_0008': 'OlivOS plugin [{0}] call [{1}] failed: {2}\n{3}',
        'pluginAPI_0009': 'OlivOS plugin [{0}] call [{1}] done',
        'pluginAPI_0010': 'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}\n{3}',
        'pluginAPI_0011': 'OlivOS plugin [{0}] is support for old OlivOS version {1}',
        'pluginAPI_0012': 'is support for old OlivOS version {0}',
        'pluginAPI_0013': 'OlivOS plugin [{0}] is skiped by OlivOS plugin shallow [{1}]: {2}',
        'pluginAPI_0014': 'OlivOS plugin [{0}] is loaded by OlivOS plugin shallow [{1}]',
        'pluginAPI_0015': 'Total count [{0}] OlivOS plugin is loaded by OlivOS plugin shallow [{1}]',
        'onebotV12LinkServerAPI_0001': 'OlivOS onebotV12 link server [{0}] is running',
        'onebotV12LinkServerAPI_0002': 'OlivOS onebotV12 link server [{0}] websocket link will retry in {1}s',
        'onebotV12LinkServerAPI_0003': 'OlivOS onebotV12 link server [{0}] websocket link error',
        'onebotV12LinkServerAPI_0004': 'OlivOS onebotV12 link server [{0}] websocket link close',
        'onebotV12LinkServerAPI_0005': 'OlivOS onebotV12 link server [{0}] websocket link start',
        'onebotV12LinkServerAPI_0006': 'OlivOS onebotV12 link server [{0}] websocket link lost',
        'hackChatLinkServerAPI_0001': 'OlivOS hackChat link server [{0}] is running',
        'hackChatLinkServerAPI_0002': 'OlivOS hackChat link server [{0}] websocket link will retry in {1}s',
        'hackChatLinkServerAPI_0003': 'OlivOS hackChat link server [{0}] websocket link error',
        'hackChatLinkServerAPI_0004': 'OlivOS hackChat link server [{0}] websocket link close',
        'hackChatLinkServerAPI_0005': 'OlivOS hackChat link server [{0}] websocket link start',
        'hackChatLinkServerAPI_0006': 'OlivOS hackChat link server [{0}] websocket link lost',
    },
    'zh-CN': {
        'diagnoseAPI_0001': '欢迎使用 青果核心交互栈 OlivOS {0}',
        'diagnoseAPI_0002': 'OlivOS 日志组件 [{0}] 正在运作',
        'accountAPI_0001': '从默认配置装载账号 ... 完成',
        'accountAPI_0002': '从配置存档 [{0}] 装载账号 ... 完成',
        'accountAPI_0003': '从配置存档 [{0}] 装载账号 ... 失败',
        'accountAPI_0004': '进行 [{0}] 账号装载，从 [{1}] 至 [{2}] ... 完成',
        'accountAPI_0005': '进行账号装载 ... 全部完成',
        'pluginAPI_0001': 'OlivOS 插件组件 [{0}] 正在运作',
        'pluginAPI_0002': 'OlivOS 插件组件 [{0}] 即将重载',
        'pluginAPI_0003': 'OlivOS 插件组件 [{0}] 发起重载',
        'pluginAPI_0004': 'OlivOS 插件组件 [{0}] 发起更新检查',
        'pluginAPI_0005': '账号 [{0}] 未找到, 请检查你的账号配置',
        'pluginAPI_0006': '事件 [{0}] 调用插件 [{1}] 完成',
        'pluginAPI_0007': '事件 [{0}] 被插件 [{1}] 拦截，将终止后续插件处理',
        'pluginAPI_0008': 'OlivOS 插件 [{0}] 调用 [{1}] 失败: {2}\n{3}',
        'pluginAPI_0009': 'OlivOS 插件 [{0}] 调用 [{1}] 完成',
        'pluginAPI_0010': 'OlivOS 插件 [{0}] 被 OlivOS 插件组件 [{1}] 跳过: {2}\n{3}',
        'pluginAPI_0011': 'OlivOS 插件 [{0}] 专为旧版 OlivOS 版本 {1} 设计',
        'pluginAPI_0012': '专为旧版 OlivOS 版本 {0} 设计',
        'pluginAPI_0013': 'OlivOS 插件 [{0}] 被 OlivOS 插件组件 [{1}] 跳过: {2}',
        'pluginAPI_0014': 'OlivOS 插件 [{0}] 被 OlivOS 插件组件 [{1}] 加载',
        'pluginAPI_0015': '共 [{0}] 个 OlivOS 插件被 OlivOS 插件组件 [{1}] 加载',
        'onebotV12LinkServerAPI_0001': 'OlivOS onebotV12 连接服务组件 [{0}] 正在运作',
        'onebotV12LinkServerAPI_0002': 'OlivOS onebotV12 连接服务组件 [{0}] WebSocket 连接 将在{1}秒内重试',
        'onebotV12LinkServerAPI_0003': 'OlivOS onebotV12 连接服务组件 [{0}] WebSocket 连接 发生错误',
        'onebotV12LinkServerAPI_0004': 'OlivOS onebotV12 连接服务组件 [{0}] WebSocket 连接 已经关闭',
        'onebotV12LinkServerAPI_0005': 'OlivOS onebotV12 连接服务组件 [{0}] WebSocket 连接 已经启动',
        'onebotV12LinkServerAPI_0006': 'OlivOS onebotV12 连接服务组件 [{0}] WebSocket 连接 已经丢失',
        'hackChatLinkServerAPI_0001': 'OlivOS hackChat 连接服务组件 [{0}] 正在运作',
        'hackChatLinkServerAPI_0002': 'OlivOS hackChat 连接服务组件 [{0}] WebSocket 连接 将在{1}秒内重试',
        'hackChatLinkServerAPI_0003': 'OlivOS hackChat 连接服务组件 [{0}] WebSocket 连接 发生错误',
        'hackChatLinkServerAPI_0004': 'OlivOS hackChat 连接服务组件 [{0}] WebSocket 连接 已经关闭',
        'hackChatLinkServerAPI_0005': 'OlivOS hackChat 连接服务组件 [{0}] WebSocket 连接 已经启动',
        'hackChatLinkServerAPI_0006': 'OlivOS hackChat 连接服务组件 [{0}] WebSocket 连接 已经丢失',
    }
}
