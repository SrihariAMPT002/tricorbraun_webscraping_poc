import os, json, re


def get_cary_packing_details():
    with open("demo_batch_data/casy_all_data.json", "r") as f:
        cary_data = json.load(f)

    for d in cary_data:
        packing_details = d.get("product_packing_details", {})

        product_notes = d.get("product_notes", [])
        case_pack_from_notes = ""
        if product_notes:
            joined_notes = " ".join(product_notes).lower()
            if (
                "Please note, this bottle is packed in a 12x1 Re-Shipper Carton (12 bottles per box)".lower()
                or "Packed in a 12x1 Re-Shipper Carton (12 per box)".lower()
                in joined_notes
            ):
                case_pack_from_notes = "12 ea."

        pricing = extract_cary_pricing(
            d.get("product_sell_uom", []),
            packing_details,
            case_pack_from_notes,
            d["product_url"],
        )


def extract_cary_pricing(sell_uom, packing_details, case_pack_notes, url):
    """Extract pricing from Cary Company sell_uom data"""
    if not sell_uom:
        return {"base_price": 0, "breaks": []}

    # print(case_pack_notes)
    items_per_case = ""
    items_per_pallet = ""
    if packing_details:
        items_per_case = packing_details.get("Case Pack", None)
        items_per_pallet = packing_details.get("Pallet Pack", None)

    if not items_per_case:
        items_per_case = case_pack_notes if case_pack_notes else ""

    breaks = []
    unit_prices = []

    # print(sell_uom)

    for tier in sell_uom:
        # Skip header row
        if tier.get("qty") == "Quantity":
            continue

        price_str = tier.get("price", "$0")
        qty_str = tier.get("qty", "1")

        try:
            price = float(re.sub(r"[^\d.]", "", price_str))
            unit_prices.append(price)
            base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

            if price > 15:
                if price == 56389.0:
                    price = price / 10000
                items = float(items_per_case.replace("ea.", ""))
                price = price / items

            unit_prices.append(price)

            breaks.append(
                {
                    "quantity": qty_str,
                    "price": price,
                    "price_per_unit": price_str,
                }
            )
        except (ValueError, TypeError):
            continue

    # Calculate average unit price across all tiers
    base_price = sum(unit_prices) / len(unit_prices) if unit_prices else 0

    if base_price > 3:
        items_per_case_float = float(items_per_case.replace("ea.", ""))
        base_price = base_price / items_per_case_float

    print(f"{'=' * 60}")
    print(f"URL: {url}")
    print(f"Computed base price: ${base_price:.2f}")
    # print(items_per_case)

    return {"base_price": base_price, "breaks": breaks}


get_cary_packing_details()
