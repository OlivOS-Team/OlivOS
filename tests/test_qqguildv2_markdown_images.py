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
        Mock(return_value=(None, [], 'cover: 图片超过 10MB 素材上限'))
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
    assert result['data']['markdown_fallback'].startswith('cover: 图片超过')
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
    assert content.startswith('literal {{image_0}} ')
    assert content.endswith('![image #20px #10px](qqbot-media://image/v1/t)')


def test_mixed_markdown_keeps_skill_check_brackets(monkeypatch):
    monkeypatch.setattr(
        SDK.event_action,
        '_upload_markdown_images',
        Mock(return_value=(
            {'image_0': '![image #20px #10px](qqbot-media://image/v1/t)'},
            [],
            None
        ))
    )
    send = Mock(return_value={'active': True, 'data': {'http_status': 200}})
    monkeypatch.setattr(SDK.event_action, 'create_markdown_message', send)
    monkeypatch.setattr(SDK.event_action, '_delete_markdown_images', Mock())
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('[Desom]进行技能[50]检定: 1D100=53/50 失败。'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    content = send.call_args.args[3]['content']
    assert content.startswith('[Desom]进行技能[50]检定')
    assert r'\[' not in content
    assert '![image #20px #10px](qqbot-media://image/v1/t)' in content


def test_remote_markdown_image_rejects_private_network_targets(monkeypatch):
    request = Mock(side_effect=AssertionError('private URL must not be fetched'))
    monkeypatch.setattr(common.req, 'get', request)
    monkeypatch.setattr(
        SDK.event_action,
        '_validate_public_image_url',
        Mock(side_effect=ValueError('图片 URL 必须解析到公网地址'))
    )

    image, _, error = SDK.event_action._read_markdown_image(
        _target_event(), 'http://127.0.0.1/private.png'
    )

    assert image is None
    assert '公网地址' in error
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
    # 不依赖真实 DNS：下载走"解析→校验→钉住解析"流程，这里直接给出合法解析结果。
    monkeypatch.setattr(
        SDK.event_action,
        '_resolve_public_image_addresses',
        Mock(return_value=['203.0.113.10'])
    )

    image, _, error = SDK.event_action._read_markdown_image(
        _target_event(), 'https://example.invalid/large.png'
    )

    assert image is None
    assert '10MB' in error
    response.close.assert_called_once()
    assert request.call_args.kwargs['stream'] is True
    assert request.call_args.kwargs['allow_redirects'] is False


def test_mixed_markdown_with_reply_falls_back_to_plain_message(monkeypatch):
    """QQ 不支持 Markdown 图文+引用：带 reply 段时整条回退普通图文，引用交给旧路径。"""
    upload = Mock(side_effect=AssertionError('带引用的消息不应走 Markdown 上传'))
    monkeypatch.setattr(SDK.event_action, '_upload_markdown_images', upload)
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.reply('ROBOT1.0_quote'),
        OlivOS.messageAPI.PARA.image('https://i0.hdslb.com/cover.jpg'),
        OlivOS.messageAPI.PARA.text('BV号：BV184JQ6LEW9')
    ])

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    assert result is None
    assert '引用' in error
    upload.assert_not_called()


def test_mixed_markdown_rejects_real_media_segments_with_type_name(monkeypatch):
    """视频/语音/文件这类 Markdown 表达不了的段仍然回退，并在错误里点出段类型。"""
    message = OlivOS.messageAPI.Message_templet('olivos_para', [
        OlivOS.messageAPI.PARA.text('text'),
        OlivOS.messageAPI.PARA.video('https://example.com/a.mp4'),
        OlivOS.messageAPI.PARA.image('images/a.png')
    ])

    result, error = SDK.event_action._send_markdown_mixed_message(
        _target_event(), 'qq_group', 'group', message
    )

    assert result is None
    assert '不支持的媒体段' in error
    assert 'video' in error


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


def test_force_active_conflicts_with_msg_id_even_without_local_images():
    """互斥校验不限定 local_images：不带本地图也必须报错，不能静默丢弃 msg_id。"""
    result = SDK.event_action.create_markdown_message(
        _target_event(),
        'qq_group',
        'group',
        {'content': 'hello'},
        msg_id='reply-id',
        force_active=True
    )

    assert result['data']['error'] == 'force_active cannot be combined with msg_id or event_id'


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


def test_upload_5xx_restarts_pipeline_with_new_prepare(monkeypatch):
    """直传 5xx 后预签名 URL 已被消耗，必须整段重跑并以新 upload_id 完成。"""
    monkeypatch.setattr(common.time, 'sleep', Mock())

    class FakePrepare:
        calls = 0

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(
                file_name=None, file_size=None, content_type=None, md5=None, sha1=None
            )
            self.res_code = 200

        def do_api(self, req_type='POST'):
            FakePrepare.calls += 1
            self.res = json.dumps({
                'upload_id': 'u%d' % FakePrepare.calls,
                'presigned_url': 'https://cos.example.invalid/x'
            })
            return self.res

    class FakeUpload:
        calls = 0

        def __init__(self, url=None, content_type=None, file_data=None):
            self.res_code = None
            self.res = ''
            self.res_headers = {'ETag': '"%s"' % ('a' * 32)}

        def do_api(self, req_type='PUT'):
            FakeUpload.calls += 1
            if FakeUpload.calls == 1:
                # 第一次直传服务端内部错误（可重试）。
                self.res_code = 502
                self.res = 'upstream error'
            else:
                self.res_code = 200
            return self.res

    class FakeComplete:
        submitted_upload_ids = []

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(upload_id=None, md5=None)
            self.res_code = 200
            self.res = json.dumps({'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'})

        def do_api(self, req_type='POST'):
            FakeComplete.submitted_upload_ids.append(self.data.upload_id)
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
    # 整段重跑：prepare 两次，complete 用的是第二轮的新 upload_id。
    assert FakePrepare.calls == 2
    assert FakeUpload.calls == 2
    assert FakeComplete.submitted_upload_ids == ['u2']


def test_complete_md5_mismatch_restarts_pipeline_with_new_upload_id(monkeypatch):
    """complete 报 40035003（md5 比对失败）时单步重试无意义，整段重跑换新任务。"""
    monkeypatch.setattr(common.time, 'sleep', Mock())

    class FakePrepare:
        calls = 0

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(
                file_name=None, file_size=None, content_type=None, md5=None, sha1=None
            )
            self.res_code = 200

        def do_api(self, req_type='POST'):
            FakePrepare.calls += 1
            self.res = json.dumps({
                'upload_id': 'u%d' % FakePrepare.calls,
                'presigned_url': 'https://cos.example.invalid/x'
            })
            return self.res

    class FakeUpload:
        def __init__(self, url=None, content_type=None, file_data=None):
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
                self.res = json.dumps({'code': 40035003, 'message': 'MD5 校验失败'})
            else:
                self.res_code = 200
                self.res = json.dumps({'image_id': 'id-1', 'url': 'qqbot-media://image/v1/t'})
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
    assert FakePrepare.calls == 2


def test_upload_pipeline_gives_up_after_retry_budget(monkeypatch):
    """持续 5xx 时按重试预算止损，最终返回失败原因；prepare 只跑整段两次。"""
    monkeypatch.setattr(common.time, 'sleep', Mock())
    # 预算收紧，避免真实等待。
    monkeypatch.setattr(common, 'qqMediaImageApiRetryBudget', 0.05)

    class FakePrepare:
        calls = 0

        def __init__(self, bot_info=None):
            self.data = SimpleNamespace(
                file_name=None, file_size=None, content_type=None, md5=None, sha1=None
            )
            self.res_code = 200

        def do_api(self, req_type='POST'):
            FakePrepare.calls += 1
            self.res = json.dumps({
                'upload_id': 'u%d' % FakePrepare.calls,
                'presigned_url': 'https://cos.example.invalid/x'
            })
            return self.res

    class FakeUpload:
        def __init__(self, url=None, content_type=None, file_data=None):
            self.res_code = 500
            self.res = 'server error'
            self.res_headers = {}

        def do_api(self, req_type='PUT'):
            return self.res

    monkeypatch.setattr(SDK.API, 'prepareMediaImage', FakePrepare)
    monkeypatch.setattr(SDK.API, 'uploadMediaImage', FakeUpload)

    uploaded, error = SDK.event_action._upload_markdown_image(
        _target_event(),
        {
            'bytes': b'image', 'file_name': 'image.png', 'content_type': 'image/png',
            'width': 20, 'height': 10, 'md5': 'a' * 32, 'sha1': 'b' * 40
        }
    )

    assert uploaded is None
    assert '图片直传图片失败' in error
    # PUT 不做同 URL 重试，两轮整段（各一次 prepare + 一次 PUT）后止损。
    assert FakePrepare.calls == 2


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
