"""消息解析与序列化边界的扩展离线覆盖。"""

import json

import pytest

from OlivOS.core.core.messageAPI import PARA, Message_templet


def _segment_types(message):
    """按顺序返回消息段类型，便于紧凑的结构断言。"""

    return [segment.type for segment in message.data]


def test_message_helpers_and_unknown_format_keep_public_contract():
    """辅助方法、追加操作和未知 get 模式应保持既有公共行为。"""

    message = Message_templet('olivos_para', [PARA.text('hello')])
    assert message.match_str('abcdef', 'abc')
    assert not message.match_str('ab', 'abc')
    assert message.get_from_dict({'a': {'b': 2}}, ['a', 'b']) == 2
    assert message.get_from_dict({'a': 1}, ['a', 'missing'], 'fallback') == 'fallback'
    message.append(PARA.text('!'))
    assert message.get('olivos_para') is message
    assert 'hello' in str(message)
    assert message.get('unknown_format') == str(message)


def test_olivos_para_keeps_only_real_segments():
    """olivos_para 列表中只把 PARA 子类实例保留为消息段。"""

    message = Message_templet('olivos_para', [PARA.text('kept'), object(), PARA.image('file.png')])
    assert message.active
    assert _segment_types(message) == ['text', 'image']


def test_unknown_mode_is_active_but_empty():
    """未知接收格式不应抛错，应生成 active 但 data 为空的消息。"""

    message = Message_templet('future_format', 'ignored')
    assert message.active
    assert message.data == []
    assert message.get('olivos_string') == ''


def test_inactive_message_serializes_its_state_as_string():
    """inactive 消息应通过旧字符串回退暴露自身状态。"""

    message = Message_templet('olivos_para', None)
    assert not message.active
    serialized = message.get('old_string')
    assert isinstance(serialized, str) and "'active': False" in serialized


def test_obv12_parses_and_serializes_every_supported_segment():
    """OneBot V12 全部受支持段应完整映射并保留文档字段。"""

    payload = [
        {'type': 'text', 'data': {'text': 'hello'}},
        {'type': 'mention', 'data': {'user_id': 42}},
        {'type': 'mention_all', 'data': {}},
        {'type': 'image', 'data': {'file_id': 'image.png', 'url': 'https://example.invalid/i', 'flush': True}},
        {'type': 'voice', 'data': {'file_id': 'voice.amr'}},
        {'type': 'audio', 'data': {'file_id': 'audio.mp3'}},
        {'type': 'video', 'data': {'file_id': 'video.mp4'}},
        {'type': 'location', 'data': {'latitude': 1, 'longitude': 2, 'title': 'T', 'content': 'C'}},
        {'type': 'face', 'data': {'id': '9'}},
        {'type': 'dice', 'data': {}},
        {'type': 'rps', 'data': {}},
        {'type': 'reply', 'data': {'message_id': 8}},
        {'type': 'json', 'data': {'data': '{"a":1}'}},
        {'type': 'xml', 'data': {'data': '<xml/>'}},
    ]
    message = Message_templet('obv12_para', payload)
    assert message.active
    assert _segment_types(message) == [
        'text', 'at', 'at', 'image', 'record', 'record', 'video',
        'location', 'face', 'dice', 'rps', 'reply', 'json', 'xml',
    ]
    assert message.data[2].data['id'] == 'all'
    assert message.data[3].data['type'] == 'flush'
    assert message.data[3].data['url'] == 'https://example.invalid/i'
    assert message.data[7].data == {'lat': 1, 'lon': 2, 'title': 'T', 'content': 'C'}
    assert message.get('obv12_para') == [
        {'type': 'text', 'data': {'text': 'hello'}},
        {'type': 'mention', 'data': {'user_id': '42'}},
        {'type': 'mention_all', 'data': {}},
        {'type': 'image', 'data': {'file_id': 'image.png', 'url': 'https://example.invalid/i', 'flush': True}},
        {'type': 'record', 'data': {'file_id': 'voice.amr'}},
        {'type': 'record', 'data': {'file_id': 'audio.mp3'}},
        {'type': 'video', 'data': {'file_id': 'video.mp4'}},
        {'type': 'location', 'data': {'latitude': 1, 'longitude': 2, 'title': 'T', 'content': 'C'}},
        {'type': 'face', 'data': {'id': '9'}},
        {'type': 'dice', 'data': {}},
        {'type': 'rps', 'data': {}},
        {'type': 'reply', 'data': {'message_id': '8'}},
        {'type': 'json', 'data': {'data': '{"a":1}'}},
        {'type': 'xml', 'data': {'data': '<xml/>'}},
    ]


@pytest.mark.parametrize('mode', ['obv12_para', 'milky_para_rx', 'milky_para_tx'])
def test_structured_message_requires_a_list_container(mode):
    """结构化消息格式收到非列表容器时应安全置为 inactive。"""

    message = Message_templet(mode, {'type': 'text', 'data': {'text': 'ignored'}})
    assert not message.active and message.data == []


def test_obv12_skips_malformed_and_unknown_segments():
    """畸形或未知 V12 段应被跳过且不影响后续有效文本。"""

    message = Message_templet('obv12_para', [
        None,
        {'type': 'text'},
        {'type': 'text', 'data': 'not-a-dict'},
        {'type': 'future', 'data': {}},
        {'type': 'text', 'data': {'text': 'kept'}},
    ])
    assert message.active and _segment_types(message) == ['text']
    assert message.data[0].data['text'] == 'kept'


def test_obv12_image_without_optional_url_still_roundtrips():
    """V12 图片缺少可选 url 时仍应显式输出固定字段并完成往返。"""

    message = Message_templet('obv12_para', [{'type': 'image', 'data': {'file_id': 'image.png'}}])
    assert message.get('obv12_para') == [
        {'type': 'image', 'data': {'file_id': 'image.png', 'url': None, 'flush': False}},
    ]


def test_milky_rx_parses_every_supported_segment():
    """Milky 接收载荷应把媒体、回复、文件和卡片映射到 PARA 数据。"""

    payload = [
        {'type': 'text', 'data': {'text': 'hello'}},
        {'type': 'mention', 'data': {'user_id': 42, 'name': 'Alice'}},
        {'type': 'mention_all', 'data': {}},
        {'type': 'face', 'data': {'face_id': '9'}},
        {'type': 'reply', 'data': {'message_seq': 8}},
        {'type': 'image', 'data': {'resource_id': 'image.bin', 'temp_url': 'https://example.invalid/i'}},
        {'type': 'record', 'data': {'resource_id': 'record.bin', 'temp_url': 'https://example.invalid/r'}},
        {'type': 'video', 'data': {'resource_id': 'video.bin', 'temp_url': 'https://example.invalid/v'}},
        {'type': 'file', 'data': {'file_id': 'file.bin', 'file_name': 'a.txt', 'file_size': 3}},
        {'type': 'forward', 'data': {'forward_id': 'forward-1'}},
        {'type': 'light_app', 'data': {'app_name': 'demo', 'json_payload': '{"title":"demo"}'}},
        {'type': 'xml', 'data': {'service_id': 5, 'xml_payload': '<xml/>'}},
        {'type': 'future', 'data': {}},
        None,
    ]
    message = Message_templet('milky_para_rx', payload)
    assert message.active
    assert _segment_types(message) == [
        'text', 'at', 'at', 'face', 'reply', 'image', 'record',
        'video', 'file', 'forward', 'json', 'xml',
    ]
    assert message.data[1].data == {'id': '42', 'name': 'Alice'}
    assert message.data[3].data['id'] == '9'
    assert message.data[8].data['name'] == 'a.txt'
    assert message.data[11].data == {'data': '<xml/>', 'resid': 5}
    reply = message.get('milky_para_rx')[4]
    assert reply == {'type': 'reply', 'data': {'message_seq': 8}}


def test_milky_tx_parses_outgoing_segments_and_ignores_unsupported_cards():
    """Milky 发送载荷应映射出站媒体并丢弃不支持的 XML 卡片。"""

    payload = [
        {'type': 'text', 'data': {'text': 'hello'}},
        {'type': 'mention', 'data': {'user_id': 42}},
        {'type': 'mention_all', 'data': {}},
        {'type': 'face', 'data': {'face_id': '9'}},
        {'type': 'reply', 'data': {'message_seq': 8}},
        {'type': 'image', 'data': {'uri': 'image.png', 'sub_type': 'sticker'}},
        {'type': 'record', 'data': {'uri': 'record.amr'}},
        {'type': 'video', 'data': {'uri': 'video.mp4'}},
        {'type': 'forward', 'data': {}},
        {'type': 'light_app', 'data': {'app_name': 'demo', 'json_payload': '{"a":1}'}},
        {'type': 'xml', 'data': {'service_id': 5, 'xml_payload': '<xml/>'}},
        {'type': 'future', 'data': {}},
    ]
    message = Message_templet('milky_para_tx', payload)
    assert message.active
    assert _segment_types(message) == ['text', 'at', 'at', 'face', 'reply', 'image', 'record', 'video', 'json']
    assert message.data[5].data['type'] == 'sticker'
    assert message.get('milky_para_tx') == [
        {'type': 'text', 'data': {'text': 'hello'}},
        {'type': 'mention', 'data': {'user_id': 42}},
        {'type': 'mention_all', 'data': {}},
        {'type': 'face', 'data': {'face_id': '9', 'is_large': False}},
        {'type': 'reply', 'data': {'message_seq': 8}},
        {'type': 'image', 'data': {'uri': 'image.png', 'sub_type': 'normal'}},
        {'type': 'record', 'data': {'uri': 'record.amr'}},
        {'type': 'video', 'data': {'uri': 'video.mp4'}},
        {'type': 'light_app', 'data': {'json_payload': '{"a":1}'}},
    ]


def test_milky_serialization_uses_url_when_present_and_falls_back_cleanly():
    """Milky 出站媒体优先使用 URL，并兼容历史 None 字符串与不支持段回退。"""

    message = Message_templet('olivos_para', [
        PARA.record('record.bin', url='https://example.invalid/r'),
        PARA.video('video.bin', url='None'),
        PARA.forward('forward-1'),
        PARA.shake(),
    ])
    serialized = message.get('milky_para_tx')
    assert serialized[0] == {'type': 'record', 'data': {'uri': 'https://example.invalid/r'}}
    assert serialized[1] == {'type': 'video', 'data': {'uri': 'video.bin'}}
    assert serialized[2] == {'type': 'forward', 'data': {'messages': []}}
    assert serialized[3] == {'type': 'text', 'data': {'text': ''}}


def test_milky_malformed_reply_and_unsupported_segment_fall_back_to_empty_text():
    """畸形回复标识和不支持段应降级为空文本段，不能抛错。"""

    rx = Message_templet('olivos_para', [PARA.reply('not-a-triplet'), PARA.shake()])
    tx = Message_templet('olivos_para', [PARA.reply('bad-reply'), PARA.shake()])
    assert rx.get('milky_para_rx') == [
        {'type': 'text', 'data': {'text': ''}},
        {'type': 'text', 'data': {'text': ''}},
    ]
    assert tx.get('milky_para_tx') == [
        {'type': 'text', 'data': {'text': ''}},
        {'type': 'text', 'data': {'text': ''}},
    ]


def test_milky_complete_reply_identifier_keeps_sender_and_timestamp():
    """历史 scene|peer|sequence 回复标识仍应保留发送者与时间戳。"""

    message = Message_templet('olivos_para', [PARA.reply('group|42|8')])
    serialized = message.get('milky_para_rx')[0]
    assert serialized['type'] == 'reply'
    assert serialized['data']['message_seq'] == 8
    assert serialized['data']['sender_id'] == 42
    assert isinstance(serialized['data']['time'], int)


@pytest.mark.parametrize('raw,expected_type,expected_data', [
    # 基础文本与两类 at。
    ('before[CQ:at,qq=42,name=Alice]after', 'at', {'id': '42', 'name': 'Alice'}),
    # 表情与商城表情。
    ('[CQ:face,id=9]', 'face', {'id': '9'}),
    ('[CQ:mface,emoji_package_id=1,emoji_id=2,summary=s]', 'mface', {'emoji_package_id': '1', 'summary': 's'}),
    # 回复。
    ('[CQ:reply,id=8]', 'reply', {'id': '8'}),
    # 图片、语音、视频与文件。
    ('[CQ:image,file=a.png,url=https://example.invalid/a]', 'image', {'file': 'a.png'}),
    ('[CQ:record,file=a.amr]', 'record', {'file': 'a.amr'}),
    ('[CQ:video,file=a.mp4]', 'video', {'file': 'a.mp4'}),
    ('[CQ:file,file=a.txt,path=/tmp/a,name=a.txt,size=3]', 'file', {'name': 'a.txt', 'size': '3'}),
    # 交互类段。
    ('[CQ:rps]', 'rps', {}),
    ('[CQ:dice]', 'dice', {}),
    ('[CQ:shake]', 'shake', {}),
    ('[CQ:poke,id=42]', 'poke', {'id': '42'}),
    ('[CQ:anonymous]', 'anonymous', {}),
    # 富文本与位置。
    ('[CQ:share,url=u,title=t,content=c,image=i]', 'share', {'url': 'u', 'title': 't'}),
    ('[CQ:location,lat=1,lon=2,title=t,content=c]', 'location', {'lat': '1', 'lon': '2'}),
    # 音乐、转发与卡片。
    ('[CQ:music,type=custom,id=1]', 'music', {'type': 'custom', 'id': '1'}),
    ('[CQ:forward,id=forward-1]', 'forward', {'id': 'forward-1'}),
    ('[CQ:xml,data=<xml/>]', 'xml', {'data': '<xml/>'}),
    ('[CQ:json,data={"a":1}]', 'json', {'data': '{"a":1}'}),
    # 未知段原样保留为文本，避免丢失插件可见内容。
    ('[CQ:future,x=1]', 'text', {'text': '[CQ:future,x=1]'}),
])
def test_cq_segment_matrix(raw, expected_type, expected_data):
    """每个受支持 CQ 段都应映射到预期的 PARA 类型和字段。"""

    message = Message_templet('old_string', raw)
    assert message.active
    target = next(segment for segment in message.data if segment.type == expected_type)
    assert expected_data.items() <= (target.data or {}).items()


def test_code_parser_preserves_order_and_equals_inside_values():
    """代码段前后文本应保持顺序，参数值中的等号不得被拆断。"""

    message = Message_templet('old_string', 'a[CQ:at,qq=42]b[CQ:json,data=a=b]c')
    assert _segment_types(message) == ['text', 'at', 'text', 'json', 'text']
    assert [segment.data['text'] for segment in message.data if segment.type == 'text'] == ['a', 'b', 'c']
    assert message.data[3].data['data'] == 'a=b'


def test_unclosed_code_segment_is_preserved_as_text():
    """未闭合代码段必须原样保留为文本，不能部分转换或丢弃。"""

    message = Message_templet('old_string', 'a[CQ:face,id=1')
    assert message.active and _segment_types(message) == ['text', 'text']
    assert message.get('old_string') == 'a[CQ:face,id=1'


def test_segment_serializers_cover_cq_op_and_platform_specific_syntax():
    """CQ/OP 及各平台序列化器应遵循键名、图片 URL 与转义规则。"""

    assert PARA.at('42', name='Alice').CQ() == '[CQ:at,qq=42,name=Alice]'
    assert PARA.at('42', name='Alice').OP() == '[OP:at,id=42,name=Alice]'
    assert PARA.image('a.png', url='https://example.invalid/a').CQ() == '[CQ:image,file=https://example.invalid/a]'
    image_op = PARA.image('a.png', url='https://example.invalid/a').OP()
    assert image_op == '[OP:image,file=a.png,url=https://example.invalid/a]'
    assert PARA.text('plain').kaiheila() == 'plain'
    assert PARA.text('plain').fanbook() == 'plain'
    assert PARA.text('plain').dodo() == 'plain'
    assert PARA.text('plain').xiaoheihe() == 'plain'
    assert PARA.at('42').kaiheila() == '${@#42}'
    assert PARA.at('42').fanbook() == '${@!42}'
    assert PARA.at('42').dodo() == '<@!42>'
    assert PARA.at('42').xiaoheihe() == '@{id:42}'
    assert PARA.at(None).xiaoheihe() == ''
    assert PARA.shake().xiaoheihe() == ''


def test_message_get_dispatches_platform_string_formats():
    """Message.get 应把共享段分派到对应平台字符串序列化器。"""

    message = Message_templet('olivos_para', [PARA.text('a'), PARA.at('42')])
    assert message.get('fanbook_string') == 'a${@!42}'
    assert message.get('dodo_string') == 'a<@!42>'
    assert message.get('kaiheila_string') == 'a${@#42}'
    assert message.get('xiaoheihe_string') == 'a@{id:42}'
    assert message.get('qqGuild_string') == 'a[OP:at,id=42]'
    assert message.get('qqGuildv2_string') == 'a[OP:at,id=42]'


@pytest.mark.parametrize('mode,raw,expected', [
    # Fanbook: 指定用户、全体与未知段。
    (
        'fanbook_string',
        'a${@!42}${@&1}${plain}b',
        [('text', 'a'), ('at', '42'), ('at', 'all'), ('text', '${plain}'), ('text', 'b')],
    ),
    # Dodo: 尖括号语法。
    ('dodo_string', 'a<@!42><@&1>b', [('text', 'a'), ('at', '42'), ('at', 'all'), ('text', 'b')]),
    # QQ 频道旧协议：用户 at 与全体 at。
    ('qqGuild_string', 'a<@42>b@everyone', [('text', 'a'), ('at', '42'), ('text', 'b'), ('at', 'all')]),
    # 开黑啦：met 标记与反斜杠转义。
    (
        'kaiheila_string',
        r'a(met)42(met)b\[c\]',
        [('text', 'a'), ('at', '42'), ('text', 'b[c]')],
    ),
    # Discord：仅转换用户 at，不处理反斜杠。
    ('discord_string', r'a<@42>b\*c', [('text', 'a'), ('at', '42'), ('text', r'b\*c')]),
    # 小黑盒：花括号 id 语法。
    ('xiaoheihe_string', 'a@{id:42}b', [('text', 'a'), ('at', '42'), ('text', 'b')]),
])
def test_platform_code_parsers(mode, raw, expected):
    """各平台专有文本格式应正确解析为统一消息段模型。"""

    message = Message_templet(mode, raw)
    assert message.active
    assert [(segment.type, segment.data['text'] if segment.type == 'text' else segment.data['id'])
            for segment in message.data] == expected


def test_qq_guild_v2_at_syntax_and_everyone_fallback():
    """QQ 群/C2C 的 at 标签应兼容引号、无引号、空值、频道和字面 everyone。"""

    raw = ('a<qqbot-at-user id="42" />b<qqbot-at-user id=43>c'
           '<qqbot-at-user id="">d<qqbot-at-everyone />e@everyone f')
    message = Message_templet('qqGuildv2_string', raw)
    assert message.active
    actual = [(segment.type, segment.data.get('id'), segment.data.get('text')) for segment in message.data]
    assert actual == [
        ('text', None, 'a'), ('at', '42', None), ('text', None, 'b'), ('at', '43', None),
        ('text', None, 'c'), ('at', '', None), ('text', None, 'd'), ('at', 'all', None),
        ('text', None, 'e'), ('text', None, '@everyone'), ('text', None, ' f'),
    ]


@pytest.mark.parametrize('segment,expected_type,expected_data', [
    # 文本。
    (PARA.text('x'), 'text', {'text': 'x'}),
    # 表情。
    (PARA.face('1'), 'face', {'id': '1'}),
    (PARA.mface(emoji_package_id=1, emoji_id=2, key='k', summary='s', url='u', face_type='t', face_id='i', ext='e'),
     'mface', {'emoji_package_id': 1, 'ext': 'e'}),
    # 媒体。
    (PARA.image('a.png'), 'image', {'file': 'a.png'}),
    (PARA.record('a.amr'), 'record', {'file': 'a.amr'}),
    (PARA.video('a.mp4'), 'video', {'file': 'a.mp4'}),
    (PARA.file('a.txt', name='a.txt'), 'file', {'name': 'a.txt'}),
    # 交互。
    (PARA.at('42'), 'at', {'id': '42'}),
    (PARA.rps(), 'rps', None),
    (PARA.dice(), 'dice', None),
    (PARA.shake(), 'shake', None),
    (PARA.poke(id='42'), 'poke', {'id': '42'}),
    (PARA.anonymous(), 'anonymous', None),
    # 富文本。
    (PARA.share('u', 't'), 'share', {'url': 'u', 'title': 't'}),
    (PARA.contact('group', '1'), 'contact', {'type': 'group', 'id': '1'}),
    (PARA.location(1, 2), 'location', {'lat': 1, 'lon': 2}),
    (PARA.music('custom', id='1'), 'music', {'type': 'custom', 'id': '1'}),
    # 引用、转发、合并转发节点与卡片。
    (PARA.reply('8'), 'reply', {'id': '8'}),
    (PARA.forward('f'), 'forward', {'id': 'f'}),
    (PARA.node(user_id='42', nickname='Alice'), 'node', {'user_id': '42'}),
    (PARA.xml('<xml/>'), 'xml', {'data': '<xml/>'}),
    (PARA.json('{}'), 'json', {'data': '{}'}),
])
def test_para_factory_builds_expected_segment(segment, expected_type, expected_data):
    """每个 PARA 工厂方法都应生成预期的公共类型与数据形状。"""

    assert segment.type == expected_type
    if expected_data is None:
        assert segment.data is None
    else:
        assert expected_data.items() <= segment.data.items()


def test_para_json_serialization_handles_empty_data_and_copies_are_isolated():
    """无 data 的消息段应安全序列化，cut/copy 不得修改源段。"""

    assert json.loads(PARA.rps().PARA()) == {'type': 'rps', 'data': {}}
    source = PARA.image('a.png', url='https://example.invalid/a')
    copied = source.copy()
    copied.data['file'] = 'b.png'
    assert source.data['file'] == 'a.png'
    cut = source.cut()
    assert cut.data == {'file': 'a.png', 'url': 'https://example.invalid/a'}
    assert source.data['url'] == 'https://example.invalid/a'
