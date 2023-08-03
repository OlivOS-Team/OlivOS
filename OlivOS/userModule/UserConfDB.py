
import sqlite3
import threading
import os
import hashlib
import traceback
# import atexit
import gc
from concurrent.futures import ThreadPoolExecutor as PoolExecutor

DATABASE_SVN = 1
DATABASE_PATH = os.path.join(".","plugin","conf","UserConfAll.db")
DATABASE_SQL = {
# CREATE
    # 每个插件预先在总表中
    "create.table.master": """\
CREATE TABLE IF NOT EXISTS table_master{
    'hash_namespace'        TEXT        PRIMARY KEY,
    'str_namespace'         TEXT        UNIQUE,
    'time_last_update'      DATETIME    DEFAULT CURRENT_TIMESTAMP
};""",
    "create.table.namespace": """\
CREATE TABLE IF NOT EXISTS table_namespace_{namespace_hash}{
    'hash_key_basic'            TEXT,
    'str_key_conf_name'         TEXT,
    'raw_value'                 BLOB,
    (str_key_basic_hash, str_key_conf_name)     PRIMARY KEY
};""",
    # 创建一个触发器，当某个插件对应的命名空间有更新的时候，更新主表中对应插件的那一行
    "create.trigger.namespace": """\
CREATE TRIGGER IF NOT EXISTS trigger_namespace_{namespace_hash}
BEFORE INSERT ON table_namespace_{namespace_hash}
FOR EACH ROW
BEGIN
    UPDATE OR IGNORE table_master
    SET time_last_update = CURRENT_TIMESTAMP
    WHERE hash_namespace = {namespace_hash}
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

# pragma 元数据
    "pragma.get.version": """PRAGMA user_version ;""",
    "pragma.set.version": """PRAGMA user_version = {ver} ;""",

}

def get_nammespace_hash(namespace:str):
    if namespace == "unity":
        return "unity"
    return get_hash(namespace)

def get_conf_basic(config_type, platform, config_id, *args):
    return get_hash(config_type, platform, config_id, *args)

def get_hash(*data):
    if len(data) == 0:
        return "--NONEED--"
    sha1 = hashlib.sha1()
    sha1.update("-".join(map(str, data)).encode("utf-8"))
    return sha1.hexdigest()

class DataBaseAPI:
    class _sqlconn:
        # sql上下文管理实现
        def __init__(self, conn: sqlite3.Connection):
            # print('start')
            self.conn = conn
            self.cur = self.conn.cursor()

        def __enter__(self):
            return self.cur

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is not None:
                traceback.print_exc()
                self.cur.close()
                self.conn.rollback()
            self.cur.close()
            self.conn.commit()

    def __init__(self, proc_log, max_thread=None, timeout=1):
        self.proc_log = proc_log
        self.timeout = timeout
        self.cache = {}
        self.namespace_list = []
        self._thread_pool = PoolExecutor(max_thread, initializer=self.__init_thread)
        self._conn_all = []
        self._init_database


    def __init_thread(self):
        "线程池中每个线程的初始化过程，进行数据库连接"
        data = threading.local()
        data.conn = sqlite3.connect(database=DATABASE_PATH, timeout=self.timeout)
        self._conn_all.append(data.conn)

    def __run_sql_thread(self, script_list):
        "具体的运行函数，传入的是形如 `[(sql, param), (sql, param), (sql, param)]` 的操作指令队列"
        data = threading.local()
        with self._sqlconn(data.conn) as cur:
            res = {}
            for data in script_list:
                if isinstance(data, str):
                    sql = data
                    cur.execute(sql)
                    res[sql] = cur.fetchall()
                else:
                    sql = data[0]
                    param = data[1]
                    cur.execute(sql, param)
                    res[(sql, param)] = cur.fetchall()
            return res

    def _init_database(self):
        "对数据库进行总体初始化"
        # TODO
        sql_list = [
            DATABASE_SQL["create.table.master"],
            DATABASE_SQL["select.master.namespace"],
            DATABASE_SQL["pragma.get.version"],
        ]
        res = self._execmany(sql_list)
        namespace_sql = res[DATABASE_SQL["select.master.namespace"]]
        svn = res[DATABASE_SQL["pragma.get.version"]]
        if svn != DATABASE_SVN:
            if svn == 0:
                self._exec(DATABASE_SQL["pragma.set.version"], DATABASE_SVN)
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
            namespace_hash = get_nammespace_hash(namespace)
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

    def _exec(self, sql, param=None, *, blocking=True):
        """
        低层次接口函数，直接运行对应的 sql 指令，完成数据库操作
        
        如果 `blocking=False` 则直接返回 concurrent.futures.Future 对象
        """
        r = self._thread_pool.submit(self.__run_sql_thread, [(sql, param)])
        if blocking:
            return r.result(self.timeout)[(sql, param)]
        else:
            return r

    def clean_cache(self):
        "清空 cache 中的内容，同时运行垃圾回收（由于是直接赋值然后去垃圾回收，属于原子操作，不用管多线程）"
        self.cache = {}
        gc.collect()

    def stop(self):
        self._thread_pool.shutdown()
        for conn in self._conn_all:
            conn.close()
    
    def get_config(self, key: str, basic_hashed=None, namespace=None, *, default_value=None):
        """
        最基本的配置项读取操作，返回对应的键值
        
        `key`: 具体存储的配置项名称 (应为字符串)
        `basic_hashed`: 经过 sha1 处理的基本用户信息，如果不存在用户信息，则为常量 "--NONEED--"
                        默认为 --NONEED--
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则应为 "unity"
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 unity
        `dafault_value`: 如果存在，则当该配置项不存在时，返回这个值（注意：必须写成 default_value=xxx 的形式）
        """
        if basic_hashed is None:
            basic_hashed = "--NONEED--"
        if namespace is None:
            namespace = "unity"
        
        namespace_hashed = get_nammespace_hash(namespace)
        cache_key = get_hash(namespace_hashed, basic_hashed, key)
        # 缓存的键通过 命名空间+basichash+键名计算得出，如果存在则直接返回
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        sql_this = DATABASE_SQL["select.namespace.conf"].format(namespace_hash=namespace_hashed)
        param = {
            "hash_key_basic": basic_hashed,
            "str_key_conf_name": key,
        }
        
        res = self._exec(sql_this, param)
        if len(res) == 0:
            return default_value
        else:
            self.cache[cache_key] = res[0][0]
            return res[0][0]

    def set_config(self, key: str, value, basic_hashed=None, namespace=None):
        """
        最基本的配置项写入操作，返回对应的键值
        
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值
        `basic_hashed`: 经过 sha1 处理的基本用户信息，如果不存在用户信息，则为常量 "--NONEED--"
                        默认为 --NONEED--
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        """
        if basic_hashed is None:
            basic_hashed = "--NONEED--"
        if namespace is None:
            namespace = "unity"
        
        namespace_hashed = get_nammespace_hash(namespace)
        cache_key = get_hash(namespace_hashed, basic_hashed, key)

        self.cache[cache_key] = value

        sql_this = DATABASE_SQL["insert.namespace"].format(namespace_hash=namespace_hashed)
        param = {
            "hash_key_basic": basic_hashed,
            "str_key_conf_name": key,
            "raw_value": value,
        }
        self._exec(sql_this, param)
        return True

    def get_user_config(self, platform, user_id, key, namespace=None, *other_arg, default_value=None):
        """
        读取对应用户配置项
        
        `platform`: 用户所在平台
        `user_id`: 用户id
        `key`: 具体存储的配置项名称 (应为字符串)
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        `*other_arg`: 如果有其他需要被记录的键名，一并写在这里，会计算入哈希值中
        `dafault_value`: 如果存在，则当该配置项不存在时，返回这个值（注意：必须写成 default_value=xxx 的形式）
        """
        basic_hash = get_conf_basic("user", platform, user_id, *other_arg)
        return self.get_config(key, basic_hash, namespace, default_value=default_value)

    def get_group_config(self, platform, group_id, key, namespace=None, *other_arg, default_value=None):
        """
        读取对应群组配置项
        
        `platform`: 群组所在平台
        `group_id`: 群组id
        `key`: 具体存储的配置项名称 (应为字符串)
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        `*other_arg`: 如果有其他需要被记录的键名，一并写在这里，会计算入哈希值中
        `dafault_value`: 如果存在，则当该配置项不存在时，返回这个值（注意：必须写成 default_value=xxx 的形式）
        """
        basic_hash = get_conf_basic("group", platform, group_id, *other_arg)
        return self.get_config(key, basic_hash, namespace, default_value=default_value)

    def get_basic_config(self, key, namespace=None, *, default_value=None):
        """
        读取插件自身配置项（与平台和用户群组无关的配置）

        `key`: 具体存储的配置项名称 (应为字符串)
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        `dafault_value`: 如果存在，则当该配置项不存在时，返回这个值（注意：必须写成 default_value=xxx 的形式）
        """
        basic_hash = "--NONEED--"
        return self.get_config(key, basic_hash, namespace, default_value=default_value)

    def set_user_config(self, platform, user_id, key, value, namespace=None, *other_arg):
        """
        设置对应用户配置项
        
        `platform`: 用户所在平台
        `user_id`: 用户id
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        `*other_arg`: 如果有其他需要被记录的键名，一并写在这里，会计算入哈希值中
        """
        basic_hash = get_conf_basic("user", platform, user_id, *other_arg)
        return self.set_config(key, value, basic_hash, namespace)

    def set_group_config(self, platform, group_id, key, value, namespace=None, *other_arg):
        """
        设置对应群组配置项
        
        `platform`: 群组所在平台
        `group_id`: 群组id
        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        `*other_arg`: 如果有其他需要被记录的键名，一并写在这里，会计算入哈希值中
        """
        basic_hash = get_conf_basic("group", platform, group_id, *other_arg)
        return self.set_config(key, value, basic_hash, namespace)


    def set_basic_config(self, key, value, namespace=None):
        """
        设置插件自身配置项（与平台和用户群组无关的配置）

        `key`: 具体存储的配置项名称 (应为字符串)
        `value`: 具体存储的配置项值
        `namespace`: 如果这个配置项希望被其他插件共同使用（如是否为管理员等权限），则留空为 None
                     否则此处应当填写当前插件 app.json 中的命名空间
                     默认为 None
        """
        basic_hash = "--NONEED--"
        return self.set_config(key, value, basic_hash, namespace)

