"""Adaptive metric baselines and alert lifecycle."""

import math
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.alert import Alert, AlertStatus
from app.models.metric import AgentAnomalyEvent, AgentBaseline
from app.services.log_service import sustained_threshold_met
from app.utils.time import utcnow_naive

settings = get_settings()


async def evaluate_agent_baselines(db: AsyncSession, agent, values: dict) -> list[dict]:
    results = []
    for metric_name, raw_value in values.items():
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        baseline = await db.scalar(select(AgentBaseline).where(
            AgentBaseline.agent_id == agent.id,
            AgentBaseline.metric_name == metric_name,
        ))
        if not baseline:
            baseline = AgentBaseline(agent_id=agent.id, metric_name=metric_name)
            db.add(baseline)

        limit = baseline.upper_bound
        exceeded_pct = ((value - limit) / limit * 100.0) if limit and value > limit else 0.0
        anomalous = (
            baseline.sample_count >= settings.BASELINE_MIN_SAMPLES
            and limit is not None
            and value > limit
            and exceeded_pct >= settings.BASELINE_MIN_EXCESS_PERCENT
        )
        alert = await db.scalar(select(Alert).where(
            Alert.category == "agent_baseline",
            Alert.status != AlertStatus.RESOLVED,
            Alert.details["agent_id"].astext == str(agent.id),
            Alert.details["metric_name"].astext == metric_name,
        ))
        now = utcnow_naive()
        occurrence_count = 0
        span_seconds = 0
        sustained = False
        if anomalous:
            db.add(AgentAnomalyEvent(
                agent_id=agent.id, metric_name=metric_name, value=value,
                baseline=baseline.mean, upper_bound=limit, exceeded_pct=exceeded_pct,
                occurred_at=now,
            ))
            await db.flush()
            cutoff = now - timedelta(minutes=settings.BASELINE_WINDOW_MINUTES)
            occurrence_count, first_at, last_at = (await db.execute(
                select(
                    func.count(AgentAnomalyEvent.id),
                    func.min(AgentAnomalyEvent.occurred_at),
                    func.max(AgentAnomalyEvent.occurred_at),
                ).where(
                    AgentAnomalyEvent.agent_id == agent.id,
                    AgentAnomalyEvent.metric_name == metric_name,
                    AgentAnomalyEvent.occurred_at >= cutoff,
                )
            )).one()
            occurrence_count = int(occurrence_count or 0)
            span_seconds = int((last_at - first_at).total_seconds()) if first_at and last_at else 0
            sustained = sustained_threshold_met(
                occurrence_count, ">=", settings.BASELINE_MIN_OCCURRENCES,
                span_seconds, settings.BASELINE_MIN_SPAN_SECONDS,
            )

        if anomalous and sustained:
            details = {
                "entity_type": "agent", "agent_id": str(agent.id), "metric_name": metric_name,
                "value": round(value, 3), "baseline": round(baseline.mean, 3),
                "upper_bound": round(limit, 3), "exceeded_percent": round(exceeded_pct, 2),
                "samples": baseline.sample_count,
                "occurrences": occurrence_count,
                "window_minutes": settings.BASELINE_WINDOW_MINUTES,
                "span_seconds": span_seconds,
            }
            message = (
                f"{metric_name} superou o baseline em {exceeded_pct:.1f}%: "
                f"valor {value:.2f}, baseline {baseline.mean:.2f}, limite {limit:.2f}; "
                f"{occurrence_count} ocorrências em {settings.BASELINE_WINDOW_MINUTES} minutos "
                f"durante {span_seconds} segundos."
            )
            if alert:
                alert.message = message
                alert.details = details
                alert.last_occurrence = utcnow_naive()
                alert.occurrence_count += 1
            else:
                db.add(Alert(
                    device_id=agent.device_id, title=f"Baseline superado: {agent.hostname} / {metric_name}",
                    message=message, severity="high", category="agent_baseline", details=details,
                ))
            baseline.last_exceeded_pct = exceeded_pct
        elif not anomalous:
            if alert:
                alert.status = AlertStatus.RESOLVED
                alert.resolved_at = utcnow_naive()
            # Do not teach the baseline with detected anomalies.
            count = baseline.sample_count + 1
            delta = value - baseline.mean
            mean = baseline.mean + delta / count
            m2 = baseline.m2 + delta * (value - mean)
            stddev = math.sqrt(m2 / max(count - 1, 1))
            baseline.sample_count, baseline.mean, baseline.m2, baseline.stddev = count, mean, m2, stddev
            baseline.minimum = value if baseline.minimum is None else min(baseline.minimum, value)
            baseline.maximum = value if baseline.maximum is None else max(baseline.maximum, value)
            baseline.upper_bound = mean + settings.BASELINE_SIGMA * stddev
            baseline.status = "active" if count >= settings.BASELINE_MIN_SAMPLES else "learning"
            baseline.last_exceeded_pct = None
        elif alert and not sustained:
            alert.status = AlertStatus.RESOLVED
            alert.resolved_at = now
        baseline.last_value = value
        results.append({
            "metric_name": metric_name, "anomalous": anomalous, "sustained": sustained,
            "occurrences": occurrence_count, "span_seconds": span_seconds,
        })
    await db.execute(delete(AgentAnomalyEvent).where(
        AgentAnomalyEvent.occurred_at < utcnow_naive() - timedelta(days=1)
    ))
    return results
