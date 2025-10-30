import json


def find_duplicates():
    try:
        with open("demo_batch_data/berlin_new_data_normalised.json", "r") as f:
            berlin_data = json.load(f)
    except Exception as e:
        print(f"Error loading data: {e}")
        return

    print(f"Original: {len(berlin_data)} products")

    seen = set()
    unique_products = []
    for product in berlin_data:
        url = product.get("product_url")
        sku = product.get("product_id")
        key = (sku, url)
        if key in seen:
            continue
        seen.add(key)
        unique_products.append(product)

    print(f"After removing duplicates: {len(unique_products)} products")

    # Optionally, you could write the unique list back out or do something else with it.
    # For visualization/debugging, print the number of duplicates removed:
    print(f"Duplicates removed: {len(berlin_data) - len(unique_products)}")

    with open("demo_batch_data/berlin_new_data_normalised_deduped.json", "w") as f:
        json.dump(unique_products, f, indent=2)


find_duplicates()
