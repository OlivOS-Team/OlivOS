"""不创建可见应用窗口的原生界面辅助测试。"""

import base64
import hashlib
import os
import queue
from types import SimpleNamespace

import pytest

import OlivOS
from OlivOS.nativeGUI import multiLoginUIAPI, nativeWinUIAPI


pytestmark = [pytest.mark.native_gui, pytest.mark.skipif(os.name != 'nt', reason='Windows native GUI helpers')]


def _bot(model='napcat_show_new', bot_hash='hash1', enable=True, name='10001'):
    """构造原生界面辅助函数需要的最小账号结构。"""

    return SimpleNamespace(
        id=name,
        hash=bot_hash,
        enable=enable,
        platform={'platform': 'qq', 'sdk': 'onebot', 'model': model},
        post_info=SimpleNamespace(auto='True', type='post', port=5700, access_token='token'),
    )


def test_multi_login_scalar_helpers():
    """布尔、空列表和哈希辅助函数应保持历史语义。"""

    assert multiLoginUIAPI.str2bool('TRUE') is True
    assert multiLoginUIAPI.str2bool('false') is False
    assert multiLoginUIAPI.checkByListEmptyOr(['x', '', 'y']) is True
    assert multiLoginUIAPI.checkByListEmptyOr(['x', 'y']) is False
    assert multiLoginUIAPI.getHash('abc') == hashlib.md5(b'abc').hexdigest()


def test_release_base64_and_remove_directory(tmp_path):
    """Base64 资源应安全落盘，目录删除失败时可静默容忍。"""

    payload = base64.b64encode(b'payload')
    multiLoginUIAPI.releaseBase64Data(str(tmp_path / 'nested'), 'asset.bin', payload)
    assert (tmp_path / 'nested/asset.bin').read_bytes() == b'payload'
    multiLoginUIAPI.removeDir(str(tmp_path / 'nested'))
    assert not (tmp_path / 'nested').exists()
    multiLoginUIAPI.removeDir(str(tmp_path / 'missing'))


def test_send_account_update_publishes_reload_sequence():
    """账号编辑应按顺序通知系统事件并重新加载账号模型。"""

    control_queue = queue.Queue()
    multiLoginUIAPI.sendAccountUpdate(None, control_queue, {'accounts': ['new']})
    packets = [control_queue.get_nowait() for _ in range(4)]
    assert [packet.action for packet in packets] == [
        'call_system_event', 'call_account_update', 'call_system_stop_type_event', 'call_system_event',
    ]
    assert packets[1].key['data'] == {'accounts': ['new']}


def test_run_host_ui_asayc_tolerates_host_failures(monkeypatch):
    """asayc 启动器在宿主 UI 成功或异常退出后都应静默返回。"""

    class FakeHostUI:
        calls = []

        def __init__(self, **kwargs):
            self.UIData = {'flag_commit': False}
            self.start_result = kwargs['callbackData']['res'] is False
            FakeHostUI.calls.append(kwargs)

        def start(self):
            return self.start_result

    monkeypatch.setattr(multiLoginUIAPI.platform, 'system', lambda: 'Windows')
    monkeypatch.setattr(OlivOS.multiLoginUIAPI, 'HostUI', FakeHostUI)
    multiLoginUIAPI.run_HostUI_asayc({'account': object()}, queue.Queue())
    assert FakeHostUI.calls

    class BrokenHostUI:
        def __init__(self, **kwargs):
            raise RuntimeError('host unavailable')

    monkeypatch.setattr(OlivOS.multiLoginUIAPI, 'HostUI', BrokenHostUI)
    multiLoginUIAPI.run_HostUI_asayc({}, queue.Queue())


class FakeTree:
    """原生辅助测试使用的最小 Treeview 数据契约。"""

    def __init__(self, children):
        self.children = list(children)
        self.deleted = []
        self.focused = self.children[0] if self.children else None

    def get_children(self):
        return list(self.children)

    def delete(self, item):
        self.deleted.append(item)
        self.children.remove(item)

    def focus(self):
        return self.focused

    def item(self, item):
        return {'item': item}


def test_native_tree_helpers():
    """树查找应返回焦点行，裁剪时应保留最新记录。"""

    tree = FakeTree(['a', 'b', 'c', 'd'])
    assert nativeWinUIAPI.get_tree_force(tree) == {'item': 'a'}
    nativeWinUIAPI.keep_tree_thin(tree, max_num=3, step_num=2)
    assert tree.deleted == ['a', 'b']
    assert tree.children == ['c', 'd']


def test_native_release_base64_creates_directory(tmp_path):
    """WinUI 辅助方法应能把 Base64 资源写入不存在的目录。"""

    nativeWinUIAPI.releaseBase64Data(str(tmp_path / 'assets'), 'a.bin', base64.b64encode(b'a'))
    assert (tmp_path / 'assets/a.bin').read_bytes() == b'a'


def test_fix_treeview_color_filters_legacy_state_entries():
    """兼容修复只转发未禁用且未选中状态的样式映射。"""

    class FakeStyle:
        def __init__(self):
            self.calls = []

        def map(self, widget, **kwargs):
            self.calls.append((widget, kwargs))
            return [('!disabled', '!selected', 'ignored'), ('normal', 'kept')]

    style = FakeStyle()
    nativeWinUIAPI.fix_Treeview_color(style)
    assert style.calls[-1][0] == 'Treeview'
    assert style.calls[-1][1] == {
        'foreground': [('normal', 'kept')],
        'background': [('normal', 'kept')],
    }


def test_dock_account_display_and_filtering():
    """账号标签应使用元数据映射，禁用账号应从列表中隐藏。"""

    from OlivOS.core.core import accountMetadataAPI

    mapping_key = accountMetadataAPI.accountTypeList[0]
    mapping = accountMetadataAPI.accountTypeMappingList[mapping_key]
    enabled = _bot(mapping[2], bot_hash='enabled')
    disabled = _bot(mapping[2], bot_hash='disabled', enable=False, name='20002')
    dock = nativeWinUIAPI.dock(control_queue=queue.Queue(), rx_queue=queue.Queue(),
                               bot_info_dict={'enabled': enabled, 'disabled': disabled})

    assert dock.getPlatformDisplayName(enabled) == mapping_key
    assert dock.getPlatformDisplayName(SimpleNamespace(platform={'platform': 'unknown'}))
    assert dock.getAccountDisplayInfo('enabled', enabled, flagInit=True) == ('10001', mapping_key)
    assert dock.isAccountEnabled('enabled') is True
    assert dock.isAccountEnabled('disabled') is False
    assert dock.isAccountEnabled('missing') is False

    dock.updateAccountList(flagInit=True)
    assert dock.UIData['shallow_account_list_new'] == [('enabled', '10001', mapping_key)]
    assert dock.mergeAccountList() is True
    assert dock.UIData['shallow_account_list_initialized'] is True
    assert dock.UIData['shallow_menu_list']


def test_dock_falls_back_to_protocol_without_post_info():
    """缺少 post_info 时，已知平台仍应通过前三元组回退识别。"""

    from OlivOS.core.core import accountMetadataAPI

    mapping_key = accountMetadataAPI.accountTypeList[0]
    mapping = accountMetadataAPI.accountTypeMappingList[mapping_key]
    bot = SimpleNamespace(id='1', hash='h', enable=True,
                          platform={'platform': mapping[0], 'sdk': mapping[1], 'model': mapping[2]})
    assert nativeWinUIAPI.dock(bot_info_dict={'h': bot}).getPlatformDisplayName(bot) == mapping_key


def test_dock_account_list_send_and_control_event():
    """dock 应提供账号列表广播回调并转发账号更新控制包。"""

    rx_queue = queue.Queue()
    control_queue = queue.Queue()
    dock = nativeWinUIAPI.dock(control_queue=control_queue, rx_queue=rx_queue, bot_info_dict={})
    dock.updateShallowMenuAccountListSendFunc()()
    packet = rx_queue.get_nowait()
    assert packet.action == 'send'
    assert packet.key['data'] == {'action': 'update_account_list'}

    dock.on_control_rx(object())
    dock.on_control_rx(OlivOS.API.Control.packet('send', {'data': {'action': 'account_update'}, 'x': 1}))
    forwarded = rx_queue.get_nowait()
    assert forwarded.action == 'send'
    assert forwarded.key['data']['action'] == 'account_update'
