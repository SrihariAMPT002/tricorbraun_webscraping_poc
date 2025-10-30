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
