import json
from typing import Optional


def get_non_products(data=Optional[list]):
    """
    Find products that are straight up not products vs incomplete products.

    Logic:
    1. First check if it's an incomplete product (missing essential fields)
    2. If it's incomplete, it's still a product (just needs data)
    3. Only classify as "non-product" if it has SKU-URL mismatch AND is not incomplete
    """
    non_products = []
    incomplete_products = []

    for product in data:
        product_id = product.get("product_id", "")
        product_url = product.get("product_url", "")

        # Not incomplete, now check SKU-URL match
        is_valid_product = check_sku_url_match(product_id, product_url)

        if not is_valid_product:
            # SKU-URL mismatch AND not incomplete = straight up not a product
            issues = check_incomplete_product(product)

            if issues:
                if "missing_normalized_capacity" in issues:
                    non_products.append(
                        {
                            "product_url": product_url,
                            "product_id": product_id,
                            "product_name": product.get("product_name"),
                            "issue": "sku_url_mismatch",
                            "type": "non_product",
                        }
                    )
                else:
                    incomplete_products.append(
                        {
                            "product_url": product_url,
                            "product_id": product_id,
                            "product_name": product.get("product_name"),
                            "issues": issues,
                            "severity": len(issues),
                            "type": "incomplete_product",
                        }
                    )

    return {"non_products": non_products, "incomplete_products": incomplete_products}


def check_sku_url_match(product_id, product_url):
    """
    Simple check: if product_id exists and URL contains the SKU or similar pattern
    """
    if not product_id or not product_url:
        return False

    # Remove common prefixes from product_id
    clean_sku = product_id.replace("#", "").replace("-", "").lower()

    # Check if URL contains the SKU or a variation
    url_lower = product_url.lower()

    # Direct match
    if clean_sku in url_lower:
        return True

    # Check for partial matches (first few characters)
    if len(clean_sku) >= 4 and clean_sku[:4] in url_lower:
        return True

    # Check if URL ends with the SKU pattern
    if url_lower.endswith(clean_sku):
        return True

    return False


def check_incomplete_product(product):
    """
    Check if a valid product is missing essential information
    """
    issues = []

    # Essential product information
    if not product.get("product_name") or product.get("product_name").strip() == "":
        issues.append("missing_product_name")

    if (
        not product.get("product_description")
        or product.get("product_description").strip() == ""
    ):
        issues.append("missing_product_description")

    # Product images are essential for e-commerce
    if not product.get("product_images") or len(product.get("product_images", [])) == 0:
        issues.append("missing_product_images")

    # Product specs are essential technical information
    if not product.get("product_specs") or len(product.get("product_specs", {})) == 0:
        issues.append("missing_product_specs")
    elif len(
        product.get("product_specs", {})
    ) == 1 and "is_cap_included" in product.get("product_specs", {}):
        # Only has is_cap_included, which is minimal
        issues.append("minimal_product_specs")

    # Pricing information is essential for commerce
    if (
        not product.get("product_sell_uom")
        or len(product.get("product_sell_uom", [])) == 0
    ):
        issues.append("missing_pricing")

    # Availability information
    availability = product.get("product_availability", {})
    if not availability or (
        not availability.get("in_stock") and not availability.get("expected_ship")
    ):
        issues.append("missing_availability")

    # Check if product has normalized UOM data (capacity information)
    normalized_data = product.get("product_normalised_value", {})
    if not normalized_data or not normalized_data.get("normalized_capacity_value"):
        issues.append("missing_normalized_capacity")

    # Only return issues if there are 2 or more problems
    return issues if issues else []


def print_non_products():
    """Print non-products and incomplete products in a readable format"""
    with open("demo_batch_data/tricorbraun_all_data_deduped.json", "r") as f:
        data = json.load(f)
        results = get_non_products(data)

        non_products = results["non_products"]
        incomplete_products = results["incomplete_products"]

        print(f"Found {len(non_products)} NON-PRODUCTS (SKU-URL mismatch):")
        print("=" * 80)
        for i, product in enumerate(non_products, 1):
            print(f"{i}. Product ID: {product['product_id']}")
            print(f"   URL: {product['product_url']}")
            print(f"   Name: {product['product_name']}")
            print(f"   Issue: {product['issue']}")
            print("-" * 80)

        print(
            f"\nFound {len(incomplete_products)} INCOMPLETE PRODUCTS (valid but missing info):"
        )
        print("=" * 80)
        for i, product in enumerate(incomplete_products, 1):
            print(f"{i}. Product ID: {product['product_id']}")
            print(f"   URL: {product['product_url']}")
            print(f"   Name: {product['product_name']}")
            print(f"   Issues ({product['severity']}): {', '.join(product['issues'])}")
            print("-" * 80)


if __name__ == "__main__":
    print_non_products()
    # non_products = get_non_products()
    # print(f"Found {len(non_products)} products with null attributes")

    # # Print first 10 results
    # for i, product in enumerate(non_products[:10], 1):
    #     print(
    #         f"{i}. ID: {product['product_id']} | URL: {product['product_url']} | Null: {product['null_attributes']}"
    #     )

    # if len(non_products) > 10:
    #     print(f"... and {len(non_products) - 10} more products")
