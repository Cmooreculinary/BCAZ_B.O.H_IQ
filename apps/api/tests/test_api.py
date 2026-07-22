import os
import sys
from decimal import Decimal
from pathlib import Path

os.environ["APP_STORAGE"] = "memory"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"
os.environ["DEMO_PASSWORD"] = "demo-password"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app import calculations
from app.config import settings
from app.main import app


def login(client: TestClient, email: str = "owner@bcaz.example") -> str:
    response = client.post("/api/v1/auth/login", json={"email": email,"password": "demo-password"})
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_readiness_and_cors_allowlist():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["data"]["status"] == "healthy"
        readiness = client.get("/api/v1/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["data"]["database_connected"] is True
        assert "*" not in settings.cors_origins


def test_login_and_role_based_navigation_data():
    with TestClient(app) as client:
        token = login(client)
        response = client.get("/api/v1/auth/me", headers=auth_header(token))
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["organization_id"] == "org_blue_collar_demo"
        assert "organization_owner" in data["roles"]


def test_tenant_isolation_blocks_cross_tenant_records():
    with TestClient(app) as client:
        other_token = login(client, "owner@other.example")
        response = client.get("/api/v1/orders/po_10042", headers=auth_header(other_token))
        assert response.status_code == 404


def test_permissions_receiver_cannot_approve_order():
    with TestClient(app) as client:
        receiver_token = login(client, "dock@bcaz.example")
        response = client.post("/api/v1/orders/po_10042/approve", headers=auth_header(receiver_token))
        assert response.status_code == 403


def test_money_precision_and_unit_conversion():
    assert calculations.cents(Decimal("12.345")) == 1235
    assert calculations.convert_quantity(Decimal("2.5"), Decimal("40")) == Decimal("100.0000")
    assert calculations.extended_cost(Decimal("3.25"), 248) == 806


def test_order_calculations_and_three_way_match_exception():
    po_lines = [{"item_id": "item_chicken_thigh", "ordered_base_quantity": "120", "unit_cost_minor": 248, "extended_cost_minor": 29760}]
    receipts = [{"item_id": "item_chicken_thigh", "delivered_base_quantity": "110"}]
    invoices = [{"item_id": "item_chicken_thigh", "quantity": "120", "unit_price_minor": 260, "total_minor": 31200}]
    result = calculations.three_way_match(po_lines, receipts, invoices, Decimal("0.5"), 5, 100)
    assert result["status"] == "exception"
    assert {item["type"] for item in result["exceptions"]} == {"quantity_receipt", "quantity_invoice", "price", "total"}


def test_duplicate_invoice_detection_and_match_endpoint():
    with TestClient(app) as client:
        token = login(client)
        create = client.post(
            "/api/v1/invoices",
            headers={**auth_header(token), "Idempotency-Key": "dup_invoice_test"},
            json={
                "organization_id": "org_blue_collar_demo",
                "location_id": "loc_phoenix",
                "department_id": "dept_food",
                "idempotency_key": "dup_invoice_test",
                "data": {
                    "vendor_id": "vendor_desert_farm_collective",
                    "invoice_number": "DF-7781",
                    "invoice_date": "2026-07-16",
                    "due_date": "2026-07-30",
                    "purchase_order_id": "po_10042",
                    "receipt_id": "rcv_10042_partial",
                    "lines": [{"id": "dup_1", "item_id": "item_chicken_thigh", "description": "Chicken", "quantity": "120", "unit_price_minor": 260, "total_minor": 31200}],
                    "subtotal": {"currency": "USD", "amount_minor": 31200},
                    "taxes": {"currency": "USD", "amount_minor": 0},
                    "fees": {"currency": "USD", "amount_minor": 0},
                    "discounts": {"currency": "USD", "amount_minor": 0},
                    "total": {"currency": "USD", "amount_minor": 31200},
                },
            },
        )
        assert create.status_code == 200, create.text
        invoice_id = create.json()["data"]["id"]
        matched = client.post(f"/api/v1/invoices/{invoice_id}/match", headers=auth_header(token))
        assert matched.status_code == 200, matched.text
        assert matched.json()["data"]["duplicate_risk"] == "duplicate_candidate"


def test_inventory_ledger_and_receiving_completion_idempotency():
    with TestClient(app) as client:
        token = login(client)
        before = client.get("/api/v1/inventory", headers=auth_header(token)).json()["meta"]["total"]
        response = client.post("/api/v1/receiving/sessions/rcv_10042_partial/complete", headers=auth_header(token))
        assert response.status_code == 200, response.text
        after = client.get("/api/v1/inventory", headers=auth_header(token)).json()["meta"]["total"]
        assert after == before + 1


def test_actual_consumption_theoretical_depletion_and_variance():
    assert calculations.actual_inventory_consumption(1000, 250, 50, 0,25, 700, 10) == 565
    theoretical = calculations.theoretical_usage(Decimal("84"), Decimal("0.2"))
    assert theoretical == Decimal("16.8000")
    result = calculations.variance(Decimal("18"), theoretical, 4464, 4166)
    assert result["status"] == "unfavorable"
    assert result["cost_variance_minor"] == 298


def test_recipe_costing_and_menu_margin_simulation():
    with TestClient(app) as client:
        token = login(client)
        cost = client.get("/api/v1/recipes/recipe_adobo_chicken_taco/cost", headers=auth_header(token))
        assert cost.status_code == 200, cost.text
        assert cost.json()["data"]["economics"]["gross_profit_minor"] > 0
        assert "does not guarantee allergen safety" in cost.json()["data"]["allergen_disclaimer"]
        simulation = client.post(
            "/api/v1/menus/simulations",
            headers=auth_header(token),
            json={"organization_id": "org_blue_collar_demo", "location_id": "loc_phoenix", "data": {"selling_price_minor": 975, "plate_cost_minor": 246}},
        )
        assert simulation.status_code == 200, simulation.text
        assert simulation.json()["data"]["status"] == "requires_approval_before_publish"


def test_forecast_recommendation_boundaries():
    result = calculations.order_recommendation(Decimal("148"), Decimal("152"), Decimal("0"), Decimal("25"), Decimal("40"), Decimal("40"))
    assert result["recommended_quantity"] == "40.00"
    zero = calculations.order_recommendation(Decimal("20"), Decimal("100"), Decimal("0"), Decimal("10"), Decimal("40"), Decimal("40"))
    assert zero["recommended_quantity"] == "0.00"


def test_generic_idempotency_and_optimistic_concurrency():
    with TestClient(app) as client:
        token = login(client)
        payload = {
            "organization_id": "org_blue_collar_demo",
            "location_id": "loc_phoenix",
            "department_id": "dept_food",
            "idempotency_key": "idem_order_test_1",
            "data": {"vendor_id": "vendor_desert_farm_collective", "total": {"currency": "USD", "amount_minor": 1000}},
        }
        first = client.post("/api/v1/orders", headers={**auth_header(token), "Idempotency-Key": "idem_order_test_1"}, json=payload)
        second = client.post("/api/v1/orders", headers={**auth_header(token), "Idempotency-Key": "idem_order_test_1"}, json=payload)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["data"]["id"] == second.json()["data"]["id"]
        record_id = first.json()["data"]["id"]
        conflict = client.patch(
            f"/api/v1/orders/{record_id}",
            headers=auth_header(token),
            json={"expected_version": 99, "data": {"approval_status": "approved"}},
        )
        assert conflict.status_code == 409


def test_import_validation_audit_logging_and_global_iq_evidence_links():
    with TestClient(app) as client:
        token = login(client)
        preview = client.post(
            "/api/v1/imports/preview",
            headers=auth_header(token),
            json={"idempotency_key": "imp_test", "import_type": "items", "rows": [{"name": "Sea salt"}, {"category": "missing name"}]},
        )
        assert preview.status_code == 200
        assert preview.json()["data"]["error_rows"] == 1
        task = client.post(
            "/api/v1/tasks",
            headers=auth_header(token),
            json={"organization_id": "org_blue_collar_demo", "location_id": "loc_phoenix", "data": {"title": "Verify invoice photo"}},
        )
        assert task.status_code == 200
        audit_logs = client.get("/api/v1/audit-logs", headers=auth_header(token))
        assert audit_logs.status_code == 200
        assert any(log["domain"] == "tasks" for log in audit_logs.json()["data"])
        answer = client.post("/api/v1/global-iq/query", headers=auth_header(token), json={"question": "Why did food cost rise this week?"})
        assert answer.status_code == 200
        assert answer.json()["data"]["citations"][0]["domain"] in {"invoices", "receiving", "analytics"}


def test_global_iq_agents_endpoint_lists_the_ecosystem():
    with TestClient(app) as client:
        token = login(client)
        agents = client.get("/api/v1/global-iq/agents", headers=auth_header(token))
        assert agents.status_code == 200
        agent_names = {agent["name"] for agent in agents.json()["data"]}
        assert agent_names == {"receiving-agent", "invoice-agent", "inventory-agent", "recipe-agent"}


def test_global_iq_query_response_identifies_which_agent_answered():
    with TestClient(app) as client:
        token = login(client)
        answer = client.post(
            "/api/v1/global-iq/query",
            headers=auth_header(token),
            json={"question": "Why did food cost rise this week?"},
        )
        assert answer.status_code == 200
        data = answer.json()["data"]
        assert data["agent"] in {"receiving-agent", "invoice-agent", "inventory-agent", "archive-lookup"}


def test_global_iq_falls_back_when_no_agent_has_evidence():
    with TestClient(app) as client:
        token = login(client, "owner@other.example")
        answer = client.post(
            "/api/v1/global-iq/query",
            headers=auth_header(token),
            json={"question": "What is our current staff schedule?"},
        )
        assert answer.status_code == 200
        data = answer.json()["data"]
        assert data["agent"] is None
        assert data["evidence_complete"] is False
        assert data["citations"] == []
