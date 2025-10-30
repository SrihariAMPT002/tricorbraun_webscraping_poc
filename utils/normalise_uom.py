import os, json, re, time, sys
from datetime import datetime
from fractions import Fraction
from typing import Optional, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.find_non_products import get_non_products


def parse_capacity_with_ml(
    text: Optional[str],
) -> Optional[Dict[str, Optional[str | float]]]:
    """
    Extract capacity (supports mixed numbers, fractions, decimals including leading-decimal)
    and unit, then convert to milliliters.

    Examples matched: "1 1/2 oz", "1/2 oz", ".5 oz", "0.5 oz", "2 oz", "250 ml"
    """
    if not text:
        return None

    text = text.strip().lower()

    # Ignore clearly invalid capacity text
    if text in {"none", "n/a", "na", "-", "no", "nil"}:
        return None

    # Order matters: mixed numbers first, then fraction, then decimal (including leading .), then integer
    num_unit_re = re.compile(
        r"((?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d*\.\d+)|(?:\d+))\s*"
        r"(oz|fl\s*oz|floz|ml|milliliter|millilitre|l|liter|litre|ltr|gallon|gal|dram|drams|cc|centiliter|centilitre|cl)\b",
        re.IGNORECASE,
    )

    m = num_unit_re.search(text)
    if not m:
        return None

    num_str, uom = m.groups()
    uom = uom.lower().replace(".", "").replace(" ", "")

    # Normalize unit variants
    uom_map = {
        "gal": "gallon",
        "gallons": "gallon",
        "l": "liter",
        "litre": "liter",
        "litres": "liter",
        "ltr": "liter",
        "drams": "dram",
        "milliliter": "ml",
        "millilitre": "ml",
        "centiliter": "cl",
        "centilitre": "cl",
        "floz": "oz",
        "floz": "oz",
        "fl_oz": "oz",
    }
    uom = uom_map.get(uom, uom)

    # Parse numeric string to float, handling mixed numbers like "1 1/2"
    try:
        if " " in num_str and "/" in num_str:
            # Mixed number like "1 1/2"
            whole, frac = num_str.split()
            value = float(int(whole) + Fraction(frac))
        elif "/" in num_str:
            # Simple fraction like "1/2"
            value = float(Fraction(num_str))
        else:
            # Decimal or integer, supports leading decimal like ".5"
            value = float(num_str)
    except Exception:
        return None

    # Convert to ml (same conversion factors)
    conversion_factors = {
        "ml": 1,
        "cc": 1,
        "cl": 10,
        "liter": 1000,
        "oz": 29.5735,
        "gallon": 3785.411784,
        "dram": 3.6966911953125,
    }

    ml_value = None
    if uom in conversion_factors:
        ml_value = value * conversion_factors[uom]

    return {
        "value_raw": num_str,
        "value": value,
        "uom": uom,
        "value_ml": round(ml_value, 2) if ml_value is not None else None,
    }


def normalize_uom_values(capacity: Optional[str], product_name: Optional[str]) -> dict:
    """
    Normalize product capacity and UOM, automatically converting to milliliters (ml).
    Uses `parse_capacity_with_ml()` for extraction.
    Prioritizes `capacity` field, falls back to `product_name`.
    """
    normalized_uom_data = {
        "product_capacity_uom": None,
        "product_capacity_value": None,
        "normalized_capacity_uom": "ml",
        "normalized_capacity_value": None,
    }

    # Determine source text
    input_text = (capacity or "").strip()
    parsed = parse_capacity_with_ml(input_text)

    # If capacity field fails, fallback to product_name
    if not parsed and product_name:
        parsed = parse_capacity_with_ml(product_name)

    if not parsed:
        return normalized_uom_data

    normalized_uom_data.update(
        {
            "product_capacity_uom": parsed["uom"],
            "product_capacity_value": parsed["value_raw"],
            "normalized_capacity_value": parsed["value_ml"],
        }
    )

    return normalized_uom_data


def main():
    data = []
    all_invalid_products = []

    with open("demo_batch_data/berlin_products_pg=8.json", "r") as f:
        data = json.load(f)
        # results = get_non_products(data)
        # non_products = results["non_products"]
        # incomplete_products = results["incomplete_products"]
        # all_invalid_products.extend(non_products)
        # all_invalid_products.extend(incomplete_products)

    # print(len(all_invalid_products))
    # all_invalid_products_links = [
    #     product["product_url"] for product in all_invalid_products
    # ]

    repared_data = []
    for item in data:
        # if item["product_url"] in all_invalid_products_links:
        #     print(f" Skipping URL: {item['product_url']}")
        #     continue
        # item["product_specs"] = item.pop("product_information_specs")

        capacity = item["product_specs"].get("Capacity", None)
        product_name = item["product_name"]

        # if item["product_id"] in ("284686", "097977", "284414", "110008"):
        #     print("capacity:", capacity, "product_name:", product_name)

        normalised_uom_data = normalize_uom_values(capacity, product_name)

        # if item["product_id"] in ("284686", "097977", "284414", "110008"):
        #     print("capacity:", capacity, "product_name:", product_name)
        #     print(normalised_uom_data)

        item["product_normalised_data"] = normalised_uom_data

        reparsed_at = datetime.now().isoformat()

        item["product_metadata"] = {
            **item["product_metadata"],
            "reparsed_at": reparsed_at,
        }
        new_dict = {k: v for k, v in item.items() if k != "product_normalised_value"}

        repared_data.append(new_dict)

    # Save the updated data
    output_file = "demo_batch_data/berlin_products_data_pg=8.json"
    with open(output_file, "w") as f:
        json.dump(repared_data, f, indent=2)

    print(f"Normalized data saved to {output_file}")
    print(f"Processed {len(repared_data)} items")


if __name__ == "__main__":
    main()
    # return
    # print("debug mode")
    # print(
    #     "ml:",
    #     normalize_uom_values(
    #         "none",
    #         "1.75 Liter Clear Glass Nordic Pinch Liquor Bottle - 21.5 Bar Top Finish",
    #     ),
    # )

    # print(
    #     normalize_uom(
    #         "",
    #         "Mia 1 l Glass Claret Tapered Wine Bottles, ROPE Finish, Flint",
    #     )
    # )

    # print(
    #     "dram:",
    #     normalize_uom("", "1/2 dram (1.9ml) Amber Borosilicate Glass Vials, 8mm 8-425"),
    # )

    # print(
    #     "gallon:",
    #     normalize_uom("", "1 Gallon Amber Glass Jug with 38-400 Neck Finish"),
    # )

    # print(
    #     "oz:",
    #     normalize_uom(
    #         "32 oz", "32 Amber Glass Boston Round Bottles (Cap Not Included)"
    #     ),
    # )
