from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from . import calculations
from .store import Repository


@dataclass
class AgentAnswer:
    agent: str
    answer: str
    confidence: str
    citations: list[dict[str, str]]
    evidence_complete: bool


class DomainAgent:
    name: str = "domain-agent"
    description: str = ""
    keywords: tuple[str, ...] = ()

    def relevance(self, question: str) -> int:
        lowered = question.lower()
        return sum(1 for keyword in self.keywords if keyword in lowered)

    async def investigate(self, repository: Repository, filters: dict[str, Any]) -> AgentAnswer | None:
        raise NotImplementedError


class ReceivingExceptionAgent(DomainAgent):
    name = "receiving-agent"
    description = "Traces dock receiving shortages and overages against purchase orders."
    keywords = ("receiv", "shortage", "delivery", "dock", "food cost")

    async def investigate(self, repository: Repository, filters: dict[str, Any]) -> AgentAnswer | None:
        records, _ = await repository.list("receiving", filters, limit=50)
        exceptions = [record for record in records if record.get("status") == "open_exception"]
        if not exceptions:
            return None
        record = exceptions[0]
        order = await repository.get("orders", record["order_id"]) if record.get("order_id") else None
        ordered_by_item = {
            line["item_id"]: Decimal(str(line.get("ordered_base_quantity", "0")))
            for line in (order.get("lines", []) if order else [])
        }
        shortfalls = []
        for line in record.get("lines", []):
            delivered = Decimal(str(line.get("delivered_base_quantity", "0")))
            ordered = ordered_by_item.get(line["item_id"], Decimal("0"))
            if delivered < ordered:
                shortfalls.append((line["item_id"], ordered - delivered))
        if not shortfalls:
            return None
        item_id, shortfall = shortfalls[0]
        item_name = item_id.replace("item_", "").replace("_", " ")
        citations = [{"domain": "receiving", "id": record["id"]}]
        if order:
            citations.append({"domain": "orders", "id": order["id"]})
        return AgentAnswer(
            agent=self.name,
            answer=(
                f"Dock receiving has an open shortage exception on {item_name}: "
                f"{shortfall} short of the purchase order quantity."
            ),
            confidence="0.80",
            citations=citations,
            evidence_complete=True,
        )


class InvoiceMatchAgent(DomainAgent):
    name = "invoice-agent"
    description = "Runs three-way match between purchase orders, receiving, and invoices."
    keywords = ("invoice", "bill", "match", "food cost", "vendor", "price")

    async def investigate(self, repository: Repository, filters: dict[str, Any]) -> AgentAnswer | None:
        invoices, _ = await repository.list("invoices", filters, limit=50)
        exceptions = [invoice for invoice in invoices if invoice.get("status") == "match_exception"]
        if not exceptions:
            return None
        invoice = exceptions[0]
        order = await repository.get("orders", invoice["purchase_order_id"]) if invoice.get("purchase_order_id") else None
        receipt = await repository.get("receiving", invoice["receipt_id"]) if invoice.get("receipt_id") else None
        exception_types: list[str] = []
        if order and receipt:
            result = calculations.three_way_match(
                order.get("lines", []),
                receipt.get("lines", []),
                invoice.get("lines", []),
                quantity_tolerance=Decimal("0"),
                price_tolerance_minor=0,
                total_tolerance_minor=0,
            )
            exception_types = sorted({exception["type"] for exception in result["exceptions"]})
        citations = [{"domain": "invoices", "id": invoice["id"]}]
        if receipt:
            citations.append({"domain": "receiving", "id": receipt["id"]})
        if order:
            citations.append({"domain": "orders", "id": order["id"]})
        detail = f" Exceptions found: {', '.join(exception_types)}." if exception_types else ""
        return AgentAnswer(
            agent=self.name,
            answer=(
                f"Invoice {invoice.get('invoice_number', invoice['id'])} is blocked by a three-way "
                f"match exception against the purchase order and dock receipt.{detail}"
            ),
            confidence="0.85",
            citations=citations,
            evidence_complete=True,
        )


class InventoryVarianceAgent(DomainAgent):
    name = "inventory-agent"
    description = "Compares actual to theoretical usage and surfaces probable causes for variance."
    keywords = ("variance", "inventory", "usage", "waste", "food cost", "theoretical")

    async def investigate(self, repository: Repository, filters: dict[str, Any]) -> AgentAnswer | None:
        records, _ = await repository.list("analytics", filters, limit=50)
        variant = next((record for record in records if record.get("cost_variance_minor")), None)
        if not variant:
            return None
        actual = Decimal(str(variant.get("actual_quantity", "0")))
        theoretical = Decimal(str(variant.get("theoretical_quantity", "0")))
        cost_variance = Decimal(str(variant.get("cost_variance_minor", 0))) / Decimal(100)
        causes = variant.get("probable_causes", [])
        cause_text = f" Probable causes: {', '.join(causes)}." if causes else ""
        return AgentAnswer(
            agent=self.name,
            answer=(
                f"Actual usage ran {actual - theoretical} above theoretical usage, "
                f"a cost impact of ${cost_variance:.2f}.{cause_text}"
            ),
            confidence="0.82",
            citations=[{"domain": "analytics", "id": variant["id"]}],
            evidence_complete=True,
        )


class RecipeEconomicsAgent(DomainAgent):
    name = "recipe-agent"
    description = "Flags the recipe with the weakest food cost percent among tenant menu items."
    keywords = ("recipe", "plate cost", "menu", "margin", "food cost percent", "gross profit")

    async def investigate(self, repository: Repository, filters: dict[str, Any]) -> AgentAnswer | None:
        recipes, _ = await repository.list("recipes", filters, limit=50)
        priced = [recipe for recipe in recipes if recipe.get("selling_price_minor")]
        if not priced:
            return None

        def food_cost_percent(recipe: dict[str, Any]) -> Decimal:
            economics = calculations.recipe_economics(
                recipe.get("selling_price_minor", 0),
                recipe.get("ingredient_cost_minor", 0),
                recipe.get("labor_cost_minor", 0),
                recipe.get("packaging_cost_minor", 0),
            )
            return Decimal(economics["food_cost_percent"])

        weakest = max(priced, key=food_cost_percent)
        economics = calculations.recipe_economics(
            weakest.get("selling_price_minor", 0),
            weakest.get("ingredient_cost_minor", 0),
            weakest.get("labor_cost_minor", 0),
            weakest.get("packaging_cost_minor", 0),
        )
        return AgentAnswer(
            agent=self.name,
            answer=(
                f"{weakest.get('name', weakest['id'])} carries a {economics['food_cost_percent']}% food cost, "
                f"the highest of the priced menu items reviewed."
            ),
            confidence="0.75",
            citations=[{"domain": "recipes", "id": weakest["id"]}],
            evidence_complete=True,
        )


AGENTS: tuple[DomainAgent, ...] = (
    ReceivingExceptionAgent(),
    InvoiceMatchAgent(),
    InventoryVarianceAgent(),
    RecipeEconomicsAgent(),
)


def ranked_agents(question: str) -> list[DomainAgent]:
    scored = [(agent.relevance(question), agent) for agent in AGENTS]
    relevant = [(score, agent) for score, agent in scored if score > 0]
    relevant.sort(key=lambda pair: pair[0], reverse=True)
    return [agent for _, agent in relevant]


async def answer_question(
    question: str, repository: Repository, filters: dict[str, Any]
) -> AgentAnswer | None:
    for agent in ranked_agents(question):
        result = await agent.investigate(repository, filters)
        if result:
            return result
    return None
