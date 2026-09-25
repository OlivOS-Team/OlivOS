"""原生插件管理器的顺序展示与优先级编辑。"""

import json
import os
import queue
from unittest.mock import Mock

import pytest

pytestmark = [pytest.mark.native_gui, pytest.mark.skipif(os.name != 'nt', reason='Windows native plugin manager')]


class FakeTree:
    """pluginManageUI.tree_load 用到的 Treeview 子集。"""

    def __init__(self):
        self.items = []
        self.focused = None
        self.next_id = 0

    def get_children(self):
        return [item[0] for item in self.items]

    def delete(self, item_id):
        self.items = [item for item in self.items if item[0] != item_id]

    def insert(self, parent, index, text=None, values=None):
        item_id = 'item%d' % self.next_id
        self.next_id += 1
        self.items.append((item_id, text, values))
        return item_id

    def item(self, item_id, key):
        for entry in self.items:
            if entry[0] == item_id:
                return entry[1] if key == 'text' else entry[2]
        return None

    def focus(self, item_id=None):
        if item_id is not None:
            self.focused = item_id
        return self.focused


class FakeVar:
    def __init__(self):
        self.value = ''

    def set(self, value):
        self.value = value

    def get(self):
        return self.value


def plugin_data(name, priority):
    return [name, '1.0', 'OlivOS', [], '测试插件', '', priority]


@pytest.fixture
def manager():
    from OlivOS.nativeGUI import nativeWinUIAPI

    dock = nativeWinUIAPI.dock(control_queue=queue.Queue(), bot_info_dict={})
    dock.UIData['shallow_plugin_data_dict'] = {
        'alpha': plugin_data('A 插件', 30000),
        'beta': plugin_data('B 插件', 100),
    }
    dock.UIData['shallow_plugin_order_list'] = ['beta', 'alpha']
    dock.UIData['shallow_plugin_priority_dict'] = {
        'alpha': {'default': 30000, 'user': None, 'effective': 30000, 'source': 'default'},
        'beta': {'default': 20000, 'user': 100, 'effective': 100, 'source': 'user'},
    }
    view = nativeWinUIAPI.pluginManageUI('test', root=dock, logger_proc=Mock(), key='0')
    view.UIObject['tree'] = FakeTree()
    view.UIData['root_Label_PRIORITY_StringVar'] = FakeVar()
    view.UIData['root_Label_INFO_StringVar'] = FakeVar()
    return dock, view


def test_plugin_manager_tree_follows_loader_order(manager):
    _, view = manager
    view.tree_load()
    assert [item[1] for item in view.UIObject['tree'].items] == ['beta', 'alpha']


def test_plugin_manager_priority_label_shows_user_and_default(manager):
    _, view = manager
    view.tree_load()
    view.UIObject['tree'].focus('item0')
    view.treeSelect('tree', None)
    assert view.UIData['root_Label_PRIORITY_StringVar'].get() == '100（用户 100 / 默认 20000）'
    view.UIObject['tree'].focus('item1')
    view.treeSelect('tree', None)
    assert view.UIData['root_Label_PRIORITY_StringVar'].get() == '30000（默认）'


def test_plugin_priority_set_writes_override_and_reloads_loader(manager, tmp_path):
    dock, _ = manager
    dock.webui_root = str(tmp_path)
    assert dock.sendPluginPriority('alpha', 50) is True
    document = json.loads((tmp_path / 'conf/plugin_priority.json').read_text(encoding='utf-8'))
    assert document['plugins']['alpha'] == {'priority': 50}
    packet = dock.Proc_info.control_queue.get_nowait()
    assert packet.key['target'] == {'type': 'plugin', 'fliter': 'control_only'}
    assert packet.key['data'] == {'action': 'plugin_priority_reload'}


def test_plugin_priority_top_and_bottom_use_effective_range(manager, tmp_path):
    dock, _ = manager
    dock.webui_root = str(tmp_path)
    dock.setPluginPriorityTop('alpha')
    document = json.loads((tmp_path / 'conf/plugin_priority.json').read_text(encoding='utf-8'))
    assert document['plugins']['alpha'] == {'priority': 99}
    dock.Proc_info.control_queue.get_nowait()
    dock.UIData['shallow_plugin_priority_dict']['alpha']['effective'] = 99
    dock.setPluginPriorityBottom('alpha')
    document = json.loads((tmp_path / 'conf/plugin_priority.json').read_text(encoding='utf-8'))
    assert document['plugins']['alpha'] == {'priority': 101}


def test_plugin_priority_top_rejects_value_below_zero(manager, tmp_path, monkeypatch):
    from OlivOS.nativeGUI import nativeWinUIAPI

    dock, _ = manager
    dock.webui_root = str(tmp_path)
    dock.UIData['shallow_plugin_priority_dict']['beta']['effective'] = 0
    errors = []
    monkeypatch.setattr(nativeWinUIAPI.tkinter.messagebox, 'showerror',
                        lambda *args, **kwargs: errors.append(args))
    dock.setPluginPriorityTop('alpha')
    assert errors
    assert not (tmp_path / 'conf/plugin_priority.json').exists()
    assert dock.Proc_info.control_queue.empty()


def test_plugin_priority_reset_removes_override_and_keeps_others(manager, tmp_path):
    dock, _ = manager
    dock.webui_root = str(tmp_path)
    (tmp_path / 'conf').mkdir()
    (tmp_path / 'conf/plugin_priority.json').write_text(json.dumps({
        'version': 1,
        'plugins': {'beta': {'priority': 100}, 'other': {'priority': 5}},
    }), encoding='utf-8')
    dock.resetPluginPriority('beta')
    document = json.loads((tmp_path / 'conf/plugin_priority.json').read_text(encoding='utf-8'))
    assert 'beta' not in document['plugins']
    assert document['plugins']['other'] == {'priority': 5}


def test_plugin_priority_write_rejects_corrupted_file(manager, tmp_path, monkeypatch):
    from OlivOS.nativeGUI import nativeWinUIAPI

    dock, _ = manager
    dock.webui_root = str(tmp_path)
    (tmp_path / 'conf').mkdir()
    path = tmp_path / 'conf/plugin_priority.json'
    path.write_text('{not json', encoding='utf-8')
    errors = []
    monkeypatch.setattr(nativeWinUIAPI.tkinter.messagebox, 'showerror',
                        lambda *args, **kwargs: errors.append(args))
    assert dock.sendPluginPriority('alpha', 50) is False
    assert errors and path.read_text(encoding='utf-8') == '{not json'
    assert dock.Proc_info.control_queue.empty()


def test_plugin_priority_write_preserves_unknown_fields(manager, tmp_path):
    dock, _ = manager
    dock.webui_root = str(tmp_path)
    (tmp_path / 'conf').mkdir()
    path = tmp_path / 'conf/plugin_priority.json'
    path.write_text(json.dumps({
        'version': 1,
        'note': 'keep',
        'plugins': {'alpha': {'priority': 100, 'before': ['beta']}},
    }), encoding='utf-8')
    dock.sendPluginPriority('alpha', 50)
    document = json.loads(path.read_text(encoding='utf-8'))
    assert document['note'] == 'keep'
    assert document['plugins']['alpha'] == {'priority': 50, 'before': ['beta']}
