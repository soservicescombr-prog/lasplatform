# netguard/backend/app/schemas/snmp.py
"""
NetGuard - Schemas SNMP (Pydantic).
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SNMPCommunityCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    community_string: str = Field(..., min_length=1, max_length=255)
    snmp_version: str = "v2c"
    description: Optional[str] = None
    is_default: bool = False
    security_name: Optional[str] = None
    auth_protocol: Optional[str] = None
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None
    priv_password: Optional[str] = None
    security_level: Optional[str] = None


class SNMPCommunityUpdate(BaseModel):
    name: Optional[str] = None
    community_string: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class SNMPCommunityResponse(BaseModel):
    id: UUID
    name: str
    community_string: str
    snmp_version: str
    description: Optional[str] = None
    is_default: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SNMPInterfaceResponse(BaseModel):
    id: UUID
    device_id: UUID
    if_index: int
    if_name: Optional[str] = None
    if_descr: Optional[str] = None
    if_alias: Optional[str] = None
    if_type: Optional[int] = None
    if_type_name: Optional[str] = None
    if_speed: Optional[int] = None
    if_high_speed: Optional[int] = None
    if_admin_status: Optional[int] = None
    if_oper_status: Optional[int] = None
    if_in_octets: int = 0
    if_out_octets: int = 0
    if_in_errors: int = 0
    if_out_errors: int = 0
    if_in_discards: int = 0
    if_out_discards: int = 0
    in_bps: Optional[float] = None
    out_bps: Optional[float] = None
    utilization_in: Optional[float] = None
    utilization_out: Optional[float] = None
    last_collected: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SNMPCollectRequest(BaseModel):
    device_id: UUID
    community_id: Optional[UUID] = None


class SNMPBulkCollectRequest(BaseModel):
    community_id: Optional[UUID] = None
    device_ids: Optional[list[UUID]] = None
