import os
import json
from datetime import datetime
import re
import time
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.normalize_to_ml import uom_to_ml


def normalize_uom(capacity, product_name):
    normalized_uom_data = {}
    if not capacity and not product_name:
        return normalized_uom_data

    if capacity:
        product_capacity, product_uom = get_capacity_and_uom(capacity)

    elif product_name:
        product_capacity, product_uom = get_capacity_and_uom(product_name)

    else:
        return None, None

    normalized_uom_data = {
        "product_capacity_uom": product_uom,
        "product_capacity_value": product_capacity,
        "normalized_capacity_uom": "ml",
        "normalized_capacity_value": (
            f"{uom_to_ml(product_uom,product_capacity)}" if product_capacity else None
        ),
    }

    return normalized_uom_data


def get_capacity_and_uom(product_name: str | None) -> tuple[str | None, str | None]:
    if not product_name:
        return None, None
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(oz|ml|L|gallon|dram|cc)", product_name, re.IGNORECASE
    )
    if not match:
        return None, None
    return match.group(1), match.group(2).lower()


def main():
    tricor_data = []
    with open("demo_batch_data/berlin_packing_all_data_deduped.json", "r") as f:
        tricor_data = json.load(f)

    for item in tricor_data:
        capacity = item["product_specs"].get("Capacity ", None)
        product_name = item["product_name"]

        normalised_uom_data = normalize_uom(capacity, product_name)

        item["product_normalized_uom"] = normalised_uom_data

        reparsed_at = datetime.now().isoformat()

        item["product_metadata"] = {
            **item["product_metadata"],
            "reparsed_at": reparsed_at,
        }

    # Save the updated data
    output_file = "demo_batch_data/berlin_packing_all_data_normalized.json"
    with open(output_file, "w") as f:
        json.dump(tricor_data, f, indent=2)

    print(f"Normalized data saved to {output_file}")
    print(f"Processed {len(tricor_data)} items")


if __name__ == "__main__":
    main()
