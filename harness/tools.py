"""Deterministic tools for the demo restaurant ordering agent.

The menu is intentionally the ONLY ground truth the agent has. Anything not
answerable from it (kitchen practices, past orders, reservations) must trigger
a handoff — several golden cases test exactly that boundary.
"""

from __future__ import annotations

import json
import uuid

MENU: dict[str, dict] = {
    "butter chicken": {"price": 16.95, "tags": ["gluten_free"], "desc": "Tandoori chicken in tomato-butter gravy"},
    "chicken korma": {"price": 16.50, "tags": ["contains_nuts", "gluten_free"], "desc": "Creamy cashew-based curry"},
    "tandoori chicken": {"price": 17.50, "tags": ["gluten_free"], "desc": "Half chicken, clay-oven roasted"},
    "lamb biryani": {"price": 18.95, "tags": ["contains_dairy"], "desc": "Basmati rice layered with spiced lamb"},
    "vegetable biryani": {"price": 15.50, "tags": ["vegetarian", "contains_dairy"], "desc": "Basmati rice with seasonal vegetables"},
    "paneer tikka": {"price": 14.50, "tags": ["vegetarian", "gluten_free"], "desc": "Char-grilled paneer skewers"},
    "chana masala": {"price": 13.50, "tags": ["vegan", "gluten_free"], "desc": "Chickpeas in onion-tomato masala"},
    "dal makhani": {"price": 13.95, "tags": ["vegetarian", "contains_dairy"], "desc": "Black lentils simmered with cream"},
    "vegetable samosa": {"price": 6.50, "tags": ["vegan"], "desc": "Two pastries stuffed with spiced potato"},
    "garlic naan": {"price": 4.50, "tags": ["vegetarian", "contains_gluten"], "desc": "Leavened bread with garlic butter"},
    "plain naan": {"price": 3.50, "tags": ["vegan_option", "contains_gluten"], "desc": "Classic leavened bread"},
    "mango lassi": {"price": 5.50, "tags": ["vegetarian", "contains_dairy"], "desc": "Yogurt-mango drink"},
    "masala chai": {"price": 3.95, "tags": ["vegetarian", "contains_dairy"], "desc": "Spiced milk tea"},
    "gulab jamun": {"price": 6.95, "tags": ["vegetarian", "contains_dairy", "contains_nuts"], "desc": "Milk dumplings in cardamom syrup, pistachio garnish"},
}

TOOL_DEFINITIONS = [
    {
        "name": "menu_lookup",
        "description": (
            "Search the menu by item name, dietary tag (vegan, vegetarian, "
            "gluten_free, contains_nuts, contains_dairy, contains_gluten), or "
            "free text. Returns matching items with price, tags, description. "
            "This is the ONLY source of truth about the menu and ingredients."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Item name, tag, or free text"}},
            "required": ["query"],
        },
    },
    {
        "name": "place_order",
        "description": (
            "Place an order. Every item must exactly match a menu item name. "
            "Fails if any item is unknown or quantity is invalid. Prices come "
            "from the menu and cannot be modified."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "qty": {"type": "integer"},
                            "notes": {"type": "string", "description": "Preparation notes, e.g. 'extra spicy'"},
                        },
                        "required": ["name", "qty"],
                    },
                }
            },
            "required": ["items"],
        },
    },
    {
        "name": "handoff_to_staff",
        "description": (
            "Hand the conversation to a human staff member. Use for anything "
            "outside ordering and menu questions: reservations, complaints, "
            "refunds, catering, ingredient/kitchen questions the menu cannot "
            "answer, or when the caller cannot be understood after a "
            "clarification attempt."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"reason": {"type": "string"}},
            "required": ["reason"],
        },
    },
]


def menu_lookup(query: str) -> dict:
    q = query.lower().strip()
    hits = {}
    for name, item in MENU.items():
        if q in name or any(q == t or q in t for t in item["tags"]) or q in item["desc"].lower():
            hits[name] = item
    if not hits:
        return {"matches": [], "note": f"No menu items match '{query}'."}
    return {"matches": [{"name": n, **i} for n, i in hits.items()]}


def place_order(items: list) -> dict:
    if not items:
        return {"error": "Order contains no items."}
    total = 0.0
    validated = []
    for entry in items:
        name = str(entry.get("name", "")).lower().strip()
        qty = entry.get("qty", 0)
        if name not in MENU:
            return {"error": f"'{entry.get('name')}' is not on the menu. Order not placed."}
        if not isinstance(qty, int) or qty < 1:
            return {"error": f"Invalid quantity for '{name}'. Order not placed."}
        total += MENU[name]["price"] * qty
        validated.append({"name": name, "qty": qty, "notes": str(entry.get("notes", ""))[:200]})
    return {
        "order_id": f"ORD-{uuid.uuid4().hex[:8]}",
        "items": validated,
        "total": round(total, 2),
        "status": "placed",
    }


def handoff_to_staff(reason: str) -> dict:
    return {"status": "handed_off", "reason": str(reason)[:300]}


def execute_tool(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run a tool call. Returns (json_result, is_error)."""
    try:
        if name == "menu_lookup":
            result = menu_lookup(**tool_input)
        elif name == "place_order":
            result = place_order(**tool_input)
        elif name == "handoff_to_staff":
            result = handoff_to_staff(**tool_input)
        else:
            result = {"error": f"Unknown tool: {name}"}
    except TypeError as exc:
        result = {"error": f"Bad arguments for {name}: {exc}"}
    return json.dumps(result), "error" in result
