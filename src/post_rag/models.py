from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class QueryType(StrEnum):
    SHIPMENT_REQUEST = "shipment_request"
    GENERAL_REGULATION = "general_regulation"
    CONVERSATION_CONTROL = "conversation_control"
    OUT_OF_SCOPE = "out_of_scope"
    NEED_MORE_INFO = "need_more_info"


class RequestedOutput(StrEnum):
    ITEM_POLICY = "item_policy"
    AVAILABLE_SERVICES = "available_services"
    EMS_RATE = "ems_rate"
    GENERAL_ANSWER = "general_answer"


class SlotOperation(StrEnum):
    KEEP = "keep"
    REPLACE = "replace"
    ADD = "add"
    REMOVE = "remove"
    CLEAR = "clear"


class Item(BaseModel):
    original_name: str
    normalized_name: str
    quantity: int | None = None
    categories: list[str] = Field(default_factory=list)


class Dimensions(BaseModel):
    width_cm: float
    height_cm: float
    depth_cm: float


class ShipmentSlots(BaseModel):
    destination_code: str | None = None
    destination_name: str | None = None
    items: list[Item] = Field(default_factory=list)
    actual_weight_g: int | None = None
    dimensions_cm: Dimensions | None = None
    preferred_service: str | None = None


class SlotUpdate(BaseModel):
    field: Literal[
        "destination",
        "items",
        "actual_weight_g",
        "dimensions_cm",
        "preferred_service",
    ]
    operation: SlotOperation
    value: object | None = None


class RequestAnalysis(BaseModel):
    query_type: QueryType
    requested_outputs: list[RequestedOutput] = Field(default_factory=list)
    updates: list[SlotUpdate] = Field(default_factory=list)


class OperationPlan(BaseModel):
    operations: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ServiceCondition(BaseModel):
    service: str
    max_weight_g: int | None = None
    max_size: str | None = None
    rate_zone: str | None = None
    fields: dict[str, str] = Field(default_factory=dict)


class CountryConditions(BaseModel):
    code: str
    name_ko: str
    services: list[ServiceCondition]
    source_urls: dict[str, str]
    collected_at: str


class Evidence(BaseModel):
    evidence_id: str
    document_id: str
    title: str
    content: str
    country_code: str
    service_type: str
    source_type: str
    source_url: str | None = None
    collected_at: str | None = None


class ItemStatus(StrEnum):
    PROHIBITED = "prohibited"
    RESTRICTED = "restricted"
    NO_RESTRICTION_FOUND = "no_restriction_found"
    CONFLICTING = "conflicting"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class EvidenceQuote(BaseModel):
    evidence_id: str
    quote: str


class ItemDecision(BaseModel):
    item: str
    status: ItemStatus
    reason: str
    evidence: list[EvidenceQuote] = Field(default_factory=list)

