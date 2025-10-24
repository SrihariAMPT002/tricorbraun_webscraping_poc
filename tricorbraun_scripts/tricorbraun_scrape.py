import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.normalise_uom import normalize_uom_values


ROOT_DIR = "data/tricorbraun_glass_product_links"
DATA_DIR = "data/tricorbraun_data"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

BATCH_SIZE = 50
REQUEST_DELAY = 2


# ======================================================
#                HELPER FUNCTIONS
# ======================================================


def extract_basic_info(section, soup):
    """Return (name, sku, desc, product_capacity, product_uom, desc_tag)."""
    title_tag = section.select_one('span.base[itemprop="name"]')
    sku_tag = section.select_one('div.product.attribute.sku div.value[itemprop="sku"]')
    desc_tag = section.select_one("div#description div.value")

    name = title_tag.get_text(strip=True) if title_tag else None
    sku = sku_tag.get_text(strip=True) if sku_tag else None
    desc = desc_tag.get_text("\n", strip=True) if desc_tag else None

    product_capacity, product_uom = None, None
    if name:
        match = re.search(r"(\d+(?:\.\d+)?)\s*(oz|ml|L|g|cc|dram|gallon)", name)
        if match:
            product_capacity = f"{match.group(1)} {match.group(2)}"
            product_uom = match.group(2)

    return name, sku, desc, product_capacity, product_uom, desc_tag


def extract_notes_from_description(soup, desc_tag):
    """Build notes list from description divs and related nodes."""
    notes = []
    if desc_tag:
        notes.extend([li.get_text(strip=True) for li in desc_tag.find_all("li")])

    extra_divs = soup.select(
        "div.product.attribute.description + div, "
        "div.product.attribute.description ~ div, "
        'div.value[itemprop="description"], '
        "div.info.pdp__info-text div"
    )
    for div in extra_divs:
        text = div.get_text(strip=True)
        if not text:
            continue

        if re.search(r"\d[\d,]*\s*/\s*(Case|Pallet)", text, re.IGNORECASE):
            if text not in notes:
                notes.append(text)

        if "Closures not included" in text and text not in notes:
            notes.append(text)

    return notes


def extract_quantity_from_description(soup):
    """Extract quantity (e.g., 128/Case or 28,800/Pallet)."""
    desc_tag = soup.select_one('div.value[itemprop="description"]')
    if not desc_tag:
        return None
    text = desc_tag.get_text(strip=True)
    match = re.search(r"(\d[\d,]*)\s*/\s*(Case|Pallet)", text, re.IGNORECASE)
    return match.group(1) if match else None


def extract_images(section):
    """Extract product image URLs."""
    images = []
    for img in section.select("img[src*='/media/catalog/product']"):
        src = img.get("src")
        if src and src not in [i["image_url"] for i in images]:
            images.append({"image_url": src})
    return images


def extract_specs(section, quantity=None):
    """Extract product specifications table."""
    specs = {}
    items_per_unit_value = section.select_one("div.items-per__case span.strong")
    specs["items_per_unit"] = (
        items_per_unit_value.get_text(strip=True) if items_per_unit_value else None
    )
    for row in section.select("table#product-attribute-specs-table tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            specs[th.get_text(strip=True)] = td.get_text(strip=True)
    if quantity:
        specs["quantity"] = quantity
    return specs


def cap_included_with_product(product_notes) -> bool:
    """Check only the product title for 'cap included' or 'cap not included'."""
    if not product_notes:
        return True
    if isinstance(product_notes, list):
        product_notes = " ".join(product_notes)
    notes = product_notes.lower().replace("-", " ")
    if "closures not included with bottles" in notes:
        return False
    return True


def extract_sell_uom(section, soup):
    """Extract pricing tiers (Case/Pallet) and per-unit price info."""
    tiers = []
    li_elements = section.select("ul.prices-tier li.item")
    tier_count = len(li_elements)
    for id, li in enumerate(li_elements):
        qty = li.select_one(".prices-tier_qty-unit")
        main_price = li.select_one(".price-wrapper .price")  # More precise
        per_unit = li.select_one(
            f".benefit .percent.tier-{id} .price"
        )  # Fixed selector

        qty_text = qty.get_text(strip=True) if qty else None
        price_text = main_price.get_text(strip=True) if main_price else None
        per_unit_text = per_unit.get_text(strip=True) if per_unit else None

        # Extract unit (e.g. "Case", "Pallet")
        unit_match = None
        if qty_text:
            parts = qty_text.split()
            if len(parts) > 1:
                unit_match = parts[-1]

        if qty_text and price_text:
            tiers.append(
                {
                    "qty_range": qty_text,
                    "unit": unit_match,
                    "price": price_text,
                    "price_per_unit": per_unit_text,
                }
            )

    return tiers


def get_availability(section):
    # Find the availability div inside the product section
    avail_div = section.select_one("div.items-availability")
    if not avail_div:
        return {"in_stock": "N/A"}

    # Extract all text spans
    text_spans = avail_div.select("span.text")
    # Usually, the second span holds the value ("In stock")
    avail_val = text_spans[1].get_text(strip=True) if len(text_spans) > 1 else None

    return {"in_stock": avail_val or "Unknown"}


def extract_caps_closures(section):
    if not section:
        return {"info": "No Related Products section found"}

    related = []

    # Step 1: Find all owl-item divs anywhere inside the section
    owl_items = section.select("div.owl-item")
    if not owl_items:
        print("⚠️ No owl-item divs found, trying broader search.")
        # Try fallback: look for <li> elements directly
        owl_items = section.select("li.item.product.product-item.related-item")

    if not owl_items:
        print("⚠️ Still no related products found.")
        return related

    # Step 2: Extract each product info
    for item in owl_items:
        li = item if item.name == "li" else item.find("li", class_="item")
        if not li:
            print("⚠️ No li found in this item, skipping.")
            continue

        sku_div = li.select_one("div.sku")
        a_tag = li.select_one("a.product-item-link")

        if not (sku_div and a_tag):
            print("⚠️ Missing SKU or link, skipping.")
            continue

        sku = sku_div.get_text(strip=True)
        name = a_tag.get_text(strip=True)
        url = a_tag.get("href")

        related.append({"sku": sku, "name": name, "url": url})
        print(f"✅ Found related item: SKU={sku}, Name={name}")

    return related


# ======================================================
#                PRODUCT SCRAPER
# ======================================================
def scrape_product(url):
    """Scrape one product page completely."""
    start_time = time.time()
    try:
        time.sleep(REQUEST_DELAY)

        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            print(f"⚠️ Failed: {url}")
            return None

        soup = BeautifulSoup(response.text, "html.parser")
        section = soup.select_one("div.product-info-main") or soup

        related_products_section = soup.select_one("div.related-wrap")

        if not related_products_section:
            print(f"⚠️ No related products found: {url}")

        # Use refactored helper functions
        name, sku, desc, product_capacity, product_uom, desc_tag = extract_basic_info(
            section, soup
        )
        notes = extract_notes_from_description(soup, desc_tag)

        # Cap Included
        closure_included = cap_included_with_product(notes)

        # Quantity
        quantity = extract_quantity_from_description(soup)

        # Images
        images = extract_images(section)

        # Sell tiers
        sell_uom = extract_sell_uom(section, soup)

        # Specs
        specs = extract_specs(section, quantity)

        specs["is_cap_included"] = closure_included

        related_caps_closures = extract_caps_closures(related_products_section)

        availability = get_availability(section)

        normalized_capacity = normalize_uom_values(specs.get("Capacity", None), name)
        product_fields = {
            "product_url": url,
            "product_id": sku,
            "product_name": name,
            "product_uom": product_uom,
            "product_capacity": product_capacity,
            "product_description": desc,
            "product_notes": notes,
            "product_images": images,
            "product_availability": availability,
            "product_selluom": sell_uom,
            "product_specs": specs,
            "product_accessories": related_caps_closures,
            "product_normalized_uom": normalized_capacity,
        }

        missing_fields = [
            k for k, v in product_fields.items() if not v or v == [] or v == {}
        ]

        elapsed = round(time.time() - start_time, 2)

        product_fields["product_metadata"] = {
            "scraped_at": datetime.now().isoformat(),
            "processing_time_seconds": elapsed,
            "is_missing_fields": len(missing_fields) > 0,
            "missing_fields": missing_fields,
            "company_name": "TricorBraun",
        }

        return product_fields

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None


# ======================================================
#              CATEGORY PROCESSOR
# ======================================================
def process_category(category_path):
    """Process all pages within one category, skipping duplicates and logging progress."""
    print(f"\n📂 Category: {os.path.basename(category_path)}")

    pages = sorted(
        [
            f
            for f in os.listdir(category_path)
            if f.startswith("page_") and f.endswith(".json")
        ]
    )
    if not pages:
        print("⚠️ No pages found.")
        return

    tricorbraun_data_path = os.path.join(DATA_DIR, category_path.split("/")[2])
    output_dir = os.path.join(tricorbraun_data_path, "batched_products")
    os.makedirs(output_dir, exist_ok=True)

    batch_data, batch_count = [], 1
    total_products, skipped_count = 0, 0
    start_time = time.time()

    # Collect already scraped URLs from existing batch files
    scraped_urls = set()
    for file in os.listdir(output_dir):
        if file.startswith("batch_") and file.endswith(".json"):
            with open(os.path.join(output_dir, file), "r", encoding="utf-8") as f:
                try:
                    batch = json.load(f)
                    scraped_urls.update(p.get("url") for p in batch if p.get("url"))
                except json.JSONDecodeError:
                    pass

    for page_index, page in enumerate(pages, start=1):
        page_path = os.path.join(category_path, page)
        with open(page_path, "r", encoding="utf-8") as f:
            products = json.load(f)

        for prod_index, item in enumerate(products, start=1):
            url = item.get("product_url")
            if not url:
                continue

            # Skip duplicates
            if url in scraped_urls:
                print(f"⚠️  Skipping duplicate ({page_index}:{prod_index}) → {url}")
                skipped_count += 1
                continue

            print(
                f"🚀 [{page_index}:{prod_index}] Scraping: {item.get('name', '')[:80]}"
            )
            data = scrape_product(url)
            if data:
                data["url"] = url
                batch_data.append(data)
                scraped_urls.add(url)
                total_products += 1
                print(
                    f"✅ [{page_index}:{prod_index}] Scraped: {data.get('product_name', '(no name)')}"
                )

            # Save every BATCH_SIZE items
            if len(batch_data) >= BATCH_SIZE:
                filename = f"batch_{batch_count:02d}.json"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(batch_data, f, indent=4, ensure_ascii=False)
                print(f"💾 Saved {len(batch_data)} → {filename}")
                batch_count += 1
                batch_data = []

    # Save remaining items
    if batch_data:
        filename = f"batch_{batch_count:02d}.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(batch_data, f, indent=4, ensure_ascii=False)
        print(f"💾 Saved remaining {len(batch_data)} → {filename}")

    elapsed = round(time.time() - start_time, 2)
    print(
        f"✅ Done {os.path.basename(category_path)} | {total_products} new | {skipped_count} skipped | {elapsed}s"
    )


# ======================================================
#              MASTER CATEGORY RUNNER
# ======================================================
def process_all_categories(root_dir):
    """Loop through all categories in /data."""
    categories = [
        os.path.join(root_dir, d)
        for d in os.listdir(root_dir)
        if os.path.isdir(os.path.join(root_dir, d))
    ]

    print(categories)
    print(f"📦 Found {len(categories)} categories total.")
    # data_dir = "data/tricorbraun_glass_product_links"
    # category_names = ["Glass_Liquor_and_Spirit_Bottles_109_items","Glass_Packer_Bottles_30_items"]
    # category_names = ["Beer_Bottles_and_Growlers_3_items"]
    for category_name in categories:
        process_category(category_name)
    # process_category("")
    # for category in categories[0:1]:
    #     process_category(category)


if __name__ == "__main__":
    process_all_categories(ROOT_DIR)
