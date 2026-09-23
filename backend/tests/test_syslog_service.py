from datetime import datetime, timezone, timedelta

from app.services.log_service import normalize_filters, split_terms, sustained_threshold_met, threshold_met
from app.services.syslog_service import SyslogMessage


def test_parse_rfc5424_with_structured_properties():
    message = SyslogMessage(
        '<34>1 2026-09-23T10:20:30Z router01 sshd 123 ID47 '
        '[exampleSDID@32473 user="kleber" action="login"] failed password',
        '192.168.0.1',
        514,
        'udp',
    )

    assert message.facility_name == 'auth'
    assert message.severity_name == 'critical'
    assert message.hostname == 'router01'
    assert message.app_name == 'sshd'
    assert message.message == 'failed password'
    assert message.properties['user'] == 'kleber'
    assert message.properties['action'] == 'login'


def test_parse_rfc3164():
    message = SyslogMessage(
        '<13>Sep 23 10:20:30 web01 nginx[321]: upstream timeout',
        '192.168.0.10',
        5514,
        'tcp',
    )

    assert message.facility_name == 'user'
    assert message.severity_name == 'notice'
    assert message.hostname == 'web01'
    assert message.app_name == 'nginx'
    assert message.proc_id == '321'
    assert message.message == 'upstream timeout'


def test_terms_and_filter_normalization():
    assert split_terms('"failed password" firewall,blocked') == [
        'failed password', 'firewall', 'blocked'
    ]
    assert normalize_filters({'q': 'error timeout', 'severity': 'error,critical'}) == {
        'terms': ['error', 'timeout'], 'severities': ['error', 'critical']
    }


def test_threshold_operators():
    assert threshold_met(3, '>=', 3)
    assert threshold_met(4, '>', 3)
    assert threshold_met(3, '==', 3)
    assert threshold_met(2, '<=', 3)
    assert not threshold_met(2, '>=', 3)


def test_sustained_threshold_requires_count_and_three_minute_span():
    assert not sustained_threshold_met(9, '>=', 10, 180, 180)
    assert not sustained_threshold_met(10, '>=', 10, 179, 180)
    assert sustained_threshold_met(10, '>=', 10, 180, 180)


def test_filter_datetimes_are_normalized_to_naive_utc():
    source = datetime(2026, 9, 23, 12, 0, tzinfo=timezone(timedelta(hours=-3)))
    result = normalize_filters({'from_time': source})

    assert result['from_time'] == datetime(2026, 9, 23, 15, 0)
    assert result['from_time'].tzinfo is None
