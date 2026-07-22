import os
import sys
from pathlib import Path

os.environ.setdefault("APP_STORAGE", "memory")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
os.environ.setdefault("DEMO_PASSWORD", "demo-password")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.agents import (
    AGENTS,
    InventoryVarianceAgent,
    InvoiceMatchAgent,
    ReceivingExceptionAgent,
    RecipeEconomicsAgent,
    answer_question,
    ranked_agents,
)
from app.store import MemoryRepository

ORG = "org_test_tenant"
FILTERS = {"organization_id": ORG}


async def repository_with(**collections) -> MemoryRepository:
    repo = MemoryRepository(initial={key: list(value) for key, value in collections.items()})
    await repo.initialize()
    return repo


def record(collection_id: str, **fields) -> dict:
    return {"id": collection_id, "organization_id": ORG, **fields}


def test_ranked_agents_orders_by_keyword_relevance():
    ranked = ranked_agents("What caused the dock shortage on the chicken delivery?")
    assert [agent.name for agent in ranked] == ["receiving-agent"]

    ranked = ranked_agents("What is our current staff schedule?")
    assert ranked == []


@pytest.mark.asyncio
async def test_receiving_agent_reports_shortfall_against_the_purchase_order():
    repo = await repository_with(
        orders=[
            record(
                "po_test",
                lines=[{"item_id": "item_chicken_thigh", "ordered_base_quantity": "120"}],
            )
        ],
        receiving=[
            record(
                "rcv_test",
                order_id="po_test",
                status="open_exception",
                lines=[{"item_id": "item_chicken_thigh", "delivered_base_quantity": "110"}],
            )
        ],
    )
    result = await ReceivingExceptionAgent().investigate(repo, FILTERS)
    assert result is not None
    assert result.agent == "receiving-agent"
    assert result.citations[0] == {"domain": "receiving", "id": "rcv_test"}
    assert "10" in result.answer


@pytest.mark.asyncio
async def test_receiving_agent_returns_none_without_an_open_exception():
    repo = await repository_with(
        orders=[record("po_test", lines=[])],
        receiving=[record("rcv_test", order_id="po_test", status="completed", lines=[])],
    )
    result = await ReceivingExceptionAgent().investigate(repo, FILTERS)
    assert result is None


@pytest.mark.asyncio
async def test_invoice_agent_surfaces_three_way_match_exceptions():
    repo = await repository_with(
        orders=[
            record(
                "po_test",
                lines=[
                    {
                        "item_id": "item_chicken_thigh",
                        "ordered_base_quantity": "120",
                        "unit_cost_minor": 248,
                        "extended_cost_minor": 29760,
                    }
                ],
            )
        ],
        receiving=[
            record(
                "rcv_test",
                lines=[{"item_id": "item_chicken_thigh", "delivered_base_quantity": "110"}],
            )
        ],
        invoices=[
            record(
                "inv_test",
                invoice_number="DF-9001",
                purchase_order_id="po_test",
                receipt_id="rcv_test",
                status="match_exception",
                lines=[
                    {
                        "item_id": "item_chicken_thigh",
                        "quantity": "120",
                        "unit_price_minor": 260,
                        "total_minor": 31200,
                    }
                ],
            )
        ],
    )
    result = await InvoiceMatchAgent().investigate(repo, FILTERS)
    assert result is not None
    assert result.agent == "invoice-agent"
    assert result.citations[0] == {"domain": "invoices", "id": "inv_test"}
    for exception_type in ("price", "quantity_invoice", "quantity_receipt", "total"):
        assert exception_type in result.answer


@pytest.mark.asyncio
async def test_inventory_agent_reports_variance_and_probable_causes():
    repo = await repository_with(
        analytics=[
            record(
                "avt_test",
                actual_quantity="138",
                theoretical_quantity="126.4",
                cost_variance_minor=2877,
                probable_causes=["short delivery not fully credited", "prep waste above plan"],
            )
        ]
    )
    result = await InventoryVarianceAgent().investigate(repo, FILTERS)
    assert result is not None
    assert result.agent == "inventory-agent"
    assert result.citations == [{"domain": "analytics", "id": "avt_test"}]
    assert "prep waste above plan" in result.answer
    assert "28.77" in result.answer


@pytest.mark.asyncio
async def test_recipe_agent_flags_the_weakest_food_cost_percent():
    repo = await repository_with(
        recipes=[
            record(
                "recipe_healthy",
                name="Grain Bowl",
                selling_price_minor=900,
                ingredient_cost_minor=180,
                labor_cost_minor=20,
                packaging_cost_minor=10,
            ),
            record(
                "recipe_weak",
                name="Loaded Nachos",
                selling_price_minor=900,
                ingredient_cost_minor=520,
                labor_cost_minor=40,
                packaging_cost_minor=20,
            ),
        ]
    )
    result = await RecipeEconomicsAgent().investigate(repo, FILTERS)
    assert result is not None
    assert result.agent == "recipe-agent"
    assert result.citations == [{"domain": "recipes", "id": "recipe_weak"}]
    assert "Loaded Nachos" in result.answer


@pytest.mark.asyncio
async def test_answer_question_falls_back_to_none_when_no_agent_has_evidence():
    repo = await repository_with()
    result = await answer_question("What is our current staff schedule?", repo, FILTERS)
    assert result is None


@pytest.mark.asyncio
async def test_answer_question_skips_agents_without_evidence_and_tries_the_next_ranked_agent():
    question = "What happened with the dock delivery shortage on this invoice?"
    assert [agent.name for agent in ranked_agents(question)] == ["receiving-agent", "invoice-agent"]

    repo = await repository_with(
        receiving=[record("rcv_test", status="completed", lines=[])],
        invoices=[
            record(
                "inv_test",
                invoice_number="DF-9002",
                status="match_exception",
                lines=[{"item_id": "item_chicken_thigh", "quantity": "10", "unit_price_minor": 100, "total_minor": 1000}],
            )
        ],
    )
    result = await answer_question(question, repo, FILTERS)
    assert result is not None
    assert result.agent == "invoice-agent"


def test_agent_registry_has_a_description_for_every_agent():
    assert len(AGENTS) == 4
    for agent in AGENTS:
        assert agent.name
        assert agent.description
        assert agent.keywords
