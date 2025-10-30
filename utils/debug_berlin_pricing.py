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
            else None
        )
    except ValueError:
        packing_unit_count = None

    breaks = []
    unit_prices = []
    current_unit = None
    current_unit_qty = None

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
                if not packing_unit_count:
                    packing_unit_count = current_unit_qty
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
    {"qty_range": "Pack (Qty 144)", "price": "Price Per Pack", "header": "true"},
    {"qty_range": "1-5", "price": "$89.42", "price_per_unit": "$0.62 ea."},
    {"qty_range": "6-9", "price": "$70.81", "price_per_unit": "$0.49 ea."},
    {"qty_range": "10+", "price": "$56.64", "price_per_unit": "$0.39 ea."},
]
print(extract_berlin_pricing(berlin_price, ""))
