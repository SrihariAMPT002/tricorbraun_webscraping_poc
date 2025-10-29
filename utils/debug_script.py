# import os, json, re


# def get_cary_packing_details():
#     with open("demo_batch_data/casy_all_data.json", "r") as f:
#         cary_data = json.load(f)

#     for d in cary_data:
#         packing_details = d.get("product_packing_details", {})

#         product_notes = d.get("product_notes", [])
#         case_pack_from_notes = ""
#         if product_notes:
#             joined_notes = " ".join(product_notes).lower()
#             if (
#                 "Please note, this bottle is packed in a 12x1 Re-Shipper Carton (12 bottles per box)".lower()
#                 or "Packed in a 12x1 Re-Shipper Carton (12 per box)".lower()
#                 in joined_notes
#             ):
#                 case_pack_from_notes = "12 ea."

#         pricing = extract_cary_pricing(
#             d.get("product_sell_uom", []),
#             packing_details,
#             case_pack_from_notes,
#             d["product_url"],
#         )


# def extract_cary_pricing(sell_uom, packing_details, case_pack_notes, url):
#     """Extract pricing from Cary Company sell_uom data"""
#     if not sell_uom:
#         return {"base_price": 0, "breaks": []}

#     # print(case_pack_notes)
#     items_per_case = ""
#     items_per_pallet = ""
#     if packing_details:
#         items_per_case = packing_details.get("Case Pack", None)
#         items_per_pallet = packing_details.get("Pallet Pack", None)

#     if not items_per_case:
#         items_per_case = case_pack_notes if case_pack_notes else ""

#     breaks = []
#     unit_prices = []

#     # print(sell_uom)

#     for tier in sell_uom:
#         # Skip header row
#         if tier.get("qty") == "Quantity":
#             continue

#         price_str = tier.get("price", "$0")
#         qty_str = tier.get("qty", "1")

#         try:
#             price = float(re.sub(r"[^\d.]", "", price_str))
#             unit_prices.append(price)
#             base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

#             if price > 15:
#                 if price == 56389.0:
#                     price = price / 10000
#                 items = float(items_per_case.replace("ea.", ""))
#                 price = price / items

#             unit_prices.append(price)

#             breaks.append(
#                 {
#                     "quantity": qty_str,
#                     "price": price,
#                     "price_per_unit": price_str,
#                 }
#             )
#         except (ValueError, TypeError):
#             continue

#     # Calculate average unit price across all tiers
#     base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

#     if base_price > 3:
#         items_per_case_float = float(items_per_case.replace("ea.", ""))
#         base_price = base_price / items_per_case_float

#     print(f"{'=' * 60}")
#     print(f"URL: {url}")
#     print(f"Computed base price: ${base_price:.2f}")
#     # print(items_per_case)

#     return {"base_price": base_price, "breaks": breaks}


# get_cary_packing_details()


# import re

# from typing import Optional


# def extract_berlin_pricing(sell_uom, packing_unit_quantity: Optional[str]):
#     """Extract pricing from Berlin Packaging sell_uom data"""
#     if not sell_uom:
#         return {"base_price": 0, "breaks": []}

#     breaks = []
#     unit_prices = []

#     for tier in sell_uom:
#         # Extract unit price from price_per_unit field for base_price calculation
#         qty_range = tier.get("qty_range")
#         price_per_packing_str = tier.get("price")  # case / pallet
#         price_per_unit_str = tier.get("price_per_unit")
#         price_per_packing = 0
#         price_per_unit = 0

#         # if price_per_unit is null
#         if not price_per_unit_str:
#             price_per_packing = float(
#                 re.sub(r"[^\d.]", "", price_per_packing_str)
#             )  # $26.56 or $0.12 in edge cases

#             price_per_unit = price_per_packing
#             # handling price_per_unit outliers
#             if price_per_unit > 10:
#                 price_per_unit = price_per_unit / int(packing_unit_quantity)
#             unit_prices.append(price_per_unit)

#         # if price_per_unit is not null
#         else:
#             price_per_unit_value = re.sub(r"[^\d.]", "", price_per_unit_str).rstrip(
#                 "."
#             )  # $0.12 ea.
#             price_per_unit = float(price_per_unit_value)
#             price_per_packing = float(re.sub(r"[^\d.]", "", price_per_packing_str))
#             unit_prices.append(price_per_unit)

#         breaks.append(
#             {
#                 "quantity": qty_range,
#                 "price": price_per_packing,  # Use total price for case/pallet
#                 "price_per_unit": price_per_unit,
#             }
#         )

#     # Calculate average unit price across all tiers
#     base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

#     return {"base_price": base_price, "breaks": breaks}


# sell_uom = [
#     [
#         {"qty_range": "1-5", "price": "$48.78", "price_per_unit": None},
#         {"qty_range": "6-14", "price": "$46.34", "price_per_unit": None},
#         {"qty_range": "15+", "price": "$44.35", "price_per_unit": None},
#     ]
# ]
# for uom in sell_uom:
#     print(extract_berlin_pricing(uom, "12"))
#     print("-" * 10)


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
