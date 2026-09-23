"""Time-series metrics and adaptive baselines for devices and agents."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.database import Base


class DeviceMetric(Base):
    __tablename__ = "device_metrics"
    __table_args__ = (Index("ix_device_metrics_device_time", "device_id", "collected_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    in_bps = Column(Float, nullable=True)
    out_bps = Column(Float, nullable=True)
    utilization_in = Column(Float, nullable=True)
    utilization_out = Column(Float, nullable=True)
    interfaces_up = Column(Integer, nullable=True)
    interfaces_down = Column(Integer, nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentMetric(Base):
    __tablename__ = "agent_metrics"
    __table_args__ = (Index("ix_agent_metrics_agent_time", "agent_id", "collected_at"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_registrations.id", ondelete="CASCADE"), nullable=False)
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    load_1m = Column(Float, nullable=True)
    load_5m = Column(Float, nullable=True)
    load_15m = Column(Float, nullable=True)
    network_bytes_sent = Column(BigInteger, nullable=True)
    network_bytes_recv = Column(BigInteger, nullable=True)
    network_packets_sent = Column(BigInteger, nullable=True)
    network_packets_recv = Column(BigInteger, nullable=True)
    network_send_bps = Column(Float, nullable=True)
    network_recv_bps = Column(Float, nullable=True)
    disk_read_bytes = Column(BigInteger, nullable=True)
    disk_write_bytes = Column(BigInteger, nullable=True)
    disk_read_bps = Column(Float, nullable=True)
    disk_write_bps = Column(Float, nullable=True)
    process_count = Column(Integer, nullable=True)
    boot_time = Column(DateTime, nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
    collected_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentBaseline(Base):
    """Online Welford baseline, one row per agent and metric."""

    __tablename__ = "agent_baselines"
    __table_args__ = (
        UniqueConstraint("agent_id", "metric_name", name="uq_agent_baseline_metric"),
        Index("ix_agent_baselines_agent", "agent_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_registrations.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(80), nullable=False)
    sample_count = Column(Integer, nullable=False, default=0)
    mean = Column(Float, nullable=False, default=0.0)
    m2 = Column(Float, nullable=False, default=0.0)
    stddev = Column(Float, nullable=False, default=0.0)
    minimum = Column(Float, nullable=True)
    maximum = Column(Float, nullable=True)
    upper_bound = Column(Float, nullable=True)
    status = Column(String(20), nullable=False, default="learning")
    last_value = Column(Float, nullable=True)
    last_exceeded_pct = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AgentAnomalyEvent(Base):
    """Individual anomalous samples used to enforce a sustained alert window."""

    __tablename__ = "agent_anomaly_events"
    __table_args__ = (
        Index("ix_agent_anomaly_agent_metric_time", "agent_id", "metric_name", "occurred_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_registrations.id", ondelete="CASCADE"), nullable=False)
    metric_name = Column(String(80), nullable=False)
    value = Column(Float, nullable=False)
    baseline = Column(Float, nullable=False)
    upper_bound = Column(Float, nullable=False)
    exceeded_pct = Column(Float, nullable=False)
    occurred_at = Column(DateTime, default=datetime.utcnow, nullable=False)
