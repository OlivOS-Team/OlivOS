# -*- encoding: utf-8 -*-
r'''
_______________________    ________________
__  __ \__  /____  _/_ |  / /_  __ \_  ___/
_  / / /_  /  __  / __ | / /_  / / /____ \
/ /_/ /_  /____/ /  __ |/ / / /_/ /____/ /
\____/ /_____/___/  _____/  \____/ /____/

@File      :   OlivOS/qqGuildv2WebhookServerAPI.py
@Author    :   lunzhiPenxil仑质
@Contact   :   lunzhipenxil@gmail.com
@License   :   AGPL
@Copyright :   (C) 2020-2026, OlivOS-Team
@Desc      :   None
'''

from gevent import pywsgi
from flask import Flask
from flask import current_app
from flask import request
from flask import Response

import http.client
import json
import multiprocessing
import os
import socket
import ssl
import threading
import time

import OlivOS

modelName = 'qqGuildv2WebhookServerAPI'

# 存活心跳与自探活间隔(秒)。服务一旦假死, 日志会彻底静默、外部只能看到超时,
# 排查时毫无线索; 因此定期打一行存活记录, 并用真实 HTTP(S) 请求自探活,
# 连续失败按错误级别记录, 让"静默假死"变得可见。
qqGuildv2WebhookHeartbeatInterval = 300.0
qqGuildv2WebhookSelfProbeTimeout = 5.0


def get_qqGuildv2_webhook_server_conf():
    tmp_server = dict(
        OlivOS.bootDataAPI.default_Conf['models']['OlivOS_qqGuildv2_webhook']['server']
    )
    for tmp_path in ['./conf/basic.json', './conf/config.json']:
        try:
            with open(tmp_path, 'r', encoding='utf-8') as tmp_f:
                tmp_conf = json.loads(tmp_f.read())
            tmp_patch = tmp_conf['models']['OlivOS_qqGuildv2_webhook']['server']
            if type(tmp_patch) is dict:
                tmp_server.update(tmp_patch)
        except Exception:
            pass
    return tmp_server


def get_qqGuildv2_webhook_xpath_prefix(xpath=None):
    tmp_xpath = '/OlivOSQQGuildv2Webhook'
    if xpath is not None and str(xpath).strip() != '':
        tmp_xpath = str(xpath).strip()
    if not tmp_xpath.startswith('/'):
        tmp_xpath = '/' + tmp_xpath
    if len(tmp_xpath) > 1 and tmp_xpath.endswith('/'):
        tmp_xpath = tmp_xpath[:-1]
    return tmp_xpath


def get_qqGuildv2_webhook_listen_scheme(cert_pairs=None):
    # 监听协议必须由「是否真的找到可用证书」决定,不能写死:
    # 否则证书缺失时会对外给出 https 地址,而服务端实际只提供 http。
    if type(cert_pairs) is list and len(cert_pairs) > 0:
        return 'https'
    return 'http'


def get_qqGuildv2_webhook_listen_url(appid=None):
    tmp_server = get_qqGuildv2_webhook_server_conf()
    tmp_xpath = get_qqGuildv2_webhook_xpath_prefix(tmp_server.get('xpath', None))
    tmp_appid = '{AppID}'
    if appid is not None and str(appid).strip() != '':
        tmp_appid = str(appid).strip()
    tmp_pairs = get_qqGuildv2_webhook_cert_pairs(
        certdir=tmp_server.get('certdir', None),
        fallback_cert=tmp_server.get('cert', None),
        fallback_key=tmp_server.get('key', None)
    )
    return '%s://%s:%s%s/%s' % (
        get_qqGuildv2_webhook_listen_scheme(tmp_pairs),
        tmp_server['host'],
        tmp_server['port'],
        tmp_xpath,
        tmp_appid
    )


qqGuildv2WebhookCertNameList = [
    # fullchain 优先:证书链必须带中间证书,否则开放平台侧 TLS 校验可能直接失败
    'fullchain.pem',
    'fullchain.crt',
    'certificate.pem',
    'certificate.crt',
    'cert.pem',
    'cert.crt',
    'server.pem',
    'server.crt'
]
qqGuildv2WebhookKeyNameList = [
    'key.pem',
    'privkey.pem',
    'private.pem',
    'server.key',
    'key.key',
    'privkey.key',
    'private.key'
]


def get_qqGuildv2_webhook_ssl_files(cert=None, key=None):
    if cert is None:
        return None, None
    tmp_cert = str(cert).strip()
    if tmp_cert == '' or not os.path.isfile(tmp_cert):
        return None, None
    tmp_key = tmp_cert
    if key is not None and str(key).strip() != '':
        tmp_key = str(key).strip()
    if not os.path.isfile(tmp_key):
        return None, None
    return os.path.abspath(tmp_cert), os.path.abspath(tmp_key)


def get_qqGuildv2_webhook_bot_ssl_dir(certdir, appid):
    tmp_dir = './conf/ssl'
    if certdir is not None and str(certdir).strip() != '':
        tmp_dir = str(certdir).strip()
    tmp_appid = str(appid).strip()
    return os.path.abspath(os.path.join(tmp_dir, tmp_appid))


def ensure_qqGuildv2_webhook_ssl_dir(appid, certdir=None):
    tmp_certdir = certdir
    if tmp_certdir is None:
        try:
            tmp_certdir = get_qqGuildv2_webhook_server_conf().get('certdir', None)
        except Exception:
            tmp_certdir = None
    tmp_path = get_qqGuildv2_webhook_bot_ssl_dir(tmp_certdir, appid)
    try:
        OlivOS.bootAPI.releaseDir(tmp_path)
    except Exception:
        try:
            if not os.path.exists(tmp_path):
                os.makedirs(tmp_path)
        except Exception:
            pass
    return tmp_path


def ensure_qqGuildv2_webhook_ssl_dirs(bot_info_dict, certdir=None):
    tmp_paths = []
    if type(bot_info_dict) is not dict:
        return tmp_paths
    for bot_hash in bot_info_dict:
        tmp_bot = bot_info_dict[bot_hash]
        if not OlivOS.qqGuildv2SDK.is_qqGuildv2_webhook_account(tmp_bot):
            continue
        try:
            tmp_paths.append(ensure_qqGuildv2_webhook_ssl_dir(tmp_bot.id, certdir=certdir))
        except Exception:
            continue
    return tmp_paths


def find_qqGuildv2_webhook_ssl_pair_in_dir(bot_dir):
    if bot_dir is None or not os.path.isdir(str(bot_dir)):
        return None, None
    tmp_cert = None
    tmp_key = None
    for tmp_name in qqGuildv2WebhookCertNameList:
        tmp_path = os.path.join(bot_dir, tmp_name)
        if os.path.isfile(tmp_path):
            tmp_cert = tmp_path
            break
    for tmp_name in qqGuildv2WebhookKeyNameList:
        tmp_path = os.path.join(bot_dir, tmp_name)
        if os.path.isfile(tmp_path):
            tmp_key = tmp_path
            break
    if tmp_cert is None or tmp_key is None:
        try:
            for tmp_name in os.listdir(bot_dir):
                tmp_path = os.path.join(bot_dir, tmp_name)
                if not os.path.isfile(tmp_path):
                    continue
                tmp_low = tmp_name.lower()
                if tmp_key is None and (
                    tmp_low.endswith('.key')
                    or 'priv' in tmp_low
                    or tmp_low in ['key.pem', 'key.key']
                ):
                    tmp_key = tmp_path
                elif tmp_cert is None and (
                    tmp_low.endswith('.crt')
                    or tmp_low.endswith('.cer')
                    or tmp_low.endswith('.pem')
                    or tmp_low.endswith('.cert')
                ):
                    if 'key' not in tmp_low and 'priv' not in tmp_low:
                        tmp_cert = tmp_path
        except Exception:
            pass
    if tmp_cert is not None and tmp_key is None:
        tmp_key = tmp_cert
    return get_qqGuildv2_webhook_ssl_files(tmp_cert, tmp_key)


def get_qqGuildv2_webhook_cert_pairs(
    certdir=None,
    fallback_cert=None,
    fallback_key=None,
    bot_info_dict=None
):
    tmp_pairs = []
    tmp_seen = set()

    def add_pair(cert, key):
        tmp_cert, tmp_key = get_qqGuildv2_webhook_ssl_files(cert, key)
        if tmp_cert is None:
            return
        tmp_flag = '%s|%s' % (tmp_cert, tmp_key)
        if tmp_flag in tmp_seen:
            return
        tmp_seen.add(tmp_flag)
        tmp_pairs.append((tmp_cert, tmp_key))

    def add_dir(bot_dir):
        tmp_cert, tmp_key = find_qqGuildv2_webhook_ssl_pair_in_dir(bot_dir)
        add_pair(tmp_cert, tmp_key)

    tmp_dir = './conf/ssl'
    if certdir is not None and str(certdir).strip() != '':
        tmp_dir = str(certdir).strip()
    if type(bot_info_dict) is dict:
        for bot_hash in bot_info_dict:
            try:
                tmp_appid = str(bot_info_dict[bot_hash].id)
            except Exception:
                continue
            add_dir(get_qqGuildv2_webhook_bot_ssl_dir(tmp_dir, tmp_appid))
    if os.path.isdir(tmp_dir):
        try:
            for tmp_name in os.listdir(tmp_dir):
                tmp_bot_dir = os.path.join(tmp_dir, tmp_name)
                if os.path.isdir(tmp_bot_dir):
                    add_dir(tmp_bot_dir)
        except Exception:
            pass
    add_pair(fallback_cert, fallback_key)
    return tmp_pairs


def get_qqGuildv2_webhook_cert_hostnames(cert_path):
    tmp_names = []
    try:
        from cryptography import x509
        with open(cert_path, 'rb') as tmp_f:
            tmp_cert = x509.load_pem_x509_certificate(tmp_f.read())
        try:
            tmp_san = tmp_cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            )
            tmp_names.extend(tmp_san.value.get_values_for_type(x509.DNSName))
        except Exception:
            pass
        try:
            tmp_cn_list = tmp_cert.subject.get_attributes_for_oid(
                x509.oid.NameOID.COMMON_NAME
            )
            for tmp_attr in tmp_cn_list:
                if tmp_attr.value not in tmp_names:
                    tmp_names.append(tmp_attr.value)
        except Exception:
            pass
    except Exception:
        pass
    return tmp_names


def build_qqGuildv2_webhook_ssl_context(cert_pairs):
    tmp_failed = []
    if type(cert_pairs) is not list or len(cert_pairs) == 0:
        return None, tmp_failed
    try:
        import ssl
    except Exception:
        return None, tmp_failed
    tmp_ctx_map = {}
    tmp_default_ctx = None
    for tmp_cert, tmp_key in cert_pairs:
        try:
            tmp_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            tmp_ctx.load_cert_chain(certfile=tmp_cert, keyfile=tmp_key)
        except Exception as error:
            tmp_failed.append('%s:%s' % (tmp_cert, type(error).__name__))
            continue
        if tmp_default_ctx is None:
            tmp_default_ctx = tmp_ctx
        for tmp_name in get_qqGuildv2_webhook_cert_hostnames(tmp_cert):
            tmp_ctx_map[str(tmp_name).lower()] = tmp_ctx
    if tmp_default_ctx is None:
        return None, tmp_failed

    def sni_callback(ssl_socket, server_hostname, ssl_context):
        if server_hostname is None:
            return None
        tmp_name = str(server_hostname).lower()
        if tmp_name in tmp_ctx_map:
            ssl_socket.context = tmp_ctx_map[tmp_name]
            return None
        tmp_parts = tmp_name.split('.')
        if len(tmp_parts) >= 2:
            tmp_wild = '*.' + '.'.join(tmp_parts[1:])
            if tmp_wild in tmp_ctx_map:
                ssl_socket.context = tmp_ctx_map[tmp_wild]
        return None

    try:
        tmp_default_ctx.sni_callback = sni_callback
    except Exception:
        pass
    return tmp_default_ctx, tmp_failed


class server(OlivOS.API.Proc_templet):
    def __init__(
        self,
        Proc_name,
        Flask_namespace,
        Flask_server_methods,
        Flask_host,
        Flask_port,
        tx_queue=None,
        debug_mode=False,
        logger_proc=None,
        scan_interval=0.001,
        dead_interval=16,
        Flask_server_xpath='/OlivOSQQGuildv2Webhook',
        Flask_ssl_cert=None,
        Flask_ssl_key=None,
        Flask_ssl_dir=None,
        bot_info_dict=None
    ):
        OlivOS.API.Proc_templet.__init__(
            self,
            Proc_name=Proc_name,
            Proc_type='qqGuildv2_webhook',
            scan_interval=scan_interval,
            dead_interval=dead_interval,
            rx_queue=None,
            tx_queue=tx_queue,
            logger_proc=logger_proc
        )
        self.Proc_config['Flask_namespace'] = Flask_namespace
        self.Proc_config['Flask_app'] = None
        self.Proc_config['Flask_name'] = Proc_name
        self.Proc_config['Flask_server_xpath'] = get_qqGuildv2_webhook_xpath_prefix(
            Flask_server_xpath
        )
        self.Proc_config['Flask_server_methods'] = Flask_server_methods
        self.Proc_config['Flask_server_host'] = Flask_host
        self.Proc_config['Flask_server_port'] = Flask_port
        self.Proc_config['Flask_ssl_cert'] = Flask_ssl_cert
        self.Proc_config['Flask_ssl_key'] = Flask_ssl_key
        tmp_ssl_dir = './conf/ssl'
        if Flask_ssl_dir is not None and str(Flask_ssl_dir).strip() != '':
            tmp_ssl_dir = str(Flask_ssl_dir).strip()
        self.Proc_config['Flask_ssl_dir'] = tmp_ssl_dir
        self.Proc_config['config'] = self.config_T(debug_mode)
        if bot_info_dict is None:
            bot_info_dict = {}
        self.Proc_data['bot_info_dict'] = bot_info_dict
        # WebUI 位于主进程，监听状态需要在线程和子进程模式下都可见。
        self._webhook_last_ready = multiprocessing.Value('d', 0.0)
        self._webhook_stopped = multiprocessing.Event()

    @property
    def webhook_online(self):
        last_ready = self._webhook_last_ready.value
        max_age = qqGuildv2WebhookHeartbeatInterval + qqGuildv2WebhookSelfProbeTimeout + 5
        return not self._webhook_stopped.is_set() and last_ready > 0 and time.monotonic() - last_ready <= max_age

    def on_terminate(self):
        self._webhook_stopped.set()
        self._webhook_last_ready.value = 0.0

    class config_T(object):
        def __init__(self, debug_mode):
            self.debug_mode = debug_mode

    def app(self):
        self.Proc_config['Flask_app'] = Flask(self.Proc_config['Flask_namespace'])
        return self.Proc_config['Flask_app']

    def _get_ssl_files(self):
        return get_qqGuildv2_webhook_ssl_files(
            self.Proc_config.get('Flask_ssl_cert', None),
            self.Proc_config.get('Flask_ssl_key', None)
        )

    def _get_cert_pairs(self):
        return get_qqGuildv2_webhook_cert_pairs(
            certdir=self.Proc_config.get('Flask_ssl_dir', None),
            fallback_cert=self.Proc_config.get('Flask_ssl_cert', None),
            fallback_key=self.Proc_config.get('Flask_ssl_key', None),
            bot_info_dict=self.Proc_data.get('bot_info_dict', None)
        )

    def _get_appid_list(self):
        tmp_appid_list = []
        bot_info_dict = self.Proc_data.get('bot_info_dict', None)
        if type(bot_info_dict) is not dict:
            return tmp_appid_list
        for bot_hash in bot_info_dict:
            try:
                tmp_appid = str(bot_info_dict[bot_hash].id).strip()
            except Exception:
                continue
            if tmp_appid == '' or tmp_appid in tmp_appid_list:
                continue
            tmp_appid_list.append(tmp_appid)
        return tmp_appid_list

    def _get_listen_url(self):
        tmp_prefix = '%s://%s:%s%s' % (
            get_qqGuildv2_webhook_listen_scheme(self._get_cert_pairs()),
            str(self.Proc_config['Flask_server_host']),
            str(self.Proc_config['Flask_server_port']),
            str(self.Proc_config['Flask_server_xpath'])
        )
        tmp_appid_list = self._get_appid_list()
        if len(tmp_appid_list) == 0:
            tmp_appid_list = ['<AppID>']
        return ' '.join([
            '%s/%s' % (tmp_prefix, tmp_appid)
            for tmp_appid in tmp_appid_list
        ])

    def _self_probe(self):
        # 必须做应用层探测: 服务假死时内核仍会替它完成 TCP 握手(连接 backlog),
        # 只探端口是发现不了的, 所以这里真发一次 HTTP(S) 请求并要求拿到响应。
        tmp_host = str(self.Proc_config['Flask_server_host'])
        if tmp_host in ['0.0.0.0', '::', '']:
            tmp_host = '127.0.0.1'
        tmp_port = int(self.Proc_config['Flask_server_port'])
        tmp_xpath = str(self.Proc_config['Flask_server_xpath'])
        tmp_scheme = get_qqGuildv2_webhook_listen_scheme(self._get_cert_pairs())
        tmp_conn = None
        try:
            if tmp_scheme == 'https':
                tmp_ctx = ssl.create_default_context()
                tmp_ctx.check_hostname = False
                tmp_ctx.verify_mode = ssl.CERT_NONE
                tmp_conn = http.client.HTTPSConnection(
                    tmp_host, tmp_port,
                    timeout=qqGuildv2WebhookSelfProbeTimeout,
                    context=tmp_ctx
                )
            else:
                tmp_conn = http.client.HTTPConnection(
                    tmp_host, tmp_port,
                    timeout=qqGuildv2WebhookSelfProbeTimeout
                )
            tmp_conn.request('GET', tmp_xpath)
            tmp_conn.getresponse()
            return True
        except Exception:
            return False
        finally:
            if tmp_conn is not None:
                try:
                    tmp_conn.close()
                except Exception:
                    pass

    def _run_watchdog(self):
        # 跑在独立线程里(未 monkey patch 的 gevent 下是真实线程): 即使服务线程的
        # hub 被阻塞, 这里仍能完成探测并经 logger 进程把日志写出去。
        tmp_start_time = time.monotonic()
        tmp_fail_count = 0
        while not self._webhook_stopped.wait(qqGuildv2WebhookHeartbeatInterval):
            healthy = self._self_probe()
            if self._webhook_stopped.is_set():
                return
            self._webhook_last_ready.value = time.monotonic() if healthy else 0.0
            if self.webhook_online:
                tmp_fail_count = 0
                self.log(
                    2,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS qqGuildv2 webhook server [{0}] alive [{1}]s handled [{2}] request(s)',
                        [
                            self.Proc_config['Flask_name'],
                            int(time.monotonic() - tmp_start_time),
                            int(self.Proc_data.get('rx_count', 0))
                        ],
                        modelName
                    )
                )
            else:
                tmp_fail_count += 1
                self.log(
                    3,
                    OlivOS.L10NAPI.getTrans(
                        'OlivOS qqGuildv2 webhook server [{0}] self check failed [{1}] time(s), '
                        'the service may be stuck',
                        [
                            self.Proc_config['Flask_name'],
                            tmp_fail_count
                        ],
                        modelName
                    )
                )

    def _json_response(self, payload_obj, status=200):
        return Response(
            json.dumps(obj=payload_obj),
            status=status,
            mimetype='application/json'
        )

    def _ack_response(self):
        return Response(
            OlivOS.qqGuildv2SDK.PAYLOAD.sendWebhookAck().dump(),
            status=200,
            mimetype='application/json'
        )

    def _unauthorized_response(self, reason):
        self.log(
            3,
            OlivOS.L10NAPI.getTrans(
                'OlivOS qqGuildv2 webhook server [{0}] auth failed [{1}]',
                [
                    self.Proc_config['Flask_name'],
                    str(reason)
                ],
                modelName
            )
        )
        return Response('', status=401)

    def _get_bot_info_by_appid(self, appid):
        if appid is None:
            return None
        tmp_appid = str(appid)
        if tmp_appid == '':
            return None
        bot_info_dict = self.Proc_data.get('bot_info_dict', {})
        if type(bot_info_dict) is not dict:
            return None
        for bot_hash in bot_info_dict:
            bot_info = bot_info_dict[bot_hash]
            try:
                if str(bot_info.id) == tmp_appid:
                    return bot_info
            except Exception:
                continue
        return None

    def set_config(self):
        with self.Proc_config['Flask_app'].app_context():
            tmp_xpath = self.Proc_config['Flask_server_xpath']

            @current_app.route(
                tmp_xpath,
                methods=self.Proc_config['Flask_server_methods'],
                strict_slashes=False
            )
            def Flask_server_func():
                return self._handle_webhook_request()

            @current_app.route(
                tmp_xpath + '/<appid>',
                methods=self.Proc_config['Flask_server_methods'],
                strict_slashes=False
            )
            def Flask_server_func_appid(appid):
                return self._handle_webhook_request(path_appid=appid)

    def _handle_webhook_request(self, path_appid=None):
        self._webhook_last_ready.value = time.monotonic()
        try:
            self.Proc_data['rx_count'] = int(self.Proc_data.get('rx_count', 0)) + 1
        except Exception:
            pass
        try:
            raw_body = request.get_data(cache=False)
        except Exception as error:
            return self._unauthorized_response('%s' % type(error).__name__)
        if raw_body is None:
            raw_body = b''
        if type(raw_body) is str:
            raw_body = raw_body.encode('utf-8')
        tmp_appid = request.headers.get('X-Bot-Appid', None)
        if path_appid is not None and str(path_appid) != '':
            if tmp_appid is None or str(tmp_appid) == '':
                tmp_appid = path_appid
            elif str(tmp_appid) != str(path_appid):
                return self._unauthorized_response(
                    'appid mismatch [%s]' % str(path_appid)
                )
        tmp_bot_info = self._get_bot_info_by_appid(tmp_appid)
        if tmp_bot_info is None:
            if tmp_appid is None or str(tmp_appid) == '':
                return self._unauthorized_response('missing appid')
            return self._unauthorized_response('unknown appid [%s]' % str(tmp_appid))
        tmp_secret = None
        try:
            tmp_secret = tmp_bot_info.post_info.access_token
        except Exception:
            tmp_secret = None
        try:
            payload_obj = json.loads(raw_body.decode('utf-8'))
        except Exception as error:
            self.log(
                3,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS qqGuildv2 webhook server [{0}] payload error [{1}: {2}]',
                    [
                        self.Proc_config['Flask_name'],
                        type(error).__name__,
                        str(error)
                    ],
                    modelName
                )
            )
            return self._ack_response()
        if type(payload_obj) is not dict:
            self.log(
                3,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS qqGuildv2 webhook server [{0}] payload error [{1}: {2}]',
                    [
                        self.Proc_config['Flask_name'],
                        'ValueError',
                        'invalid gateway payload'
                    ],
                    modelName
                )
            )
            return self._ack_response()
        tmp_op = payload_obj.get('op', None)
        # 回调地址验证(op=13)是开放平台校验回调可达性的握手:官方示例的请求头只有
        # User-Agent / X-Bot-Appid,不保证携带 X-Signature-*。因此必须优先处理,
        # 否则会被下面的入站验签拦成 401,平台侧表现为「签名校验不通过」。
        if tmp_op == 13:
            return self._handle_validation(tmp_secret, payload_obj)
        # 事件推送等入站请求必须通过 Ed25519 验签
        tmp_signature = request.headers.get('X-Signature-Ed25519', None)
        tmp_timestamp = request.headers.get('X-Signature-Timestamp', None)
        if not OlivOS.qqGuildv2SDK.verify_qqGuildv2_webhook_signature(
            tmp_secret,
            tmp_timestamp,
            raw_body,
            tmp_signature
        ):
            return self._unauthorized_response('invalid signature [%s]' % str(tmp_bot_info.id))
        self.log(
            0,
            OlivOS.L10NAPI.getTrans(
                'OlivOS qqGuildv2 webhook server [{0}] auth ACK',
                [self.Proc_config['Flask_name']],
                modelName
            )
        )
        if tmp_op == 0:
            # 开放平台要求 3 秒内 ACK,否则判定超时并延迟重推。而事件构造
            # (qqGuildv2SDK.event -> API.Event.get_Event_from_SDK)会同步发起出站
            # API 请求(自 openid 解析、换取 token),这些请求未设置超时;本进程用
            # gevent pywsgi 且未 monkey patch,一次阻塞式 socket I/O 会拖住整个
            # Webhook 服务进程。所以先应答 ACK,再把构造与入队交给独立线程
            # (threading.Thread 在未 patch 的 gevent 下是真实线程,不会占用 hub)。
            tmp_thread = threading.Thread(
                target=self._handle_dispatch,
                args=(payload_obj, tmp_bot_info),
                daemon=True
            )
            tmp_thread.start()
            return self._ack_response()
        return self._ack_response()

    def _handle_validation(self, secret, payload_obj):
        plain_token, event_ts = OlivOS.qqGuildv2SDK.get_qqGuildv2_webhook_validation(payload_obj)
        if plain_token is None or event_ts is None:
            return self._unauthorized_response('invalid validation payload')
        signature_hex = OlivOS.qqGuildv2SDK.sign_qqGuildv2_webhook_validation(
            secret,
            event_ts,
            plain_token
        )
        if signature_hex is None:
            return self._unauthorized_response('validation sign failed')
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS qqGuildv2 webhook server [{0}] callback verified',
                [self.Proc_config['Flask_name']],
                modelName
            )
        )
        return self._json_response({
            'plain_token': plain_token,
            'signature': signature_hex
        })

    def _handle_dispatch(self, payload_obj, bot_info):
        try:
            tmp_data_rx_obj = OlivOS.qqGuildv2SDK.PAYLOAD.rxPacket(data=payload_obj)
            if not tmp_data_rx_obj.active:
                raise ValueError('invalid gateway payload')
            if tmp_data_rx_obj.data.t in OlivOS.qqGuildv2SDK.qqDispatchEventTypes:
                sdk_event = OlivOS.qqGuildv2SDK.event(tmp_data_rx_obj, bot_info)
                tx_packet_data = OlivOS.pluginAPI.shallow.rx_packet(sdk_event)
                if self.Proc_info.tx_queue is not None:
                    self.Proc_info.tx_queue.put(tx_packet_data, block=False)
        except Exception as error:
            self.log(
                3,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS qqGuildv2 webhook server [{0}] payload error [{1}: {2}]',
                    [
                        self.Proc_config['Flask_name'],
                        type(error).__name__,
                        str(error)
                    ],
                    modelName
                )
            )
        return self._ack_response()

    def run(self):
        self._webhook_stopped.clear()
        self._webhook_last_ready.value = 0.0
        self.app()
        self.set_config()
        self.Proc_config['Flask_app'].config.from_object(self.Proc_config['config'])
        tmp_ssl_dirs = ensure_qqGuildv2_webhook_ssl_dirs(
            self.Proc_data.get('bot_info_dict', None),
            certdir=self.Proc_config.get('Flask_ssl_dir', None)
        )
        tmp_pairs = self._get_cert_pairs()
        tmp_ssl_context, tmp_ssl_failed = build_qqGuildv2_webhook_ssl_context(tmp_pairs)
        if tmp_ssl_context is None:
            tmp_search = os.path.abspath(str(self.Proc_config.get('Flask_ssl_dir', './conf/ssl')))
            if type(tmp_ssl_dirs) is list and len(tmp_ssl_dirs) > 0:
                tmp_search = '; '.join(tmp_ssl_dirs)
            tmp_fail = str(self.Proc_config.get('Flask_ssl_cert', ''))
            if type(tmp_ssl_failed) is list and len(tmp_ssl_failed) > 0:
                tmp_fail = '; '.join(tmp_ssl_failed)
            self.log(
                3,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS qqGuildv2 webhook server [{0}] missing HTTPS cert [{1}] [{2}]',
                    [
                        self.Proc_config['Flask_name'],
                        tmp_search,
                        tmp_fail
                    ],
                    modelName
                )
            )
        else:
            self.log(
                2,
                OlivOS.L10NAPI.getTrans(
                    'OlivOS qqGuildv2 webhook server [{0}] loaded HTTPS certs [{1}]',
                    [
                        self.Proc_config['Flask_name'],
                        str(len(tmp_pairs))
                    ],
                    modelName
                )
            )
        self.log(
            2,
            OlivOS.L10NAPI.getTrans(
                'OlivOS qqGuildv2 webhook server [{0}] is running on [{1}]',
                [
                    self.Proc_config['Flask_name'],
                    self._get_listen_url()
                ],
                modelName
            )
        )
        tmp_watchdog = threading.Thread(
            target=self._run_watchdog,
            args=(),
            daemon=True
        )
        if self.Proc_config['config'].debug_mode:
            try:
                tmp_watchdog.start()
                self.Proc_config['Flask_app'].run(
                    host=self.Proc_config['Flask_server_host'],
                    port=self.Proc_config['Flask_server_port'],
                    ssl_context=tmp_ssl_context
                )
            finally:
                self.on_terminate()
        else:
            tmp_listen = (
                self.Proc_config['Flask_server_host'],
                self.Proc_config['Flask_server_port']
            )
            tmp_wsgi_kwargs = {
                'log': None,
                'environ': {
                    'SERVER_NAME': socket.gethostname() if tmp_listen[0] in ('0.0.0.0', '::', '')
                    else str(tmp_listen[0])
                }
            }
            if tmp_ssl_context is not None:
                tmp_wsgi_kwargs['ssl_context'] = tmp_ssl_context
            else:
                tmp_cert, tmp_key = self._get_ssl_files()
                if tmp_cert is not None:
                    tmp_wsgi_kwargs['certfile'] = tmp_cert
                    tmp_wsgi_kwargs['keyfile'] = tmp_key
            try:
                server = pywsgi.WSGIServer(
                    tmp_listen,
                    self.Proc_config['Flask_app'],
                    **tmp_wsgi_kwargs
                )
            except TypeError:
                tmp_wsgi_kwargs.pop('ssl_context', None)
                if type(tmp_pairs) is list and len(tmp_pairs) > 0:
                    tmp_wsgi_kwargs['certfile'] = tmp_pairs[0][0]
                    tmp_wsgi_kwargs['keyfile'] = tmp_pairs[0][1]
                server = pywsgi.WSGIServer(
                    tmp_listen,
                    self.Proc_config['Flask_app'],
                    **tmp_wsgi_kwargs
                )
            try:
                server.start()
                self._webhook_last_ready.value = time.monotonic()
                tmp_watchdog.start()
                server.serve_forever()
            finally:
                self.on_terminate()
