from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class CreateRecordRequest(StrictModel):
    organization_id: str = Field(min_length=1, max_length=120)
    location_id: str | None = Field(default=None, max_length=120)
    department_id: str | None = Field(default=None, max_length=120)
    idempotency_key: str | None = Field(default=None, max_length=200)
    data: dict[str, Any] = Field(default_factory=dict)


class PatchRecordRequest(StrictModel):
    expected_version: int | None = Field(default=None, ge=1)
    data: dict[str, Any] = Field(default_factory=dict)


class GlobalIQRequest(StrictModel):
    question: str = Field(min_length=3, max_length=1000)


class ImportPreviewRequest(StrictModel):
    idempotency_key: str = Field(min_length=1, max_length=200)
    import_type: str = Field(min_length=1, max_length=100)
    rows: list[dict[str, Any]] = Field(max_length=10_000)


class SyncQueueRequest(StrictModel):
    operation_type: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any]
    idempotency_key: str = Field(min_length=1, max_length=200)
    client_created_at: str | None = None

