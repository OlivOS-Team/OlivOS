"""Tray account management and the existing hot-reload control bus."""

import os
import queue
from unittest.mock import Mock

import pytest

import OlivOS

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='Windows account GUI')


@pytest.fixture
def account_editor():
    bot = OlivOS.API.bot_info_T(
        id=10001, platform_sdk='terminal_link', platform_platform='terminal', platform_model='default')
    accounts = {bot.hash: bot}
    control = queue.Queue()
    editor = OlivOS.multiLoginUIAPI.HostUI('test', accounts, asaycMode=True, control_queue=control)
    editor.tree_load = Mock()
    editor.UIObject['root'] = Mock()
    return editor, accounts, control


def test_tray_account_management_starts_existing_edit_workflow():
    control = queue.Queue()
    dock = OlivOS.nativeWinUIAPI.dock(control_queue=control, bot_info_dict={})
    entry = next(item for item in dock.UIData['shallow_menu_list'] if item[0] == '账号管理')
    entry[1]()
    packet = control.get_nowait()
    assert packet.action == 'call_system_event'
    assert packet.key['action'] == ['account_edit_asayc_start', 'account_edit_asayc_do']


def test_cancelling_account_edit_keeps_running_account_objects(account_editor):
    editor, accounts, control = account_editor
    key = next(iter(accounts))
    editor.UIData['Account_data'][key].enable = False
    editor.UIData['Account_data'][key].extends['draft'] = True
    editor.tree_edit_commit(['delete', key, None])
    assert accounts[key].enable is True
    assert 'draft' not in accounts[key].extends
    assert control.empty()


@pytest.mark.parametrize('action', ['create', 'update', 'delete'])
def test_account_editor_updates_draft_list(account_editor, action):
    editor, accounts, _ = account_editor
    old = next(iter(accounts))
    new = OlivOS.API.bot_info_T(id=10002)
    editor.tree_edit_commit([action, old, new])
    draft = editor.UIData['Account_data']
    assert (new.hash in draft) is (action != 'delete')
    assert (old in draft) is (action == 'create')
    editor.tree_load.assert_called_once()


def test_account_save_requests_persistence_then_hot_reload(account_editor):
    editor, accounts, control = account_editor
    key = next(iter(accounts))
    editor.UIData['Account_data'][key].enable = False
    editor.account_data_commit()
    packets = [control.get_nowait() for _ in range(4)]
    assert [packet.action for packet in packets] == [
        'call_system_event', 'call_account_update', 'call_system_stop_type_event', 'call_system_event']
    assert packets[0].key['action'] == ['account_edit_asayc_end']
    assert packets[1].key['data'][key].enable is False
    assert packets[2].key['action'] == packets[3].key['action'] == ['account_update']
    steps = OlivOS.bootDataAPI.default_Conf['system']['event']['account_edit_asayc_end']
    assert 'OlivOS_account_config_save' in steps and 'OlivOS_account_config_update' in steps
    assert editor.UIData['flag_commit'] is True
    editor.UIObject['root'].destroy.assert_called_once()
