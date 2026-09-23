"""Shared query and threshold helpers for persistent logs."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select

from app.models.log import SyslogEvent
from app.utils.time import utcnow_naive


def split_terms(value: str | None) -> list[str]:
    """Split free text while preserving quoted expressions."""
    if not value:
        return []
    return [item.strip('"') for item in re.findall(r'"[^"]+"|[^,\s]+', value) if item.strip('"')]


def normalize_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Remove empty values and normalize list-like search fields."""
    clean = {key: value for key, value in filters.items() if value not in (None, "", [], {})}
    if isinstance(clean.get("severity"), str):
        clean["severities"] = [item.strip() for item in clean.pop("severity").split(",") if item.strip()]
    if isinstance(clean.get("severities"), str):
        clean["severities"] = [item.strip() for item in clean["severities"].split(",") if item.strip()]
    if isinstance(clean.get("q"), str):
        clean["terms"] = split_terms(clean.pop("q"))
    # PostgreSQL columns in this project use TIMESTAMP WITHOUT TIME ZONE.
    # FastAPI parses ISO values ending in Z as timezone-aware datetimes, so
    # normalize them to naive UTC before binding through asyncpg.
    for key in ("from_time", "to_time"):
        value = clean.get(key)
        if isinstance(value, datetime) and value.tzinfo is not None:
            clean[key] = value.astimezone(timezone.utc).replace(tzinfo=None)
    return clean


def apply_log_filters(query, filters: dict[str, Any], *, window_start: datetime | None = None):
    """Apply the same filter semantics to search, preview and alert evaluation."""
    data = normalize_filters(filters)
    if window_start:
        query = query.where(SyslogEvent.received_at >= window_start)
    if data.get("from_time"):
        query = query.where(SyslogEvent.received_at >= data["from_time"])
    if data.get("to_time"):
        query = query.where(SyslogEvent.received_at <= data["to_time"])
    if data.get("severities"):
        query = query.where(SyslogEvent.severity.in_(data["severities"]))
    if data.get("facility"):
        query = query.where(SyslogEvent.facility == data["facility"])
    if data.get("source_ip"):
        query = query.where(SyslogEvent.source_ip.ilike(f"%{data['source_ip']}%"))
    if data.get("hostname"):
        query = query.where(SyslogEvent.hostname.ilike(f"%{data['hostname']}%"))
    if data.get("host"):
        host = f"%{data['host']}%"
        query = query.where(or_(SyslogEvent.hostname.ilike(host), SyslogEvent.source_ip.ilike(host)))
    if data.get("app_name"):
        query = query.where(SyslogEvent.app_name.ilike(f"%{data['app_name']}%"))
    if data.get("protocol"):
        query = query.where(SyslogEvent.protocol == data["protocol"])
    if data.get("security_category"):
        query = query.where(SyslogEvent.security_category == data["security_category"])
    if data.get("property_key"):
        prop = SyslogEvent.properties[data["property_key"]].astext
        if data.get("property_value"):
            query = query.where(prop.ilike(f"%{data['property_value']}%"))
        else:
            query = query.where(prop.is_not(None))

    term_conditions = []
    for term in data.get("terms", []):
        pattern = f"%{term}%"
        term_conditions.append(or_(
            SyslogEvent.message.ilike(pattern),
            SyslogEvent.raw.ilike(pattern),
            SyslogEvent.hostname.ilike(pattern),
            SyslogEvent.app_name.ilike(pattern),
        ))
    if term_conditions:
        if data.get("match", "all") == "any":
            query = query.where(or_(*term_conditions))
        else:
            for condition in term_conditions:
                query = query.where(condition)
    return query


async def count_matching_logs(db, filters: dict[str, Any], window_minutes: int) -> int:
    cutoff = utcnow_naive() - timedelta(minutes=window_minutes)
    query = apply_log_filters(select(func.count(SyslogEvent.id)), filters, window_start=cutoff)
    return int((await db.execute(query)).scalar() or 0)


async def matching_log_stats(db, filters: dict[str, Any], window_minutes: int) -> dict:
    """Return count and temporal coverage for an alert window."""
    cutoff = utcnow_naive() - timedelta(minutes=window_minutes)
    query = apply_log_filters(
        select(func.count(SyslogEvent.id), func.min(SyslogEvent.received_at), func.max(SyslogEvent.received_at)),
        filters,
        window_start=cutoff,
    )
    count, first_at, last_at = (await db.execute(query)).one()
    span_seconds = int((last_at - first_at).total_seconds()) if first_at and last_at else 0
    return {"count": int(count or 0), "first_at": first_at, "last_at": last_at, "span_seconds": span_seconds}


def threshold_met(value: int, operator: str, threshold: int) -> bool:
    return {
        ">=": value >= threshold,
        ">": value > threshold,
        "==": value == threshold,
        "<=": value <= threshold,
        "<": value < threshold,
    }.get(operator, value >= threshold)


def sustained_threshold_met(
    value: int, operator: str, threshold: int, span_seconds: int, minimum_span_seconds: int,
) -> bool:
    return threshold_met(value, operator, threshold) and span_seconds >= minimum_span_seconds
