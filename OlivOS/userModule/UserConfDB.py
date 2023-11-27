# -*- encoding: utf-8 -*-
r"""
 ________  ________  ___  ________       ___    ___ ________  ___  ___  ________  ___  ___
|\   __  \|\   __  \|\  \|\   ___  \    |\  \  /  /|\_____  \|\  \|\  \|\   __  \|\  \|\  \
\ \  \|\  \ \  \|\  \ \  \ \  \\ \  \   \ \  \/  / /\|___/  /\ \  \\\  \ \  \|\  \ \  \\\  \
 \ \   _  _\ \   __  \ \  \ \  \\ \  \   \ \    / /     /  / /\ \   __  \ \  \\\  \ \  \\\  \
  \ \  \\  \\ \  \ \  \ \  \ \  \\ \  \   \/  /  /     /  /_/__\ \  \ \  \ \  \\\  \ \  \\\  \
   \ \__\\ _\\ \__\ \__\ \__\ \__\\ \__\__/  / /      |\________\ \__\ \__\ \_______\ \_______\
    \|__|\|__|\|__|\|__|\|__|\|__| \|__|\___/ /        \|_______|\|__|\|__|\|_______|\|_______|
                                       \|___|/

    Copyright 2023 RainyZhou
    @Contact: thunderain_zhou@163.com

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import sqlite3
import threading
import os
import hashlib
import traceback
import gc
import pickle
from concurrent.futures import ThreadPoolExecutor as PoolExecutor


DATABASE_SVN = 1
DATABASE_PATH = os.path.join(".","plugin","conf","UserConfAll.db")
DATABASE_SQL = {
# CREATE
    # 每个插件预先在总表中
    "create.table.master": """\
CREATE TABLE IF NOT EXISTS table_master(
    hash_namespace        TEXT        PRIMARY KEY,
    str_namespace         TEXT        UNIQUE,
    time_last_update      DATETIME    DEFAULT CURRENT_TIMESTAMP
);""",
    "create.table.namespace": """\
CREATE TABLE IF NOT EXISTS table_namespace_{namespace_hash}(
    hash_key_basic            TEXT,
    str_key_conf_name         TEXT,
    raw_value                 BLOB,
    PRIMARY KEY (hash_key_basic, str_key_conf_name)
);""",
    # 创建一个触发器，当某个插件对应的命名空间有更新的时候，更新主表中对应插件的那一行
    "create.trigger.namespace": """\
CREATE TRIGGER IF NOT EXISTS trigger_namespace_{namespace_hash}
BEFORE INSERT ON table_namespace_{namespace_hash}
FOR EACH ROW
BEGIN
    UPDATE OR IGNORE table_master
    SET time_last_update = CURRENT_TIMESTAMP
    WHERE hash_namespace = "{namespace_hash}";
END;
""",

# INSERT (使用 replace 代替 update, 操作更加方便)
    "insert.table_master": """\
INSERT OR REPLACE INTO table_master(
    "hash_namespace", "str_namespace"
)
VALUES (:hash_namespace, :str_namespace);
""",
    "insert.namespace": """\
INSERT OR REPLACE INTO table_namespace_{namespace_hash}(
    "hash_key_basic", "str_key_conf_name", "raw_value"
)
VALUES (:hash_key_basic, :str_key_conf_name, :raw_value);
""",

# SELECT 查询语句
    "select.master.namespace":"""\
SELECT str_namespace FROM table_master
""",
    "select.namespace.conf": """\
SELECT raw_value FROM table_namespace_{namespace_hash}
WHERE hash_key_basic = :hash_key_basic AND str_key_conf_name = :str_key_conf_name
""",

# pragma 元数据（配置项数据库自身的版本号）
    "pragma.get.version": """PRAGMA user_version ;""",
    "pragma.set.version": """PRAGMA user_version = {ver} ;""",

}

def get_namespace_hash(namespace:"str|None"):
    if namespace == "unity" or namespace is None:
        return "unity"
    return get_hash(namespace)

def get_user_hash(platform: "str", user_id: "str|int", *args):
    return get_hash("user", platform, str(user_id), *args)

def get_group_hash(platform: "str", group_id: "str|int", host_id: "str|int|None"=None, *args):
    return get_hash("group", platform, str(group_id), str(host_id), *args)

def get_hash(*data):
    if len(data) == 0 or data[0] == "--NONEED--":
        return "--NONEED--"
    sha1 = hashlib.sha1()
    sha1.update("-".join(map(str, data)).encode("utf-8"))
    return sha1.hexdigest()

class DataBaseAPI:
    class _sqlconn:
        "sqlite 上下文管理实现"
        def __init__(self, conn: sqlite3.Connection, log=None):
            # print('start')
            self.conn = conn
            self.cur = self.conn.cursor()
            if log is None:
                log = print
            self.log = log

        def __enter__(self):
            return self.cur

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                # 如果sqlite发生错误，打印错误内容并回滚数据库连接
                err_str = traceback.format_exc()
                self.cur.close()
                self.conn.rollback()
                self.log(4, f"配置数据库发生错误： {err_str}")
                return False
            self.cur.close()
            self.conn.commit()

    def __init__(self, proc_log, max_thread=None, timeout=1):
        self.proc_log = proc_log
        self.timeout = timeout
        self.cache = {}
        self.namespace_list = []
        self._thread_pool = PoolExecutor(max_thread, initializer=self.__init_thread)
        self.__conn_all = {}
        self._init_database()
        # atexit.register(self.stop)


    def __init_thread(self):
        "线程池中每个线程的初始化过程，进行数据库连接"
        name = threading.current_thread().name
        # 为方便在主线程一并关闭所有连接 check_same_thread 设为 False
        conn= sqlite3.connect(database=DATABASE_PATH, timeout=self.timeout, check_same_thread=False)
        self.__conn_all[name] = conn
        # self.proc_log(0, f"thread init <{name}>")

    def __run_sql_thread(self, script_list):
        "具体的运行函数，传入的是形如 `[(sql, param), (sql, param), (sql, param)]` 的操作指令队列"
        name = threading.current_thread().name
        conn = self.__conn_all[name]
        with self._sqlconn(conn, self.proc_log) as cur:
            res = {}
            for data in script_list:
                # self.proc_log(0, str(data))
                if isinstance(data, str):
                    sql = data
                    cur.execute(sql)
                    res[sql] = cur.fetchall()
                else:
                    sql = data[0]
                    param = data[1]
                    cur.execute(sql, param)
                    res[str((sql, param))] = cur.fetchall()
            return res

    def _init_database(self):
        "对数据库进行总体初始化"
        sql_list = [
            DATABASE_SQL["create.table.master"],
            DATABASE_SQL["select.master.namespace"],
            DATABASE_SQL["pragma.get.version"],
        ]
        res = self._execmany(sql_list)
        namespace_sql = res[DATABASE_SQL["select.master.namespace"]]
        svn = res[DATABASE_SQL["pragma.get.version"]][0][0]
        if svn != DATABASE_SVN:
            if svn == 0:
                # svn 不存在，为新建的sqlite数据库
                self._exec(DATABASE_SQL["pragma.set.version"].format(ver=DATABASE_SVN))
            else:
                self.proc_log(3, "用户自定义数据库版本不符合，数据库版本为{0}，OlivOS中所需版本为{1}".format(svn, DATABASE_SVN))
        for i in namespace_sql:
            self.namespace_list.append(i[0])
        self._init_namespace()

    def _init_namespace(self, namespace=None):
        "对每个 namespace 进行分别初始化"
        if namespace is None:
            namespace = "unity"
            namespace_hash = "unity"
        else:
            namespace_hash = get_namespace_hash(namespace)
        if namespace in self.namespace_list:
            return True

        sql_list = [
            DATABASE_SQL["create.table.namespace"].format(namespace_hash=namespace_hash),
            DATABASE_SQL["create.trigger.namespace"].format(namespace_hash=namespace_hash),
            (DATABASE_SQL["insert.table_master"], {"hash_namespace": namespace_hash, "str_namespace": namespace})
        ]
        self._execmany(sql_list)
        self.namespace_list.append(namespace)
        return True

    def _execmany(self, sql_list):
        """
        低层次接口函数，一次性运行多个 sql 指令
        """
        r = self._thread_pool.submit(self.__run_sql_thread, sql_list)
        return r.result(self.timeout)

    def _exec(self, sql, param=None):
        """
        低层次接口函数，直接运行对应的 sql 指令，完成数据库操作
        """
        # self.proc_log(0, f"{sql}, {param}")
        if param is None:
            r = self._thread_pool.submit(self.__run_sql_thread, [sql,])
            return r.result(self.timeout)[sql]
        else:
            r = self._thread_pool.submit(self.__run_sql_thread, [(sql, param)])
            return r.result(self.timeout)[str((sql, param))]
        # else:
        #     return r

    def clean_cache(self):
        "清空 cache 中的内容，同时运行垃圾回收（由于是直接赋值然后去垃圾回收，属于原子操作，不用管多线程）"
        self.cache = {}
        gc.collect()

    def stop(self):
        self._thread_pool.shutdown()
        for conn in self.__conn_all.values():
            conn.close()

    def get_config(self, namespace: "str | None", key: "str", basic_hashed: "str | None" =None,  default_value=None, pkl=False):
        """
        最基本的配置项读取操作，返回对应的键值

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则填写 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        
        `key`: 具体存储的配置项名称 (应为字符串)

        `basic_hashed`: 经过 sha1 处理的基本用户信息，如果不存在用户信息，则填写 None
            具体的计算函数应当使用当前模块给定函数：
            - 用户哈希： OlivOS.userModule.UserConfDB.get_user_hash(platform, user_id)
            - 群组哈希： OlivOS.userModule.UserConfDB.get_group_hash(platform, group_id, host_id=None)
        
        `default_value`: 如果存在，则当该配置项不存在时，返回这个值 默认为 `None`
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        if basic_hashed is None:
            basic_hashed = "--NONEED--"
        if namespace is None:
            namespace = "unity"

        namespace_hashed = get_namespace_hash(namespace)
        cache_key = get_hash(namespace_hashed, basic_hashed, key)
        # 缓存的键通过 命名空间+basichash+键名计算得出，如果存在则直接返回
        res = self.cache.get(cache_key, None)
        if res is not None:
            if pkl:
                return pickle.loads(res)
            else:
                return res

        sql_this = DATABASE_SQL["select.namespace.conf"].format(namespace_hash=namespace_hashed)
        param = {
            "hash_key_basic": basic_hashed,
            "str_key_conf_name": key,
        }

        res = self._exec(sql_this, param)
        if len(res) == 0:
            return default_value
        else:
            val_raw = res[0][0]
            self.cache[cache_key] = val_raw
            if pkl:
                return pickle.loads(val_raw)
            else:
                return val_raw

    def set_config(self, namespace: "str | None", key: "str", value, basic_hashed: "str | None"=None, pkl=False):
        """
        最基本的配置项写入操作，返回对应的键值

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则配置为 None
                    否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值

        `basic_hashed`: 经过 sha1 处理的基本用户信息，如果不存在用户信息，则填写 None
                        默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        if basic_hashed is None:
            basic_hashed = "--NONEED--"

        namespace_hashed = get_namespace_hash(namespace)
        if namespace is None:
            namespace = "unity"

        cache_key = get_hash(namespace_hashed, basic_hashed, key)

        if pkl:
            val_raw = pickle.dumps(value)
        else:
            val_raw = value

        self.cache[cache_key] = val_raw

        sql_this = DATABASE_SQL["insert.namespace"].format(namespace_hash=namespace_hashed)
        param = {
            "hash_key_basic": basic_hashed,
            "str_key_conf_name": key,
            "raw_value": val_raw,
        }
        self._exec(sql_this, param)
        return True

    def get_user_config(self, namespace: "str|None", key: "str", platform: "str", user_id: "str|int", default_value=None, pkl=False):
        """
        读取对应用户配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `platform`: 用户所在平台
        `user_id`: 用户id
        `default_value`: 如果存在，则当该配置项不存在时，返回这个值，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = get_user_hash(
            platform=platform, 
            user_id=user_id,
        )
        return self.get_config(
            namespace=namespace,
            key=key,
            basic_hashed=basic_hash,
            default_value=default_value,
            pkl=pkl
        )

    def get_group_config(self, namespace: "str|None", key: "str", platform: "str", group_id: "str|int", host_id: "None|str|int"=None, default_value=None, pkl=False):
        """
        读取对应群组配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `platform`: 群组所在平台
        `group_id`: 群组id
        `host_id`: 如果如果该平台的群组有多个层级，则在这里设置，默认为 None
        `default_value`: 如果存在，则当该配置项不存在时，返回这个值，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = get_group_hash(
            platform=platform, 
            group_id=str(group_id), 
            host_id=str(host_id),
        )
        return self.get_config(
            namespace=namespace,
            key=key,
            basic_hashed=basic_hash,
            default_value=default_value,
            pkl=pkl
        )

    def get_basic_config(self, namespace: "str|None", key: "str", default_value=None, pkl=False):
        """
        读取插件自身配置项（与平台和用户群组无关的配置）

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `default_value`: 如果存在，则当该配置项不存在时，返回这个值，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = "--NONEED--"
        return self.get_config(
            namespace=namespace,
            key=key,
            basic_hashed=basic_hash,
            default_value=default_value,
            pkl=pkl
        )

    def set_user_config(self, namespace: "str|None", key: "str", value, platform: "str", user_id: "str|int", pkl=False):
        """
        设置对应用户配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值 (所有sqlite支持的数据类型)
        `platform`: 用户所在平台
        `user_id`: 用户id
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = get_user_hash(
            platform=platform, 
            user_id=str(user_id), 
        )
        return self.set_config(
            namespace=namespace,
            key=key,
            value=value,
            basic_hashed=basic_hash,
            pkl=pkl
        )

    def set_group_config(self, namespace: "str|None", key: "str", value, platform: "str", group_id: "str|int", host_id: "str|int|None"=None, pkl=False):
        """
        设置对应群组配置项

        `namespace`: 如果这个配置项希望与其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值 (所有sqlite支持的数据类型)
        `platform`: 群组所在平台
        `group_id`: 群组id
        `host_id`: 如果如果该平台的群组有多个层级，则在这里设置，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = get_group_hash(
            platform=platform, 
            group_id=str(group_id), 
            host_id=str(host_id), 
            # *other_arg
        )
        return self.set_config(
            namespace=namespace,
            key=key,
            value=value,
            basic_hashed=basic_hash,
            pkl=pkl
        )

    def set_basic_config(self, namespace: "str|None", key: "str", value, pkl=False):
        """
        设置插件自身配置项（与平台和用户群组无关的配置）

        `namespace`: 如果这个配置项希望与其他插件共同使用，则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值 (所有sqlite支持的数据类型)
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        basic_hash = "--NONEED--"
        return self.set_config(
            namespace=namespace,
            key=key,
            value=value,
            basic_hashed=basic_hash,
            pkl=pkl
        )

    def get_group_config_from_event(self, namespace: "str|None", key: "str", plugin_event, default_value=None, pkl=False):
        """
        读取消息事件对应群组的配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `plugin_event`: OlivOS 框架的事件对象
        `default_value`: 当该配置项不存在时，返回这个值，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        platfrom = plugin_event.platform["platform"]
        group_id = plugin_event.data.group_id
        host_id = plugin_event.data.host_id
        return self.get_group_config(
            namespace=namespace,
            key=key,
            platform=platfrom,
            group_id=group_id,
            host_id=host_id,
            default_value=default_value,
            pkl=pkl
        )

    def set_group_config_from_event(self, namespace: "str|None", key: "str", value, plugin_event, pkl=False):
        """
        设置消息事件对应群组的配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值 (所有sqlite支持的数据类型)
        `plugin_event`: OlivOS 框架的事件对象
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        platfrom = plugin_event.platform["platform"]
        group_id = plugin_event.data.group_id
        host_id = plugin_event.data.host_id
        return self.set_group_config(
            namespace=namespace,
            key=key,
            value=value,
            platform=platfrom,
            group_id=group_id,
            host_id=host_id,
            pkl=pkl
        )

    def get_user_config_from_event(self, namespace: "str|None", key: "str", plugin_event, default_value=None, pkl=False):
        """
        读取消息事件对应用户的配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `plugin_event`: OlivOS 框架的事件对象
        `default_value`: 当该配置项不存在时，返回这个值，默认为 None
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        platfrom = plugin_event.platform["platform"]
        user_id = plugin_event.data.user_id
        return self.get_user_config(
            namespace=namespace,
            key=key,
            platform=platfrom,
            user_id=user_id,
            default_value=default_value,
            pkl=pkl
        )
    def set_user_config_from_event(self, namespace: "str|None", key: "str", value, plugin_event, pkl=False):
        """
        设置消息事件对应用户的配置项

        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值 (所有sqlite支持的数据类型)
        `plugin_event`: OlivOS 框架的事件对象
        `pkl`: 是否采用 pickle 进行序列化和反序列化 (如果为真，可以通过这个方式保存很多python内置数据结构和实例类型) 默认为 False
        """
        platfrom = plugin_event.platform["platform"]
        user_id = plugin_event.data.user_id
        return self.set_user_config(
            namespace=namespace,
            key=key,
            value=value,
            platform=platfrom,
            user_id=user_id,
            pkl=pkl
        )

