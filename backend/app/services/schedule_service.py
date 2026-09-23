"""Cálculo dos próximos horários de execução dos discoveries agendados."""

from calendar import monthrange
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


VALID_FREQUENCIES = {"daily", "weekly", "biweekly", "monthly", "custom"}


def _parse_time(value: str) -> time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise ValueError("Horário do agendamento deve usar o formato HH:MM") from exc


def _timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Timezone inválido: {name}") from exc


def calculate_next_run(config: dict, after: datetime | None = None) -> datetime:
    """Calcula a próxima execução e retorna UTC sem tzinfo para o schema legado."""
    frequency = config.get("frequency")
    if frequency not in VALID_FREQUENCIES:
        raise ValueError("Frequência de agendamento inválida")

    tz = _timezone(config.get("timezone", "America/Sao_Paulo"))
    run_time = _parse_time(config.get("time", "02:00"))
    after_utc = (after or datetime.now(timezone.utc).replace(tzinfo=None)).replace(
        tzinfo=timezone.utc
    )
    local_now = after_utc.astimezone(tz)

    def at_local(day) -> datetime:
        return datetime.combine(day, run_time, tzinfo=tz)

    if frequency == "daily":
        candidate = at_local(local_now.date())
        if candidate <= local_now:
            candidate += timedelta(days=1)
    elif frequency == "biweekly":
        candidate = at_local(local_now.date() + timedelta(days=14))
    elif frequency in {"weekly", "custom"}:
        days = sorted(set(config.get("days") or []))
        if not days or any(day < 0 or day > 6 for day in days):
            raise ValueError("Selecione ao menos um dia da semana válido")
        candidate = None
        for offset in range(0, 8):
            day = local_now.date() + timedelta(days=offset)
            option = at_local(day)
            if day.weekday() in days and option > local_now:
                candidate = option
                break
        if candidate is None:  # pragma: no cover
            raise ValueError("Não foi possível calcular o próximo dia agendado")
    else:
        day_of_month = int(config.get("day_of_month", 1))
        if day_of_month < 1 or day_of_month > 28:
            raise ValueError("O dia mensal deve estar entre 1 e 28")
        year, month = local_now.year, local_now.month
        candidate = at_local(local_now.date().replace(day=day_of_month))
        if candidate <= local_now:
            month = 1 if month == 12 else month + 1
            year = year + 1 if local_now.month == 12 else year
            day = min(day_of_month, monthrange(year, month)[1])
            candidate = at_local(local_now.date().replace(year=year, month=month, day=day))

    return candidate.astimezone(timezone.utc).replace(tzinfo=None)


def schedule_expression(config: dict) -> str:
    """Gera representação compacta do agendamento para auditoria."""
    parsed_time = _parse_time(config.get("time", "02:00"))
    hour, minute = parsed_time.hour, parsed_time.minute
    frequency = config["frequency"]
    if frequency == "daily":
        return f"{minute} {hour} * * *"
    if frequency == "monthly":
        return f"{minute} {hour} {int(config.get('day_of_month', 1))} * *"
    if frequency == "biweekly":
        return f"@biweekly {hour:02d}:{minute:02d}"
    cron_days = ",".join(str((day + 1) % 7) for day in config.get("days", []))
    return f"{minute} {hour} * * {cron_days}"
