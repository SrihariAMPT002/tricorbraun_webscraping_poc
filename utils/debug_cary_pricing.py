import re


def parse_float(value):
    if not value:
        return 0.0
    value = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(value)
    except ValueError:
        return 0.0


def parse_count(value):
    if not value:
        return 0
    try:
        return float(re.sub(r"[^\d.]", "", str(value)))
    except ValueError:
        return 0


def extract_cary_pricing(sell_uom, packing_details=None, product_notes=None):
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    items_per_case = 0
    items_per_pallet = 0

    if product_notes:
        joined = " ".join(product_notes).lower()
        case_match = re.search(r"(\d+)\s?(?:per\s?(?:case|box|carton))", joined)
        pallet_match = re.search(r"(\d+)\s?(?:per\s?pallet)", joined)
        if case_match:
            items_per_case = float(case_match.group(1))
        if pallet_match:
            items_per_pallet = float(pallet_match.group(1))

    if not items_per_case and packing_details:
        items_per_case = parse_count(packing_details.get("Case Pack"))
    if not items_per_pallet and packing_details:
        items_per_pallet = parse_count(packing_details.get("Pallet Pack"))

    breaks = []
    unit_prices = []

    for tier in sell_uom:
        qty_str = tier.get("qty", "")
        if qty_str.lower() == "quantity":
            continue

        unit = (tier.get("unit") or "").strip().lower().rstrip(".")
        price_value = parse_float(tier.get("price"))
        price_per_unit = 0.0

        if unit == "case" and items_per_case > 0:
            price_per_unit = round(price_value / items_per_case, 4)
        elif unit == "pallet" and items_per_pallet > 0:
            price_per_unit = round(price_value / items_per_pallet, 4)
        elif unit in ["piece", "ea", "each", ""]:
            price_per_unit = round(price_value, 4)
        else:
            continue

        unit_prices.append(price_per_unit)
        breaks.append(
            {
                "quantity_of_packing": qty_str,
                "type_of_packing": unit,
                "price_per_packing": price_value,
                "price_per_item": price_per_unit,
            }
        )

    base_price = round(sum(unit_prices) / len(unit_prices), 4) if unit_prices else 0
    return {"base_price": base_price, "breaks": breaks}


# Example usage
packing = {"Case Pack": "12 ea.", "Pallet Pack": "1,200 ea. (100 Cases)"}
uom = [
    {"qty": "Quantity", "price": "Price", "unit": "Quantity"},
    {"qty": "12", "price": "$2.020", "unit": "ea."},
    {"qty": "96", "price": "$1.620", "unit": "ea."},
    {"qty": "672", "price": "$1.370", "unit": "ea."},
    {"qty": "1344", "price": "$1.170", "unit": "ea."},
    {"qty": "2688", "price": "$1.050", "unit": "ea."},
]
product_notes = [
    "Packed in a 12x1 Re-Shipper Carton (12 per box)",
    "*Corks sold separately. -- Scroll down below to view recommended options.",
    "*It is recommended to clean before use.",
]

print(extract_cary_pricing(uom, packing, product_notes))
