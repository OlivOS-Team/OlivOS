'''插件 IOStream 状态机的回归测试。'''

import pickle
from types import SimpleNamespace

from OlivOS.userModule.IOStream import IO_construct


def _event(message, user_id='42', group_id=None, host_id=None, platform='qq'):
    data = SimpleNamespace(message=message, user_id=user_id)
    if group_id is not None:
        data.group_id = group_id
    if host_id is not None:
        data.host_id = host_id
    return SimpleNamespace(data=data, platform={'platform': platform})


def _paths(plugin):
    log = 'plugin/tmp/Input/{}_input_log.pickle'.format(plugin)
    cache_dir = 'plugin/tmp/Input/input_data'
    return log, cache_dir


def _load(path):
    with open(path, 'rb') as stream:
        return pickle.load(stream)


def _dump(path, value):
    with open(path, 'wb') as stream:
        pickle.dump(value, stream)


def _callback(calls, new_index=None):
    def run(plugin_event, string, re_string, cache_data):
        calls.append((string, re_string, cache_data))
        cache_data.setdefault('visited', []).append(string)
        return cache_data, new_index

    return run


def test_group_stream_advances_and_finishes_at_last_step():
    '''匹配到流程步骤后应保存游标，最后一步结束时清理群会话状态。'''

    plugin = 'group_stream'
    calls = []
    steps = [
        {'re': r'start (\d+)', 'function': _callback(calls)},
        {'re': 'end', 'function': _callback(calls)},
    ]
    IO_construct(_event('start 7', group_id='9'), steps, plugin, mode=1)
    log_path, cache_dir = _paths(plugin)
    log = _load(log_path)
    state = log['qq']['group']['9']['all']
    assert state['index'] == 1
    cache_path = cache_dir + '/' + state['cache_file_name'] + '.pickle'
    assert _load(cache_path)['visited'] == ['start 7']
    assert calls[0][1] == ('7',)

    IO_construct(_event('end', group_id='9'), steps, plugin, mode=1)
    assert _load(log_path)['qq']['group']['9']['all'] == {}
    assert not __import__('os').path.exists(cache_path)
    assert [item[0] for item in calls] == ['start 7', 'end']


def test_nonmatching_message_leaves_stream_cursor_untouched():
    '''正则未命中时不得推进步骤或调用回调。'''

    plugin = 'miss_stream'
    calls = []
    IO_construct(
        _event('hello', group_id='9'),
        [{'re': r'start (\d+)', 'function': _callback(calls)}],
        plugin,
        mode=1,
    )
    log_path, _ = _paths(plugin)
    assert _load(log_path) == {}
    assert calls == []


def test_timeout_does_not_invoke_callback_or_change_cursor():
    '''流程超时后应保留原步骤，等待插件重置或重试。'''

    plugin = 'timeout_stream'
    calls = []
    log_path, cache_dir = _paths(plugin)
    __import__('os').makedirs(cache_dir, exist_ok=True)
    _dump(cache_dir + '/timeout.pickle', {'input_history_data': []})
    _dump(log_path, {'qq': {
        'group': {'9': {'42': {}, 'all': {
            'index': 0, 'time': 0, 'cache_file_name': 'timeout'}}},
        'private': {'42': {}},
    }})
    IO_construct(
        _event('start 1', group_id='9'),
        [{'re': r'start (\d+)', 'function': _callback(calls), 'max_time': 1}],
        plugin,
        mode=1,
    )
    assert calls == []
    assert _load(log_path)['qq']['group']['9']['all']['index'] == 0


def test_private_mode_uses_private_user_stream_and_clears_cache():
    '''无群号的私聊模式应按用户保存状态，并在流程完成时清理缓存。'''

    plugin = 'private_stream'
    calls = []
    IO_construct(
        _event('answer', user_id='42'),
        [{'re': 'answer', 'function': _callback(calls, new_index=99)}],
        plugin,
        mode=2,
    )
    log_path, cache_dir = _paths(plugin)
    assert _load(log_path)['qq']['private']['42'] == {}
    assert calls and calls[0][0] == 'answer'
    assert __import__('os').path.isdir(cache_dir)
    assert not __import__('os').listdir(cache_dir)


def test_group_user_modes_keep_independent_cursors():
    '''不同群号和用户组合应维护互不干扰的流程游标。'''

    plugin = 'scoped_stream'
    calls = []
    steps = [
        {'re': 'go', 'function': _callback(calls)},
        {'re': 'end', 'function': _callback(calls)},
    ]
    IO_construct(_event('go', group_id='9'), steps, plugin, mode=3)
    IO_construct(_event('go', group_id='10'), steps, plugin, mode=3)
    log_path, _ = _paths(plugin)
    log = _load(log_path)
    assert log['qq']['group']['9']['42']['index'] == 1
    assert log['qq']['group']['10']['42']['index'] == 1
    assert len(calls) == 2


def test_non_integer_next_index_falls_back_to_sequential_step():
    '''回调返回非整数索引时应回退为顺序推进一个步骤。'''

    plugin = 'fallback_index'
    calls = []
    steps = [
        {'re': 'go', 'function': _callback(calls, new_index='invalid')},
        {'re': 'end', 'function': _callback(calls)},
    ]
    IO_construct(_event('go', group_id='9'), steps, plugin, mode=1)
    log_path, _ = _paths(plugin)
    assert _load(log_path)['qq']['group']['9']['all']['index'] == 1


def test_unknown_mode_returns_without_stream_state():
    '''未知模式即使已创建状态目录也应直接返回，不写入流程状态。'''

    plugin = 'unknown_mode'
    calls = []
    IO_construct(
        _event('go', group_id='9'),
        [{'re': 'go', 'function': _callback(calls)}],
        plugin,
        mode=4,
    )
    log_path, _ = _paths(plugin)
    assert _load(log_path) == {}
    assert calls == []


def test_finished_empty_stream_removes_absent_cache_without_error():
    '''游标越界时即使缓存文件不存在，也要安全重置为空状态。'''

    plugin = 'empty_stream'
    log_path, _ = _paths(plugin)
    __import__('os').makedirs(__import__('os').path.dirname(log_path), exist_ok=True)
    _dump(log_path, {'qq': {
        'group': {'9': {'42': {}, 'all': {'index': 3}}},
        'private': {'42': {}},
    }})
    IO_construct(_event('ignored', group_id='9'), [], plugin, mode=1)
    assert _load(log_path)['qq']['group']['9']['all'] == {}
