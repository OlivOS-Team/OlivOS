"""Compatibility configuration APIs still exported by OlivOS.userModule."""

from OlivOS.userModule import JyunkoUserConf


def test_legacy_user_configuration_roundtrip():
    JyunkoUserConf.setUserConf(42, 'setting', {'value': '中文'})
    assert JyunkoUserConf.getUserConf('42', 'setting') == {'value': '中文'}


def test_legacy_group_configuration_roundtrip():
    JyunkoUserConf.setGroupConf(7, 'setting', True)
    assert JyunkoUserConf.getGroupConf('7', 'setting') is True


def test_legacy_group_and_user_configuration_are_separate():
    JyunkoUserConf.setUserConf(7, 'setting', 'user')
    JyunkoUserConf.setGroupConf(7, 'setting', 'group')
    assert JyunkoUserConf.getUserConf(7, 'setting') == 'user'
    assert JyunkoUserConf.getGroupConf(7, 'setting') == 'group'


def test_legacy_missing_configuration_returns_default():
    assert JyunkoUserConf.getUserConf(42, 'missing', 'fallback') == 'fallback'
    assert JyunkoUserConf.getGroupConf(7, 'missing', 'fallback') == 'fallback'
