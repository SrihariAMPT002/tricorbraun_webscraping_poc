import os, json, re, time, sys
from datetime import datetime
from fractions import Fraction
from typing import Optional, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from find_non_products import get_non_products


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

    # Order matters: mixed numbers first, then fraction, then decimal (including leading .), then integer
    num_unit_re = re.compile(
        r"((?:\d+\s+\d+/\d+)|(?:\d+/\d+)|(?:\d*\.\d+)|(?:\d+))\s*"
        r"(oz|ml|l|litre|liter|gallon|gal|dram|drams|cc)\b",
        re.IGNORECASE,
    )

    m = num_unit_re.search(text)
    if not m:
        return None

    num_str, uom = m.groups()
    uom = uom.lower().replace(".", "")
    if uom in ("gal", "gallons"):
        uom = "gallon"
    elif uom in ("l", "litre"):
        uom = "liter"
    elif uom in ("drams",):
        uom = "dram"

    # Parse numeric string to float, handling mixed numbers like "1 1/2"
    value = None
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

    # Convert to ml (same conversion factors as before)
    if uom in ("ml", "milliliter", "millilitre", "milli"):
        ml_value = value
    elif uom in ("l", "liter"):
        ml_value = value * 1000
    elif uom in ("cc",):
        ml_value = value
    elif uom in ("oz", "fl oz", "floz", "ounce", "ounces"):
        ml_value = value * 29.5735
    elif uom in ("gallon", "gal"):
        ml_value = value * 3785.411784
    elif uom in ("dram",):
        ml_value = value * 3.6966911953125
    else:
        ml_value = None

    return {
        "value_raw": num_str,
        "value": value,
        "uom": uom,
        "value_ml": round(ml_value, 2) if ml_value is not None else None,
    }


def normalize_uom_values(capacity: Optional[str], product_name: str | None) -> dict:
    """
    Normalize product capacity and UOM, automatically converting to milliliters (ml).

    ```
    Uses `parse_capacity_with_ml()` for extraction.
    Prioritizes `capacity` field, falls back to `product_name`.

    Returns:
        {
            "product_capacity_uom": str | None,
            "product_capacity_value": str | None,
            "normalized_capacity_uom": "ml",
            "normalized_capacity_value": float | None
        }
    """
    normalized_uom_data = {
        "product_capacity_uom": None,
        "product_capacity_value": None,
        "normalized_capacity_uom": "ml",
        "normalized_capacity_value": None,
    }

    # Determine source text
    input_text = capacity or product_name
    if not input_text:
        return normalized_uom_data

    parsed = parse_capacity_with_ml(input_text)
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

    with open("demo_batch_data/cary_all_data.json", "r") as f:
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
        item["product_specs"] = item.pop("product_information_specs")

        capacity = item["product_specs"].get("Capacity", None)
        product_name = item["product_name"]

        normalised_uom_data = normalize_uom_values(capacity, product_name)

        item["product_normalised_data"] = normalised_uom_data

        reparsed_at = datetime.now().isoformat()

        item["product_metadata"] = {
            **item["product_metadata"],
            "reparsed_at": reparsed_at,
        }
        new_dict = {k: v for k, v in item.items() if k != "product_normalized_uom"}

        repared_data.append(new_dict)

    # Save the updated data
    output_file = "demo_batch_data/cary_all_data_normalized.json"
    with open(output_file, "w") as f:
        json.dump(repared_data, f, indent=2)

    print(f"Normalized data saved to {output_file}")
    print(f"Processed {len(repared_data)} items")


if __name__ == "__main__":
    main()
    # print(
    #     "ml:",
    #     normalize_uom(
    #         "",
    #         "375 ml Clear Glass California Long Neck Bottle - 18.5 Bar Top Neck Finish",
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
