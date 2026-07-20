from __future__ import annotations

import asyncio
import json
import os
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from pymongo import AsyncMongoClient, ReturnDocument

from .config import Settings, settings
from .seed import demo_dataset

DOMAIN_COLLECTIONS = [
    "organizations",
    "concepts",
    "regions",
    "locations",
    "departments",
    "storage-areas",
    "users",
    "roles",
    "permissions",
    "vendors",
    "vendor-contacts",
    "contracts",
    "catalogs",
    "items",
    "vendor-skus",
    "purchase-units",
    "count-units",
    "recipe-units",
    "conversion-factors",
    "item-aliases",
    "categories",
    "allergens",
    "gl-accounts",
    "tax-charge-rules",
    "budgets",
    "forecasts",
    "purchase-requests",
    "orders",
    "order-lines",
    "deliveries",
    "receiving",
    "documents",
    "invoices",
    "invoice-lines",
    "credits",
    "bills",
    "payments",
    "inventory",
    "audits",
    "audit-lines",
    "transfers",
    "waste",
    "depletions",
    "production",
    "recipes",
    "recipe-versions",
    "recipe-ingredients",
    "menus",
    "pos-items",
    "pos-mappings",
    "modifiers",
    "sales",
    "labor",
    "operating-day-summaries",
    "logbook",
    "tasks",
    "alerts",
    "recommendations",
    "approvals",
    "comments",
    "integrations",
    "sync-jobs",
    "data-quality-issues",
    "audit-logs",
    "reports",
    "analytics",
    "global-iq",
    "command-cards",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(record: Any) -> Any:
    return json.loads(json.dumps(record, default=str))


class Repository(Protocol):
    async def initialize(self) -> None: ...
    async def list(self, collection: str, filters: dict[str, Any] | None = None, limit: int = 50, offset: int = 0, sort: str | None = None) -> tuple[list[dict], int]: ...
    async def get(self, collection: str, record_id: str) -> dict | None: ...
    async def create(self, collection: str, record: dict[str, Any]) ->dict: ...
    async def update(self, collection: str, record_id: str, patch: dict[str, Any], expected_version: int | None = None) -> dict: ...
    async def find_one(self, collection: str, filters: dict[str, Any])-> dict | None: ...
    async def append_audit_event(self, event: dict[str, Any]) -> None:...


def ensure_collection(collection: str) -> None:
    if collection not in DOMAIN_COLLECTIONS:
        raise KeyError(collection)


def matches(record: dict[str, Any], filters: dict[str, Any] | None) ->bool:
    if record.get("deleted_at"):
        return False
    for key, value in (filters or {}).items():
        if key == "location_ids":
            location_id = record.get("location_id")
            if location_id and location_id not in value:
                return False
        elif key == "department_ids":
            department_id = record.get("department_id")
            if department_id and department_id not in value:
                return False
        elif isinstance(value, list):
            if record.get(key) not in value:
                return False
        elif record.get(key) != value:
            return False
    return True


class MemoryRepository:
    def __init__(self, initial: dict[str, list[dict]] | None = None):
        self._data: dict[str, list[dict]] = initial or {}
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._lock:
            if not self._data:
                self._data = demo_dataset()
            for collection in DOMAIN_COLLECTIONS:
                self._data.setdefault(collection, [])

    async def list(self, collection: str, filters: dict[str, Any] | None = None, limit: int = 50, offset: int = 0, sort: str | None = None) -> tuple[list[dict], int]:
        ensure_collection(collection)
        records = [deepcopy(record) for record in self._data.get(collection, []) if matches(record, filters)]
        if sort:
            reverse = sort.startswith("-")
            key = sort[1:] if reverse else sort
            records.sort(key=lambda item: item.get(key) or "", reverse=reverse)
        total = len(records)
        return records[offset : offset + limit], total

    async def get(self, collection: str, record_id: str) -> dict | None:
        ensure_collection(collection)
        for record in self._data.get(collection, []):
            if record.get("id") == record_id and not record.get("deleted_at"):
                return deepcopy(record)
        return None

    async def find_one(self, collection: str, filters: dict[str, Any])-> dict | None:
        ensure_collection(collection)
        for record in self._data.get(collection, []):
            if matches(record, filters):
                return deepcopy(record)
        return None

    async def create(self, collection: str, record: dict[str, Any]) ->dict:
        ensure_collection(collection)
        async with self._lock:
            item = _json_safe(record)
            item.setdefault("id", f"{collection}_{uuid.uuid4().hex[:12]}")
            item.setdefault("created_at", now_iso())
            item.setdefault("updated_at", now_iso())
            item.setdefault("version", 1)
            self._data.setdefault(collection, []).append(item)
            await self.append_audit_event({"actor_id": item.get("created_by", "system"), "action": "create", "domain": collection, "record_id": item["id"], "immutable": True})
            return deepcopy(item)

    async def update(self, collection: str, record_id: str, patch: dict[str, Any], expected_version: int | None = None) -> dict:
        ensure_collection(collection)
        async with self._lock:
            for index, record in enumerate(self._data.get(collection, [])):
                if record.get("id") == record_id and not record.get("deleted_at"):
                    if expected_version is not None and record.get("version") != expected_version:
                        raise ValueError("version_conflict")
                    updated = deepcopy(record)
                    updated.update(_json_safe(patch))
                    updated["updated_at"] = now_iso()
                    updated["version"] = int(updated.get("version", 1)) + 1
                    self._data[collection][index] = updated
                    await self.append_audit_event({"actor_id": updated.get("updated_by", "system"), "action": "update", "domain": collection,"record_id": record_id, "immutable": True})
                    return deepcopy(updated)
        raise KeyError(record_id)

    async def append_audit_event(self, event: dict[str, Any]) -> None:
        safe = _json_safe(event)
        safe.setdefault("id", f"auditlog_{uuid.uuid4().hex[:12]}")
        safe.setdefault("organization_id", safe.get("organization_id","org_blue_collar_demo"))
        safe.setdefault("timestamp", now_iso())
        safe.setdefault("created_at", now_iso())
        safe.setdefault("updated_at", now_iso())
        self._data.setdefault("audit-logs", []).append(safe)


class FileRepository(MemoryRepository):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    async def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self._data = json.loads(self.path.read_text())
        await super().initialize()
        await self._persist()

    async def create(self, collection: str, record: dict[str, Any]) ->dict:
        item = await super().create(collection, record)
        await self._persist()
        return item

    async def update(self, collection: str, record_id: str, patch: dict[str, Any], expected_version: int | None = None) -> dict:
        item = await super().update(collection, record_id, patch, expected_version)
        await self._persist()
        return item

    async def append_audit_event(self, event: dict[str, Any]) -> None:
        await super().append_audit_event(event)

    async def _persist(self) -> None:
        fd, temp_path = tempfile.mkstemp(prefix=self.path.name, dir=str(self.path.parent))
        with os.fdopen(fd, "w") as handle:
            json.dump(self._data, handle, indent=2, default=str)
        Path(temp_path).replace(self.path)


class MongoRepository:
    def __init__(self, uri: str, database: str):
        self.client: AsyncMongoClient = AsyncMongoClient(uri)
        self.db = self.client[database]

    async def initialize(self) -> None:
        for collection in DOMAIN_COLLECTIONS:
            await self.db[collection].create_index([("organization_id", 1), ("id", 1)], unique=False)
            await self.db[collection].create_index("id", unique=True)
            await self.db[collection].create_index("idempotency_key", unique=False, sparse=True)
        if await self.db["organizations"].count_documents({}) == 0:
            for collection, records in demo_dataset().items():
                if records:
                    await self.db[collection].insert_many(_json_safe(records))

    async def list(self, collection: str, filters: dict[str, Any] | None = None, limit: int = 50, offset: int = 0, sort: str | None = None) -> tuple[list[dict], int]:
        ensure_collection(collection)
        query = self._query(filters)
        cursor = self.db[collection].find(query, {"_id": 0}).skip(offset).limit(limit)
        if sort:
            cursor = cursor.sort(
                sort[1:] if sort.startswith("-") else sort,
                -1 if sort.startswith("-") else 1,
            )
        total = await self.db[collection].count_documents(query)
        return await cursor.to_list(None), total

    async def get(self, collection: str, record_id: str) -> dict | None:
        ensure_collection(collection)
        return await self.db[collection].find_one({"id": record_id, "deleted_at": {"$exists": False}}, {"_id": 0})

    async def find_one(self, collection: str, filters: dict[str, Any])-> dict | None:
        ensure_collection(collection)
        return await self.db[collection].find_one(self._query(filters), {"_id": 0})

    async def create(self, collection: str, record: dict[str, Any]) ->dict:
        ensure_collection(collection)
        item = _json_safe(record)
        item.setdefault("id", f"{collection}_{uuid.uuid4().hex[:12]}")
        item.setdefault("created_at", now_iso())
        item.setdefault("updated_at", now_iso())
        item.setdefault("version", 1)
        await self.db[collection].insert_one(item)
        await self.append_audit_event({"actor_id": item.get("created_by", "system"), "action": "create", "domain": collection, "record_id": item["id"], "immutable": True, "organization_id": item.get("organization_id")})
        return {key: value for key, value in item.items() if key != "_id"}

    async def update(self, collection: str, record_id: str, patch: dict[str, Any], expected_version: int | None = None) -> dict:
        ensure_collection(collection)
        query: dict[str, Any] = {"id": record_id, "deleted_at": {"$exists": False}}
        if expected_version is not None:
            query["version"] = expected_version
        update = {"$set": {**_json_safe(patch), "updated_at": now_iso()}, "$inc": {"version": 1}}
        result = await self.db[collection].find_one_and_update(
            query,
            update,
            projection={"_id": 0},
            return_document=ReturnDocument.AFTER,
        )
        if not result:
            if expected_version is not None and await self.get(collection, record_id):
                raise ValueError("version_conflict")
            raise KeyError(record_id)
        await self.append_audit_event({"actor_id": result.get("updated_by", "system"), "action": "update", "domain": collection, "record_id":record_id, "immutable": True, "organization_id": result.get("organization_id")})
        return result

    async def append_audit_event(self, event: dict[str, Any]) -> None:
        safe = _json_safe(event)
        safe.setdefault("id", f"auditlog_{uuid.uuid4().hex[:12]}")
        safe.setdefault("timestamp", now_iso())
        safe.setdefault("created_at", now_iso())
        safe.setdefault("updated_at", now_iso())
        await self.db["audit-logs"].insert_one(safe)

    @staticmethod
    def _query(filters: dict[str, Any] | None) -> dict[str, Any]:
        query: dict[str, Any] = {"deleted_at": {"$exists": False}}
        for key, value in (filters or {}).items():
            if key == "location_ids":
                query["$or"] = [{"location_id": {"$exists": False}}, {"location_id": {"$in": value}}]
            elif key == "department_ids":
                existing = query.pop("$or", [])
                dept_or = [{"department_id": {"$exists": False}}, {"department_id": {"$in": value}}]
                query["$and"] = [{"$or": existing}, {"$or": dept_or}] if existing else [{"$or": dept_or}]
            elif isinstance(value, list):
                query[key] = {"$in": value}
            else:
                query[key] = value
        return query


def build_repository(active_settings: Settings = settings) -> Repository:
    if active_settings.app_storage == "mongo":
        if not active_settings.mongodb_uri:
            raise RuntimeError("MONGODB_URI is required when APP_STORAGE=mongo.")
        return MongoRepository(active_settings.mongodb_uri, active_settings.mongodb_database)
    if active_settings.app_storage == "memory":
        return MemoryRepository()
    return FileRepository(active_settings.data_file)
