from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


FOUR_PLACES = Decimal("0.0001")


def cents(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def convert_quantity(quantity: Decimal, conversion_factor: Decimal) -> Decimal:
    return (quantity * conversion_factor).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def extended_cost(quantity: Decimal, unit_cost_minor: int) -> int:
    return int((quantity * unit_cost_minor).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def actual_inventory_consumption(
    beginning_inventory: int,
    purchases: int,
    transfers_in: int,
    production_in: int,
    transfers_out: int,
    ending_inventory: int,
    approved_adjustments: int,
) -> int:
    return (
        beginning_inventory
        + purchases
        + transfers_in
        + production_in
        - transfers_out
        - ending_inventory
        - approved_adjustments
    )


def theoretical_usage(sales_quantity: Decimal, recipe_quantity: Decimal) -> Decimal:
    return (sales_quantity * recipe_quantity).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)


def variance(
    actual_quantity: Decimal,
    theoretical_quantity: Decimal,
    actual_cost_minor: int,
    theoretical_cost_minor: int,
) -> dict[str, Any]:
    quantity_variance = (actual_quantity - theoretical_quantity).quantize(FOUR_PLACES)
    cost_variance = actual_cost_minor - theoretical_cost_minor
    return {
        "quantity_variance": str(quantity_variance),
        "cost_variance_minor": cost_variance,
        "status": "unfavorable" if quantity_variance > 0 or cost_variance > 0 else "favorable",
    }


def order_recommendation(
    forecast_demand: Decimal,
    usable_inventory: Decimal,
    already_on_order: Decimal,
    safety_stock: Decimal,
    order_multiple: Decimal,
    minimum_order: Decimal,
) -> dict[str, str]:
    raw = forecast_demand + safety_stock - usable_inventory - already_on_order
    if raw <= 0:
        recommended = Decimal("0")
    else:
        multiples = (raw / order_multiple).to_integral_value(rounding="ROUND_CEILING")
        recommended = max(multiples * order_multiple, minimum_order)
    return {
        "raw_requirement": str(raw.quantize(Decimal("0.01"))),
        "recommended_quantity": str(recommended.quantize(Decimal("0.01"))),
    }


def three_way_match(
    order_lines: list[dict[str, Any]],
    receipt_lines: list[dict[str, Any]],
    invoice_lines: list[dict[str, Any]],
    quantity_tolerance: Decimal,
    price_tolerance_minor: int,
    total_tolerance_minor: int,
) -> dict[str, Any]:
    receipts = {line["item_id"]: line for line in receipt_lines}
    invoices = {line["item_id"]: line for line in invoice_lines}
    exceptions: list[dict[str, Any]] = []

    for order in order_lines:
        item_id = order["item_id"]
        ordered = Decimal(str(order.get("ordered_base_quantity", "0")))
        receipt = receipts.get(item_id, {})
        invoice = invoices.get(item_id, {})
        delivered = Decimal(str(receipt.get("delivered_base_quantity", "0")))
        invoiced = Decimal(str(invoice.get("quantity", "0")))
        order_price = int(order.get("unit_cost_minor", 0))
        invoice_price = int(invoice.get("unit_price_minor", 0))
        order_total = int(order.get("extended_cost_minor", 0))
        invoice_total = int(invoice.get("total_minor", 0))

        if abs(ordered - delivered) > quantity_tolerance:
            exceptions.append({"type": "quantity_receipt", "item_id": item_id})
        if abs(delivered - invoiced) > quantity_tolerance:
            exceptions.append({"type": "quantity_invoice", "item_id": item_id})
        if abs(order_price - invoice_price) > price_tolerance_minor:
            exceptions.append({"type": "price", "item_id": item_id})
        if abs(order_total - invoice_total) > total_tolerance_minor:
            exceptions.append({"type": "total", "item_id": item_id})

    return {"status": "exception" if exceptions else "matched", "exceptions": exceptions}


def recipe_economics(
    selling_price_minor: int,
    ingredient_cost_minor: int,
    labor_cost_minor: int = 0,
    packaging_cost_minor: int = 0,
) -> dict[str, Any]:
    plate_cost = ingredient_cost_minor + labor_cost_minor + packaging_cost_minor
    gross_profit = selling_price_minor - plate_cost
    food_cost_percent = (
        (Decimal(plate_cost) / Decimal(selling_price_minor) * Decimal(100)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if selling_price_minor
        else Decimal("0")
    )
    return {
        "plate_cost_minor": plate_cost,
        "gross_profit_minor": gross_profit,
        "food_cost_percent": str(food_cost_percent),
    }

