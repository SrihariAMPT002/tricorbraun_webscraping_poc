import re
from typing import Optional


def parse_float(value):
    if not value:
        return 0.0
    value = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(value)
    except ValueError:
        return 0.0


def extract_berlin_pricing(sell_uom, packing_unit_quantity: Optional[str]):
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    try:
        packing_unit_count = (
            float(re.sub(r"[^\d.]", "", packing_unit_quantity))
            if packing_unit_quantity
            else 1.0
        )
    except ValueError:
        packing_unit_count = 1.0

    breaks = []
    unit_prices = []
    current_unit = None
    current_unit_qty = None

    print(packing_unit_count)

    for tier in sell_uom:
        qty_range = tier.get("qty_range")
        price_per_packing_str = tier.get("price")
        price_per_unit_str = tier.get("price_per_unit")
        is_header = str(tier.get("header", "false")).lower() == "true"

        if is_header:
            match = re.match(
                r"(\w+)\s*\(Qty\s*([\d,]+)\)", qty_range or "", re.IGNORECASE
            )
            if match:
                current_unit = match.group(1).title()
                current_unit_qty = float(match.group(2).replace(",", ""))
            else:
                current_unit = (qty_range or "").title()
                current_unit_qty = 1.0
            continue

        price_per_packing = parse_float(price_per_packing_str)
        price_per_unit = parse_float(price_per_unit_str)

        if not price_per_unit_str:
            if price_per_packing > 10 and packing_unit_count > 0:
                price_per_unit = round(price_per_packing / packing_unit_count, 4)
            else:
                price_per_unit = price_per_packing

        if price_per_unit == 0 and price_per_packing > 0 and packing_unit_count > 0:
            price_per_unit = round(price_per_packing / packing_unit_count, 4)

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity_of_packing": qty_range,
                "type_of_packing": current_unit,
                "price_per_packing": price_per_packing,
                "price_per_item": price_per_unit,
                "unit_quantity": current_unit_qty,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


berlin_price = [
    {"qty_range": "924", "price": "$1071.84", "price_per_unit": "$1.15 ea."}
]
print(extract_berlin_pricing(berlin_price, "9,216"))


def extract_tricor_pricing(selluom):
    if not selluom:
        return {"base_price": 0, "breaks": []}

    breaks = []
    unit_prices = []

    for item in selluom:
        qty_text = item.get("qty_range") or ""
        qty_match = re.search(r"(\d+)", qty_text)
        qty = int(qty_match.group(1)) if qty_match else 1

        unit = (item.get("unit") or "").strip()
        price = parse_float(item.get("price"))
        price_per_unit = parse_float(item.get("price_per_unit"))

        if unit.lower() == "piece" and not price_per_unit:
            price_per_unit = price
        if not price_per_unit and price > 0 and qty > 0:
            price_per_unit = round(price / qty, 4)

        if price_per_unit > 0:
            unit_prices.append(price_per_unit)

        breaks.append(
            {
                "quantity_of_packing": qty,
                "type_of_packing": unit,
                "price_per_packing": price,
                "price_per_item": price_per_unit,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


tricor_price = [
    {
        "qty_range": "1 Case",
        "unit": "Case",
        "price": "$17.21",
        "price_per_unit": "$1.43",
    },
    {
        "qty_range": "12 Case",
        "unit": "Case",
        "price": "$15.49",
        "price_per_unit": "$1.29",
    },
    {
        "qty_range": "18 Case",
        "unit": "Case",
        "price": "$13.01",
        "price_per_unit": "$1.08",
    },
    {
        "qty_range": "160 Case",
        "unit": "Case",
        "price": "$11.06",
        "price_per_unit": "$0.92",
    },
]

# print(extract_tricor_pricing(tricor_price))
