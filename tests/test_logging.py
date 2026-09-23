"""Logger serialization, filtering and independent file/GUI sinks."""

import queue

import pytest

import OlivOS


@pytest.mark.parametrize('value,expected', [('bad\ud800', 'bad\\ud800'), (123, '123'), (None, 'None')])
def test_log_text_is_utf8_safe(value, expected):
    assert OlivOS.diagnoseAPI.safe_text(value) == expected


def test_unprintable_object_does_not_break_logger():
    class Broken:
        def __str__(self):
            raise ValueError('unprintable')

        def __repr__(self):
            raise ValueError('unprintable')

    assert OlivOS.diagnoseAPI.safe_text(Broken()) == '<unprintable>'


def test_log_display_mode_persists_and_invalid_settings_fall_back(tmp_path):
    logging = OlivOS.diagnoseAPI
    assert logging.load_log_display_mode(tmp_path) == 'op'
    with pytest.raises(ValueError):
        logging.save_log_display_mode('unsupported', tmp_path)
    logging.save_log_display_mode('cq', tmp_path)
    assert logging.load_log_display_mode(tmp_path) == 'cq'
    path = tmp_path / logging.log_display_file
    path.write_text('{invalid', encoding='utf-8')
    assert logging.load_log_display_mode(tmp_path) == 'op'


def test_log_message_format_converts_segments_without_changing_op_source():
    source = 'User: [OP:at,id=42,name=Alice][OP:face,id=311] text [CQ:at,qq=7]'
    assert OlivOS.diagnoseAPI.format_log_message(source, 'op') == (
        'User: [OP:at,id=42,name=Alice][OP:face,id=311] text [OP:at,id=7]'
    )
    assert OlivOS.diagnoseAPI.format_log_message(source, 'cq') == (
        'User: [CQ:at,qq=42,name=Alice][CQ:face,id=311] text [CQ:at,qq=7]'
    )
    assert OlivOS.diagnoseAPI.format_log_message(source, 'invalid') == source


def test_log_message_format_only_renames_at_id_and_preserves_other_fields():
    source = (r'[OP:mface,face_id=556,emoji_id=22,id=99,ext=x\,id=y]'
              r'[OP:face,id=311][OP:reply,id=12][OP:custom,id=6]'
              r'[OP:at,name=A\,id=mask,id=42]')
    expected = (r'[CQ:mface,face_id=556,emoji_id=22,id=99,ext=x\,id=y]'
                r'[CQ:face,id=311][CQ:reply,id=12][CQ:custom,id=6]'
                r'[CQ:at,name=A\,id=mask,qq=42]')
    assert OlivOS.diagnoseAPI.format_log_message(source, 'cq') == expected
    assert OlivOS.diagnoseAPI.format_log_message(expected, 'op') == source


def test_log_packet_is_sanitized_before_queueing():
    packets = queue.Queue()
    logger = OlivOS.diagnoseAPI.logger(logger_queue=packets)
    logger.log(2, 'bad\ud800', [('segment\ud800', 'default')])
    packet = packets.get_nowait()
    assert packet['log_message'] == 'bad\\ud800'
    assert packet['log_segment'] == [('segment\\ud800', 'default')]


def test_full_log_queue_does_not_block_producer():
    packets = queue.Queue(maxsize=1)
    packets.put('full')
    OlivOS.diagnoseAPI.logger(logger_queue=packets).log(2, 'ignored')
    assert packets.get_nowait() == 'full'


def test_console_level_filter_hides_debug(capsys):
    logger = OlivOS.diagnoseAPI.logger(logger_queue=queue.Queue(), logger_mode='console')
    logger.log_output(logger.log_packet(0, 'hidden', 1750000000))
    logger.log_output(logger.log_packet(2, 'shown', 1750000000))
    captured = capsys.readouterr().out
    assert 'shown' in captured and 'hidden' not in captured


def test_gui_receives_debug_even_when_console_filters_it():
    control = queue.Queue()
    logger = OlivOS.diagnoseAPI.logger(logger_queue=queue.Queue(), logger_mode=['native'], control_queue=control)
    logger.log_output(logger.log_packet(0, 'debug', 1750000000))
    packet = control.get_nowait()
    assert packet.key['target']['type'] == 'nativeWinUI'
    assert packet.key['data']['data']['str'] == 'debug'


def test_log_files_receive_complete_batch(tmp_path):
    (tmp_path / 'logfile').mkdir()
    logger = OlivOS.diagnoseAPI.logger(logger_queue=queue.Queue(), logger_mode=['logfile'])
    for index in range(10):
        logger.log_output(logger.log_packet(2, 'row-' + str(index), 1750000000))
    text = (tmp_path / 'logfile/OlivOS_logfile_unity.log').read_text(encoding='utf-8')
    assert all('row-' + str(index) in text for index in range(10))
    assert len(list((tmp_path / 'logfile').glob('*.log'))) == 2
