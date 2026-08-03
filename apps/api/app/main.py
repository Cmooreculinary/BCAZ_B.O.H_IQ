from __future__ import annotations

import logging
import sys
import uuid
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import calculations
from .agents import AGENTS, answer_question
from .config import settings
from .models import (
    CreateRecordRequest,
    GlobalIQRequest,
    ImportPreviewRequest,
    LoginRequest,
    PatchRecordRequest,
    SyncQueueRequest,
)
from .security import TokenError, create_access_token, decode_access_token, verify_password
from .store import DOMAIN_COLLECTIONS, Repository, build_repository, now_iso


logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format='{"level":"%(levelname)s","message":"%(message)s"}',
)
logger = logging.getLogger("bcaz-boh-iq")
repository: Repository = build_repository()
bearer = HTTPBearer(auto_error=False)


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "organization_owner": {"read", "create", "update", "approve", "resolve"},
    "general_manager": {"read", "create", "update", "approve", "resolve"},
    "accounts_payable_approver": {"read", "create", "update", "approve"},
    "receiver": {"read", "create", "update"},
    "inventory_manager": {"read", "create", "update", "resolve"},
    "viewer": {"read"},
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_runtime()
    await repository.initialize()
    logger.info("API initialized")
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0-beta",
    docs_url="/docs",
    redoc_url=None,
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
)


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def envelope(data: Any, request: Request, **meta: Any) -> dict[str, Any]:
    return {"data": data, "meta": {"request_id": request_id(request), **meta}}


def error_response(request: Request, code: str, message: str, http_status: int) -> JSONResponse:
    return JSONResponse(
        status_code=http_status,
        content={
            "error": {"code": code, "message": message},
            "meta": {"request_id": request_id(request)},
        },
    )


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request.state.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "same-origin"
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, _: RequestValidationError):
    return error_response(request, "validation_error", "The request data is invalid.", 422)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return error_response(request, f"http_{exc.status_code}", str(exc.detail), exc.status_code)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled request failure: %s", type(exc).__name__)
    return error_response(request, "internal_error", "The request could not be completed.", 500)


async def current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication is required.")
    try:
        claims = decode_access_token(credentials.credentials)
    except TokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    user = await repository.get("users", claims["sub"])
    if not user or not user.get("active", False):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The account is unavailable.")
    if user.get("organization_id") != claims["organization_id"]:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "The session is invalid.")
    return user


def public_session(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_id": user["id"],
        "organization_id": user["organization_id"],
        "email": user["email"],
        "name": user["name"],
        "roles": user.get("roles", []),
        "location_ids": user.get("location_ids", []),
        "department_ids": user.get("department_ids", []),
    }


def has_permission(user: dict[str, Any], permission: str) -> bool:
    return any(permission in ROLE_PERMISSIONS.get(role, set()) for role in user.get("roles", []))


def require_permission(user: dict[str, Any], permission: str) -> None:
    if not has_permission(user, permission):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This role cannot perform that action.")


def tenant_filters(user: dict[str, Any]) -> dict[str, Any]:
    filters: dict[str, Any] = {"organization_id": user["organization_id"]}
    if "organization_owner" not in user.get("roles", []):
        filters["location_ids"] = user.get("location_ids", [])
        filters["department_ids"] = user.get("department_ids", [])
    return filters


def accessible(record: dict[str, Any] | None, user: dict[str, Any]) -> bool:
    if not record or record.get("organization_id") != user["organization_id"]:
        return False
    if "organization_owner" in user.get("roles", []):
        return True
    location_id = record.get("location_id")
    department_id = record.get("department_id")
    return (not location_id or location_id in user.get("location_ids", [])) and (
        not department_id or department_id in user.get("department_ids", [])
    )


async def get_accessible(domain: str, record_id: str, user: dict[str, Any]) -> dict[str, Any]:
    record = await repository.get(domain, record_id)
    if not accessible(record, user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found.")
    return record


@app.get("/api/v1/health")
async def health(request: Request):
    return envelope(
        {
            "status": "healthy",
            "service": "bcaz-boh-iq-api",
            "demo_login_available": settings.seed_demo_data and settings.environment != "production"
        },
        request
    )


@app.get("/api/v1/readiness")
async def readiness(request: Request):
    try:
        await repository.list("organizations", limit=1)
        connected = True
    except Exception:
        connected = False
    return envelope({"status": "ready" if connected else "not_ready", "database_connected": connected}, request)


@app.post("/api/v1/auth/login")
async def login(payload: LoginRequest, request: Request):
    user = await repository.find_one("users", {"email": payload.email.strip().lower()})
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email or password is incorrect.")
    token = create_access_token(user["id"], user["organization_id"])
    return envelope({"access_token": token, "token_type": "bearer", "user": public_session(user)}, request)


@app.post("/api/v1/auth/demo")
async def demo_login(request: Request):
    if not settings.seed_demo_data or settings.environment == "production":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found.")
    user = await repository.find_one("users", {"email": settings.bootstrap_admin_email})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Demo user is not available.")
    token = create_access_token(user["id"], user["organization_id"])
    return envelope({"access_token": token, "token_type": "bearer", "user": public_session(user)}, request)


@app.get("/api/v1/auth/me")
async def me(request: Request, user: Annotated[dict, Depends(current_session)]):
    return envelope(public_session(user), request)


@app.get("/api/v1/command-board")
async def command_board(request: Request, user: Annotated[dict, Depends(current_session)]):
    cards, _ = await repository.list("command-cards", tenant_filters(user), limit=100, sort="rank")
    return envelope(cards, request, total=len(cards))


@app.post("/api/v1/command-board/{card_id}/{action}")
async def command_action(
    card_id: str,
    action: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    if action not in {"investigate", "assign", "resolve"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported command-card action.")
    require_permission(user, "resolve" if action == "resolve" else "update")
    card = await get_accessible("command-cards", card_id, user)
    history = [*card.get("history", []), {"at": now_iso(), "event": action, "actor_id": user["id"]}]
    patch = {"history": history, "status": "resolved" if action == "resolve" else action, "updated_by": user["id"]}
    updated = await repository.update("command-cards", card_id, patch, card.get("version"))
    return envelope(updated, request)


@app.get("/api/v1/procure-to-pay/{order_id}/timeline")
async def procure_timeline(
    order_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    order = await get_accessible("orders", order_id, user)
    receipt = await repository.find_one("receiving", {"organization_id": user["organization_id"], "order_id": order_id})
    invoice = await repository.find_one("invoices", {"organization_id": user["organization_id"], "purchase_order_id": order_id})
    timeline = [
        {"step": "Purchase order", "status": order.get("status", "created"), "record": {"domain": "orders", "id": order_id}},
        {"step": "Receiving", "status": receipt.get("status", "pending") if receipt else "pending", "record": {"domain": "receiving", "id": receipt["id"]} if receipt else None},
        {"step": "Invoice match", "status": invoice.get("status", "pending") if invoice else "pending", "record": {"domain": "invoices", "id": invoice["id"]} if invoice else None},
    ]
    return envelope({"order": order, "timeline": timeline}, request)


@app.post("/api/v1/orders/{order_id}/approve")
async def approve_order(
    order_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    require_permission(user, "approve")
    order = await get_accessible("orders", order_id, user)
    updated = await repository.update(
        "orders",
        order_id,
        {"approval_status": "approved", "approved_by": user["id"], "updated_by": user["id"]},
        order.get("version"),
    )
    return envelope(updated, request)


@app.post("/api/v1/receiving/sessions/{session_id}/complete")
async def complete_receiving(
    session_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    require_permission(user, "update")
    receipt = await get_accessible("receiving", session_id, user)
    existing = await repository.find_one(
        "inventory",
        {
            "organization_id": user["organization_id"],
            "source_record_type": "receipt",
            "source_record_id": session_id,
        },
    )
    if existing:
        return envelope(existing, request, idempotent_replay=True)
    line = (receipt.get("lines") or [{}])[0]
    quantity = Decimal(str(line.get("delivered_base_quantity", "0")))
    unit_cost = int(line.get("unit_cost_minor", 0))
    transaction = await repository.create(
        "inventory",
        {
            "organization_id": user["organization_id"],
            "location_id": receipt.get("location_id"),
            "department_id": receipt.get("department_id"),
            "transaction_type": "purchase_receipt",
            "item_id": line.get("item_id"),
            "quantity": {"amount": str(quantity), "unit": "base"},
            "unit_cost": {"currency": "USD", "amount_minor": unit_cost},
            "extended_cost": {"currency": "USD", "amount_minor": calculations.extended_cost(quantity, unit_cost)},
            "source_record_type": "receipt",
            "source_record_id": session_id,
            "created_by": user["id"],
        },
    )
    await repository.update("receiving", session_id, {"status": "completed", "updated_by": user["id"]}, receipt.get("version"))
    return envelope(transaction, request)


@app.post("/api/v1/invoices/{invoice_id}/match")
async def match_invoice(
    invoice_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    invoice = await get_accessible("invoices", invoice_id, user)
    duplicate = await repository.find_one(
        "invoices",
        {
            "organization_id": user["organization_id"],
            "vendor_id": invoice.get("vendor_id"),
            "invoice_number": invoice.get("invoice_number"),
        },
    )
    duplicate_risk = "duplicate_candidate" if duplicate and duplicate.get("id") != invoice_id else "clear"
    order = await get_accessible("orders", invoice.get("purchase_order_id", ""), user)
    receipt = await get_accessible("receiving", invoice.get("receipt_id", ""), user)
    match = calculations.three_way_match(
        order.get("lines", []),
        receipt.get("lines", []),
        invoice.get("lines", []),
        Decimal("0.5"),
        5,
        100,
    )
    updated = await repository.update(
        "invoices",
        invoice_id,
        {"match": match, "status": match["status"], "duplicate_risk": duplicate_risk, "updated_by": user["id"]},
        invoice.get("version"),
    )
    return envelope(updated, request)


@app.get("/api/v1/recipes/{recipe_id}/cost")
async def recipe_cost(
    recipe_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    recipe = await get_accessible("recipes", recipe_id, user)
    economics = calculations.recipe_economics(
        int(recipe.get("selling_price_minor", 0)),
        int(recipe.get("ingredient_cost_minor", 0)),
        int(recipe.get("labor_cost_minor", 0)),
        int(recipe.get("packaging_cost_minor", 0)),
    )
    return envelope({**recipe, "economics": economics}, request)


@app.post("/api/v1/menus/simulations")
async def menu_simulation(
    payload: CreateRecordRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    require_permission(user, "create")
    if payload.organization_id != user["organization_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant writes are prohibited.")
    selling_price = int(payload.data.get("selling_price_minor", 0))
    plate_cost = int(payload.data.get("plate_cost_minor", 0))
    economics = calculations.recipe_economics(selling_price, plate_cost)
    return envelope(
        {
            "id": f"menu_simulation_{uuid.uuid4().hex[:12]}",
            "organization_id": user["organization_id"],
            "location_id": payload.location_id,
            "status": "requires_approval_before_publish",
            "economics": economics,
        },
        request,
    )


@app.post("/api/v1/imports/preview")
async def import_preview(
    payload: ImportPreviewRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    require_permission(user, "create")
    valid_rows = [row for row in payload.rows if row.get("name")]
    return envelope(
        {
            "import_type": payload.import_type,
            "total_rows": len(payload.rows),
            "valid_rows": len(valid_rows),
            "error_rows": len(payload.rows) - len(valid_rows),
            "errors": [
                {"row": index + 1, "message": "name is required"}
                for index, row in enumerate(payload.rows)
                if not row.get("name")
            ],
        },
        request,
    )


@app.get("/api/v1/global-iq/agents")
async def global_iq_agents(
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    return envelope(
        [{"name": agent.name, "description": agent.description} for agent in AGENTS],
        request,
    )


@app.post("/api/v1/global-iq/query")
async def global_iq(
    payload: GlobalIQRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    live_answer = await answer_question(payload.question, repository, tenant_filters(user))
    if live_answer:
        return envelope(
            {
                "answer": live_answer.answer,
                "confidence": live_answer.confidence,
                "citations": live_answer.citations,
                "evidence_complete": live_answer.evidence_complete,
                "agent": live_answer.agent,
            },
            request,
        )

    answers, _ = await repository.list("global-iq", tenant_filters(user), limit=20)
    selected = next(
        (item for item in answers if item.get("question", "").lower() == payload.question.lower()),
        answers[0] if answers else None,
    )
    if not selected:
        return envelope(
            {
                "answer": "There is not enough verified operating evidence to answer that question yet.",
                "confidence": "0.00",
                "citations": [],
                "evidence_complete": False,
                "agent": None,
            },
            request,
        )
    return envelope(
        {
            "answer": selected["answer"],
            "confidence": selected.get("confidence", "0.00"),
            "citations": selected.get("citations", []),
            "evidence_complete": selected.get("evidence_complete", False),
            "agent": "archive-lookup",
        },
        request,
    )


@app.post("/api/v1/sync/queue")
async def sync_queue(
    payload: SyncQueueRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    existing = await repository.find_one(
        "sync-jobs",
        {"organization_id": user["organization_id"], "idempotency_key": payload.idempotency_key},
    )
    if existing:
        return envelope(existing, request, idempotent_replay=True)
    job = await repository.create(
        "sync-jobs",
        {
            "organization_id": user["organization_id"],
            "operation_type": payload.operation_type,
            "payload": payload.payload,
            "idempotency_key": payload.idempotency_key,
            "client_created_at": payload.client_created_at,
            "status": "queued",
            "created_by": user["id"],
        },
    )
    return envelope(job, request)


@app.get("/api/v1/{domain}")
async def list_records(
    domain: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
    limit: Annotated[int, Query(ge=1, le=250)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: str | None = None,
):
    if domain not in DOMAIN_COLLECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    require_permission(user, "read")
    records, total = await repository.list(domain, tenant_filters(user), limit, offset, sort)
    for record in records:
        record.pop("password_hash", None)
    return envelope(records, request, total=total, limit=limit, offset=offset)


@app.get("/api/v1/{domain}/{record_id}")
async def get_record(
    domain: str,
    record_id: str,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    if domain not in DOMAIN_COLLECTIONS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain not found.")
    record = await get_accessible(domain, record_id, user)
    record.pop("password_hash", None)
    return envelope(record, request)


@app.post("/api/v1/{domain}")
async def create_record(
    domain: str,
    payload: CreateRecordRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
    idempotency_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if domain not in DOMAIN_COLLECTIONS or domain in {"users", "audit-logs"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain is not writable.")
    require_permission(user, "create")
    if payload.organization_id != user["organization_id"]:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cross-tenant writes are prohibited.")
    key = idempotency_header or payload.idempotency_key
    if key:
        existing = await repository.find_one(
            domain,
            {"organization_id": user["organization_id"], "idempotency_key": key},
        )
        if existing:
            return envelope(existing, request, idempotent_replay=True)
    record = {
        "organization_id": user["organization_id"],
        "location_id": payload.location_id,
        "department_id": payload.department_id,
        "idempotency_key": key,
        "created_by": user["id"],
        **payload.data,
    }
    created = await repository.create(domain, record)
    return envelope(created, request)


@app.patch("/api/v1/{domain}/{record_id}")
async def patch_record(
    domain: str,
    record_id: str,
    payload: PatchRecordRequest,
    request: Request,
    user: Annotated[dict, Depends(current_session)],
):
    if domain not in DOMAIN_COLLECTIONS or domain in {"users", "audit-logs"}:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Domain is not writable.")
    require_permission(user, "update")
    await get_accessible(domain, record_id, user)
    try:
        updated = await repository.update(
            domain,
            record_id,
            {**payload.data, "updated_by": user["id"]},
            payload.expected_version,
        )
    except ValueError as exc:
        if str(exc) == "version_conflict":
            raise HTTPException(status.HTTP_409_CONFLICT, "The record changed; refresh before retrying.") from exc
        raise
    return envelope(updated, request)

