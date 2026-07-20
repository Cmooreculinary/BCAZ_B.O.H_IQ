from __future__ import annotations

from datetime import datetime, timezone

from .config import settings
from .security import hash_password


NOW = datetime.now(timezone.utc).isoformat()
ALLERGEN_DISCLAIMER = (
    "This information supports operational review and does not guarantee allergen "
    "safety. Verify current supplier labels, preparation methods, and cross-contact controls."
)


def _user(
    user_id: str,
    email: str,
    name: str,
    organization_id: str,
    roles: list[str],
    password: str,
    location_ids: list[str],
    department_ids: list[str],
) -> dict:
    return {
        "id": user_id,
        "email": email,
        "name": name,
        "organization_id": organization_id,
        "roles": roles,
        "location_ids": location_ids,
        "department_ids": department_ids,
        "password_hash": hash_password(password),
        "active": True,
        "created_at": NOW,
        "updated_at": NOW,
        "version": 1,
    }


def demo_dataset() -> dict[str, list[dict]]:
    primary_password = settings.bootstrap_admin_password or settings.demo_password
    common = {
        "organization_id": "org_blue_collar_demo",
        "created_at": NOW,
        "updated_at": NOW,
        "version": 1,
    }
    chicken = "item_chicken_thigh"
    tortillas = "item_corn_tortillas"
    vendor = "vendor_desert_farm_collective"
    order = "po_10042"
    receipt = "rcv_10042_partial"
    invoice = "inv_df_7781"
    recipe = "recipe_adobo_chicken_taco"

    users = [
        _user(
            "user_owner",
            settings.bootstrap_admin_email,
            "BCAz Demo Owner",
            "org_blue_collar_demo",
            ["organization_owner"],
            primary_password,
            ["loc_phoenix", "loc_commissary"],
            ["dept_food", "dept_ap"],
        )
    ]
    if settings.seed_demo_data and settings.environment != "production":
        users.extend(
            [
                _user(
                    "user_receiver",
                    "dock@bcaz.example",
                    "Dock Receiver",
                    "org_blue_collar_demo",
                    ["receiver"],
                    settings.demo_password,
                    ["loc_phoenix"],
                    ["dept_food"],
                ),
                _user(
                    "user_other_owner",
                    "owner@other.example",
                    "Other Tenant Owner",
                    "org_other_tenant",
                    ["organization_owner"],
                    settings.demo_password,
                    ["loc_other"],
                    ["dept_other"],
                ),
            ]
        )

    base: dict[str, list[dict]] = {
        "organizations": [
            {**common, "id": "org_blue_collar_demo", "name": "Blue Collar Demo Group"},
            {
                "id": "org_other_tenant",
                "organization_id": "org_other_tenant",
                "name": "Other Tenant",
                "created_at": NOW,
                "updated_at": NOW,
                "version": 1,
            },
        ],
        "locations": [
            {**common, "id": "loc_phoenix", "name": "Phoenix Kitchen", "timezone": "America/Phoenix"},
            {**common, "id": "loc_commissary", "name": "Central Commissary", "timezone": "America/Phoenix"},
        ],
        "departments": [
            {**common, "id": "dept_food", "name": "Food and Production"},
            {**common, "id": "dept_ap", "name": "Accounts Payable"},
        ],
        "users": users,
    }

    if not settings.seed_demo_data:
        return base

    base.update(
        {
            "vendors": [
                {**common, "id": vendor, "name": "Desert Farm Collective", "status": "approved"}
            ],
            "items": [
                {
                    **common,
                    "id": chicken,
                    "name": "Boneless chicken thigh",
                    "category": "Protein",
                    "base_unit": "lb",
                    "allergens": [],
                },
                {
                    **common,
                    "id": tortillas,
                    "name": "Corn tortillas",
                    "category": "Dry goods",
                    "base_unit": "each",
                    "allergens": [],
                },
            ],
            "orders": [
                {
                    **common,
                    "id": order,
                    "location_id": "loc_phoenix",
                    "department_id": "dept_food",
                    "vendor_id": vendor,
                    "status": "partially_received",
                    "approval_status": "approved",
                    "total": {"currency": "USD", "amount_minor": 29760},
                    "lines": [
                        {
                            "item_id": chicken,
                            "ordered_base_quantity": "120",
                            "unit_cost_minor": 248,
                            "extended_cost_minor": 29760,
                        }
                    ],
                }
            ],
            "receiving": [
                {
                    **common,
                    "id": receipt,
                    "location_id": "loc_phoenix",
                    "department_id": "dept_food",
                    "order_id": order,
                    "status": "open_exception",
                    "received_at": NOW,
                    "lines": [
                        {
                            "item_id": chicken,
                            "delivered_base_quantity": "110",
                            "unit_cost_minor": 248,
                        }
                    ],
                }
            ],
            "invoices": [
                {
                    **common,
                    "id": invoice,
                    "location_id": "loc_phoenix",
                    "department_id": "dept_ap",
                    "vendor_id": vendor,
                    "invoice_number": "DF-7781",
                    "invoice_date": "2026-07-16",
                    "purchase_order_id": order,
                    "receipt_id": receipt,
                    "status": "match_exception",
                    "lines": [
                        {
                            "id": "inv_line_chicken",
                            "item_id": chicken,
                            "description": "Boneless chicken thigh",
                            "quantity": "120",
                            "unit_price_minor": 260,
                            "total_minor": 31200,
                        }
                    ],
                    "total": {"currency": "USD", "amount_minor": 31200},
                }
            ],
            "credits": [
                {
                    **common,
                    "id": "credit_df_7781_short",
                    "location_id": "loc_phoenix",
                    "vendor_id": vendor,
                    "invoice_id": invoice,
                    "status": "requested",
                    "amount_minor": 2600,
                }
            ],
            "bills": [
                {
                    **common,
                    "id": "bill_df_7781",
                    "location_id": "loc_phoenix",
                    "department_id": "dept_ap",
                    "vendor_id": vendor,
                    "invoice_id": invoice,
                    "approval_status": "blocked_by_match_exception",
                    "payment_ready": False,
                }
            ],
            "inventory": [
                {
                    **common,
                    "id": "led_open_chix",
                    "location_id": "loc_phoenix",
                    "department_id": "dept_food",
                    "transaction_type": "opening_balance",
                    "item_id": chicken,
                    "quantity": {"amount": "180", "unit": "lb"},
                    "unit_cost": {"currency": "USD", "amount_minor": 248},
                    "extended_cost": {"currency": "USD", "amount_minor": 44640},
                    "timestamp": NOW,
                }
            ],
            "production": [
                {
                    **common,
                    "id": "batch_adobo_001",
                    "location_id": "loc_commissary",
                    "department_id": "dept_food",
                    "recipe_id": recipe,
                    "batch_status": "completed",
                    "yield_quantity": {"amount": "96", "unit": "portion"},
                }
            ],
            "recipes": [
                {
                    **common,
                    "id": recipe,
                    "department_id": "dept_food",
                    "name": "Adobo Chicken Taco",
                    "recipe_type": "menu_item",
                    "selling_price_minor": 925,
                    "ingredient_cost_minor": 208,
                    "labor_cost_minor": 20,
                    "packaging_cost_minor": 18,
                    "allergen_disclaimer": ALLERGEN_DISCLAIMER,
                    "ingredients": [
                        {"item_id": chicken, "quantity": "3.2", "unit": "oz"},
                        {"item_id": tortillas, "quantity": "2", "unit": "each"},
                    ],
                }
            ],
            "menus": [
                {
                    **common,
                    "id": "menu_adobo_taco",
                    "location_id": "loc_phoenix",
                    "recipe_id": recipe,
                    "selling_price": {"currency": "USD", "amount_minor": 925},
                    "plate_cost_minor": 246,
                    "gross_profit_minor": 679,
                    "food_cost_percent": "26.59",
                    "quadrant": "star",
                }
            ],
            "forecasts": [
                {
                    **common,
                    "id": "forecast_friday_chix",
                    "location_id": "loc_phoenix",
                    "item_id": chicken,
                    "forecast_demand": "148",
                    "current_usable": "152",
                    "safety_stock": "25",
                }
            ],
            "analytics": [
                {
                    **common,
                    "id": "avt_chix_week29",
                    "location_id": "loc_phoenix",
                    "item_id": chicken,
                    "actual_quantity": "138",
                    "theoretical_quantity": "126.4",
                    "cost_variance_minor": 2877,
                    "probable_causes": ["short delivery not fully credited", "prep waste above plan"],
                }
            ],
            "tasks": [
                {
                    **common,
                    "id": "task_credit_followup",
                    "location_id": "loc_phoenix",
                    "department_id": "dept_ap",
                    "title": "Follow up on short chicken delivery credit",
                    "owner_id": "user_owner",
                    "status": "open",
                }
            ],
            "audit-logs": [
                {
                    **common,
                    "id": "auditlog_seed",
                    "actor_id": "system",
                    "action": "seed_demo_dataset",
                    "domain": "system",
                    "record_id": "org_blue_collar_demo",
                    "immutable": True,
                    "timestamp": NOW,
                }
            ],
            "global-iq": [
                {
                    **common,
                    "id": "gqa_food_cost_rise",
                    "question": "Why did food cost rise this week?",
                    "answer": (
                        "Food cost pressure is concentrated in chicken. The evidence shows a "
                        "10 lb receiving shortage, invoice pricing above the purchase order, "
                        "and prep waste above plan."
                    ),
                    "citations": [
                        {"domain": "invoices", "id": invoice},
                        {"domain": "receiving", "id": receipt},
                        {"domain": "analytics", "id": "avt_chix_week29"},
                    ],
                    "confidence": "0.84",
                    "evidence_complete": True,
                }
            ],
            "command-cards": [
                {
                    **common,
                    "id": "card_chicken_invoice_exception",
                    "location_id": "loc_phoenix",
                    "section": "Exceptions",
                    "plain_language_issue": "Chicken invoice bills 120 lb; Dock accepted 110 lb.",
                    "dollar_impact_minor": 2600,
                    "source": invoice,
                    "owner": "Accounts payable",
                    "recommended_action": "Request the 10 lb credit before bill approval.",
                    "deadline": "2026-07-17T18:00:00Z",
                    "rank": 1,
                    "confidence": "0.93",
                    "history": [{"at": NOW, "event": "three_way_match_exception_created"}],
                    "actions": ["investigate", "assign", "resolve"],
                    "status": "open",
                }
            ],
        }
    )
    return base
