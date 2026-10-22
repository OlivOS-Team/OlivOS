"""QQ API V2 Markdown local-image upload and cleanup behavior."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import OlivOS
from OlivOS.adapter.qqGuild import qqGuildv2SDKCommon as common


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


def test_generated_markers_do_not_replace_matching_literal_text(monkeypatch):
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image #20px #10px](qqbot-media://image/v1/t)'},
            [],
            None
        ))
    )
    send = Mock(return_value={'active': False, 'data': {'http_status': None}})
    monkeypatch.setattr(SDK.event_action, 'create_markdown_message', send)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('literal {{image_0}} '),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    content = send.call_args.args[3]['content']
    assert content.startswith(r'literal \{\{image\_0\}\}')
    assert content.endswith('![image #20px #10px](qqbot-media://image/v1/t)')


def test_remote_markdown_image_rejects_private_network_targets(monkeypatch):
    request = Mock(side_effect=AssertionError('private URL must not be fetched'))
    monkeypatch.setattr(common.req, 'get', request)
    monkeypatch.setattr(
        SDK.event_action,
        '_validate_public_image_url',
        Mock(side_effect=ValueError('image URL must resolve to a public address'))
    )

    image, _, error = SDK.event_action._read_markdown_image(
        _target_event(), 'http://127.0.0.1/private.png'
    )

    assert image is None
    assert 'public address' in error
    request.assert_not_called()


def test_remote_markdown_image_download_stops_at_size_limit(monkeypatch):
    monkeypatch.setattr(SDK.event_action, '_validate_public_image_url', Mock())
    response = SimpleNamespace(
        status_code=200,
        headers={},
        iter_content=Mock(return_value=[b'x' * (10 * 1024 * 1024 + 1)]),
        close=Mock()
    )
    request = Mock(return_value=response)
    monkeypatch.setattr(common.req, 'get', request)

    image, _, error = SDK.event_action._read_markdown_image(
        _target_event(), 'https://example.invalid/large.png'
    )

    assert image is None
    assert '10 MB' in error
    response.close.assert_called_once()
    assert request.call_args.kwargs['stream'] is True
    assert request.call_args.kwargs['allow_redirects'] is False


def test_force_active_mixed_message_does_not_reuse_passive_ids(monkeypatch):
    call = Mock(return_value=({'active': True, 'data': {}}, None))
    monkeypatch.setattr(SDK.event_action, '_send_markdown_mixed_message', call)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('text'),
        OlivOS.messageAPI.PARA.image('image.png')
    ])

    result = SDK.event_action.send_qq_msg(
        _target_event(),
        'group',
        message,
        reply_msg_id='stale-reply-id',
        force_active=True
    )

    assert result['active'] is True
    assert call.call_args.kwargs['reply_msg_id'] is None
    assert call.call_args.kwargs['event_id'] is None
    assert call.call_args.kwargs['force_active'] is True


def test_media_upload_error_log_includes_platform_code_and_message():
    api = SimpleNamespace(
        res_code=400,
        res='{"code":40035007,"message":"图片数量超过上限"}'
    )

    error = SDK.event_action._format_markdown_image_api_failure('prepare', api)

    assert error.startswith('图片申请上传失败: HTTP 400 响应:')
    assert '40035007' in error
    assert '图片数量超过上限' in error


def test_complete_retries_platform_internal_error(monkeypatch):
    monkeypatch.setattr(common.time, 'sleep', Mock())

    class FakePrepare:
        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(
                file_name=None, file_size=None, content_type=None, md5=None, sha1=None
            )
            self.res_code = 200
            self.res = json.dumps({
                'upload_id': 'u1',
                'presigned_url': 'https://cos.example.invalid/x'
            })

        def do_api(self, req_type='POST'):
            return self.res

    class FakeUpload:
        def __init__(self, *args, **kwargs):
            self.res_code = 200
            self.res = ''
            self.res_headers = {'ETag': '"%s"' % ('a' * 32)}

        def do_api(self, req_type='PUT'):
            return self.res

    class FakeComplete:
        calls = 0

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(upload_id=None, md5=None)
            self.res_code = None
            self.res = None

        def do_api(self, req_type='POST'):
            FakeComplete.calls += 1
            if FakeComplete.calls == 1:
                self.res_code = 400
                self.res = json.dumps({'code': 40035006, 'message': '服务端内部错误'})
            else:
                self.res_code = 200
                self.res = json.dumps({
                    'image_id': 'id-1',
                    'url': 'qqbot-media://image/v1/t'
                })
            return self.res

    monkeypatch.setattr(SDK.API, 'prepareMediaImage', FakePrepare)
    monkeypatch.setattr(SDK.API, 'uploadMediaImage', FakeUpload)
    monkeypatch.setattr(SDK.API, 'completeMediaImage', FakeComplete)

    uploaded, error = SDK.event_action._upload_markdown_image(
        _target_event(),
        {
            'bytes': b'image', 'file_name': 'image.png', 'content_type': 'image/png',
            'width': 20, 'height': 10, 'md5': 'a' * 32, 'sha1': 'b' * 40
        }
    )

    assert error is None
    assert uploaded['image_id'] == 'id-1'
    assert FakeComplete.calls == 2
    common.time.sleep.assert_called_once()


def test_prepare_does_not_retry_quota_exceeded(monkeypatch):
    monkeypatch.setattr(common.time, 'sleep', Mock())

    class FakePrepare:
        calls = 0

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(
                file_name=None, file_size=None, content_type=None, md5=None, sha1=None
            )
            self.res_code = None
            self.res = None

        def do_api(self, req_type='POST'):
            FakePrepare.calls += 1
            self.res_code = 400
            self.res = json.dumps({'code': 40035007, 'message': '图片数量超过上限'})
            return self.res

    monkeypatch.setattr(SDK.API, 'prepareMediaImage', FakePrepare)

    uploaded, error = SDK.event_action._upload_markdown_image(
        _target_event(),
        {
            'bytes': b'image', 'file_name': 'image.png', 'content_type': 'image/png',
            'width': 20, 'height': 10, 'md5': 'a' * 32, 'sha1': 'b' * 40
        }
    )

    assert uploaded is None
    assert '40035007' in error
    assert '图片数量超过上限' in error
    assert FakePrepare.calls == 1
    common.time.sleep.assert_not_called()


def test_mixed_markdown_rejection_fallback_keeps_force_active(monkeypatch):
    uploaded = [{'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'}]
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image](qqbot-media://image/v1/t)'},
            uploaded,
            None
        ))
    )
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', Mock())
    monkeypatch.setattr(
        SDK.event_action,
        'create_markdown_message',
        Mock(return_value={'active': False, 'data': {'http_status': 400}})
    )
    fallback = Mock(return_value={'active': True, 'data': {}})
    monkeypatch.setattr(SDK.event_action, 'send_qq_msg', fallback)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('text'),
        OlivOS.messageAPI.PARA.image('image.png')
    ])

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message, force_active=True
    )

    assert error is None
    assert result['active'] is True
    assert fallback.call_args.kwargs['force_active'] is True
    assert fallback.call_args.kwargs['allow_markdown'] is False
