import os
import json
import time
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.thecarycompany.com/containers/glass/bottles?p={}"  # Replace this
OUTPUT_FILE = "cary_glass_bottles_links.json"

# Initialize JSON storage
if not os.path.exists(OUTPUT_FILE):
    with open(OUTPUT_FILE, "w") as f:
        json.dump([], f)

# Load existing data
with open(OUTPUT_FILE, "r") as f:
    try:
        existing_data = json.load(f)
    except json.JSONDecodeError:
        existing_data = []

existing_ids = {item["id"] for item in existing_data}
print(f"Loaded {len(existing_ids)} existing product IDs")

def scrape_page(page_number):
    url = BASE_URL.format(page_number)
    headers = {"User-Agent": "Mozilla/5.0"}
    print(f"Scraping page {page_number}: {url}")

    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to load page {page_number}, status: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # More flexible selector
    product_items = soup.select("li.item.product.product-item")
    if not product_items:
        print("No product items found on this page.")
        return []

    results = []
    for li in product_items:
        a_tag = li.select_one("a")
        href = a_tag["href"] if a_tag and a_tag.has_attr("href") else None

        # Try multiple methods to get product ID
        product_id = li.get("data-product-id")
        if not product_id:
            span = li.select_one("div.product.details.product-item-details span")
            product_id = span.get_text(strip=True) if span else None

        if href and product_id and product_id not in existing_ids:
            results.append({"id": product_id, "url": href})
            existing_ids.add(product_id)
    return results

# Iterate over pagination
for page in range(1, 18):  # change limit or make dynamic
    new_data = scrape_page(page)
    if not new_data:
        print("No more products found — stopping.")
        break

    # Append to JSON file incrementally
    existing_data.extend(new_data)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(existing_data, f, indent=2)

    print(f"Page {page}: added {len(new_data)} new products.")
    time.sleep(2)  # polite delay

print("Scraping complete.")
