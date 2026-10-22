"""QQ API V2 Markdown local-image upload and cleanup behavior."""

from types import SimpleNamespace
from unittest.mock import Mock

import OlivOS
SDK = OlivOS.qqGuildv2SDK


def _target_event():
    bot = OlivOS.API.bot_info_T(
        id=10001,
        platform_sdk='qqGuildv2_link',
        platform_platform='qqGuild',
        platform_model='public'
    )
    return SimpleNamespace(bot_info=bot, log_func=None)


def test_local_markdown_images_deduplicate_by_content(monkeypatch):
    image = {
        'bytes': b'image', 'file_name': 'image.png', 'content_type': 'image/png',
        'width': 20, 'height': 10, 'md5': 'a', 'sha1': 'b', 'sha256': 'same'
    }
    read = Mock(return_value=(image, None, None))
    upload = Mock(return_value=({'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'}, None))
    monkeypatch.setattr(SDK.event_action, '_read_markdown_image', read)
    monkeypatch.setattr(SDK.event_action, '_upload_markdown_image', upload)

    replacements, uploaded, error = SDK.event_action._upload_markdown_images(
        _target_event(), {'cover': 'cover.png', 'copy': 'copy.png'}
    )

    assert error is None
    assert upload.call_count == 1
    assert replacements['cover'] == '![cover #20px #10px](qqbot-media://image/v1/t)'
    assert replacements['copy'] == '![copy #20px #10px](qqbot-media://image/v1/t)'
    assert len(uploaded) == 1


def test_mixed_message_sends_markdown_then_cleans_up(monkeypatch):
    uploaded = [{'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'}]
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image #20px #10px](qqbot-media://image/v1/t)'},
            uploaded,
            None
        ))
    )
    delete = Mock()
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', delete)
    send = Mock(return_value={'active': True, 'data': {'http_status': 200}})
    monkeypatch.setattr(SDK.event_action, 'create_markdown_message', send)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('before '),
        OlivOS.messageAPI.PARA.image('images/a.png'),
        OlivOS.messageAPI.PARA.text(' after')
    ])

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    assert result['active'] is True
    assert error is None
    markdown = send.call_args.args[3]['content']
    assert markdown == 'before ![image #20px #10px](qqbot-media://image/v1/t) after'
    delete.assert_called_once_with(send.call_args.args[0], uploaded)


def test_uncertain_markdown_send_keeps_uploaded_assets(monkeypatch):
    uploaded = [{'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'}]
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=({'image_0': '![image](qqbot-media://image/v1/t)'}, uploaded, None))
    )
    delete = Mock()
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', delete)
    monkeypatch.setattr(
        SDK.event_action,
        'create_markdown_message',
        Mock(return_value={'active': False, 'data': {'http_status': None}})
    )
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('text'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    delete.assert_not_called()


def test_manual_markdown_upload_failure_falls_back_to_image_message(monkeypatch):
    target = _target_event()
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(None, [], 'cover: image exceeds the 10 MB Markdown asset limit'))
    )
    send = Mock(return_value={'active': True, 'data': {'message_ids': ['fallback-id']}})
    monkeypatch.setattr(SDK.event_action, 'send_qq_msg', send)

    result = SDK.event_action.create_markdown_message(
        target,
        'qq_group',
        'group',
        {'content': '# Report\n{{cover}}'},
        msg_id='reply-id',
        local_images={'cover': 'reports/cover.png'}
    )

    assert result['active'] is True
    assert result['data']['markdown_fallback'].startswith('cover: image exceeds')
    message = send.call_args.args[2]
    assert isinstance(message.data[0], OlivOS.messageAPI.PARA.text)
    assert message.data[0].data['text'] == '# Report\n'
    assert isinstance(message.data[1], OlivOS.messageAPI.PARA.image)
    assert message.data[1].data['file'] == 'reports/cover.png'
    assert send.call_args.kwargs['allow_markdown'] is False


def test_manual_markdown_rejection_cleans_assets_and_falls_back(monkeypatch):
    target = _target_event()
    uploaded = [{'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'}]
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'cover': '![cover](qqbot-media://image/v1/t)'},
            uploaded,
            None
        ))
    )
    cleanup = Mock()
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', cleanup)
    monkeypatch.setattr(
        SDK.event_action,
        '_send_qq_api',
        Mock(return_value={
            'active': False,
            'data': {'http_status': 400, 'error': 'rejected'}
        })
    )
    fallback = Mock(return_value={'active': True, 'data': {'message_ids': ['fallback']}})
    monkeypatch.setattr(SDK.event_action, 'send_qq_msg', fallback)

    result = SDK.event_action.create_markdown_message(
        target,
        'qq_group',
        'group',
        {'content': '{{cover}}'},
        local_images={'cover': 'cover.png'}
    )

    assert result['active'] is True
    cleanup.assert_called_once_with(target, uploaded)
    assert fallback.call_args.kwargs['allow_markdown'] is False
