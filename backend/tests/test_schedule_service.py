"""Testes dos agendamentos de Network Discovery."""

from datetime import datetime

import pytest

from app.services.schedule_service import calculate_next_run, schedule_expression


def test_custom_tuesday_and_thursday_schedule():
    next_run = calculate_next_run(
        {
            "frequency": "custom",
            "time": "10:00",
            "days": [1, 3],  # terça e quinta
            "timezone": "America/Sao_Paulo",
        },
        after=datetime(2026, 9, 21, 12, 0),  # segunda, 09:00 BRT
    )

    assert next_run == datetime(2026, 9, 22, 13, 0)
    assert schedule_expression({"frequency": "custom", "time": "10:00", "days": [1, 3]}) == "0 10 * * 2,4"


def test_biweekly_schedule_is_fourteen_days_later():
    next_run = calculate_next_run(
        {
            "frequency": "biweekly",
            "time": "02:00",
            "timezone": "America/Sao_Paulo",
        },
        after=datetime(2026, 9, 22, 15, 0),
    )

    assert next_run == datetime(2026, 10, 6, 5, 0)


def test_schedule_requires_valid_weekdays():
    with pytest.raises(ValueError, match="dia da semana"):
        calculate_next_run({
            "frequency": "custom",
            "time": "10:00",
            "days": [],
            "timezone": "America/Sao_Paulo",
        })
