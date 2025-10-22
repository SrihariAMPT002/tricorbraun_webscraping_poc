import os, json, sys, time, re
from datetime import datetime
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.normalize_to_ml import uom_to_ml
DATA_DIR = "data/berlin_packing_data"
os.makedirs(DATA_DIR, exist_ok=True)

# -----------------------------------------------
# HELPERS
# -----------------------------------------------

def valid_berlin_url(url: str) -> bool:
    return url.startswith("https://www.berlinpackaging.com/")

def load_html_with_playwright(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/116.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="networkidle")
        html = page.content()
        browser.close()
        return html

# -----------------------------------------------
# FIELD EXTRACTORS
# -----------------------------------------------

def get_product_name(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("section.productView-details h1.productView-title")
    return tag.get_text(strip=True) if tag else None

def get_product_id(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("p.productView-sku span")
    if not tag:
        return None
    val = tag.get_text(strip=True)
    return val if val.startswith("#") else f"#{val}"

def get_description(soup: BeautifulSoup) -> str | None:
    div = soup.select_one("div.product-description-accordion-half div.parent-desc")
    return div.get_text(separator="\n", strip=True) if div else None

def get_product_notes(soup: BeautifulSoup) -> list[str]:
    ul = soup.select_one("div.productView-descriptionList ul")
    return [li.get_text(strip=True) for li in ul.find_all("li")] if ul else []

def get_product_images(soup: BeautifulSoup) -> list[dict]:
    img_tag = soup.select_one("img.productView-image--default")
    if not img_tag:
        return []
    img_url = img_tag.get("data-src") or img_tag.get("src")
    return [{"image_url": img_url}] if img_url else []

def get_free_shipping(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("span.freeship-msg")
    return tag.get_text(strip=True) if tag else None

def get_availability(soup: BeautifulSoup, free_shipping: str | None) -> dict:
    in_stock_tag = soup.select_one("span.availablity_status_val")
    expected_ship_tag = soup.select_one("span.expectedDate_status_val")
    return {
        "in_stock": in_stock_tag.get_text(strip=True) if in_stock_tag else None,
        "expected_ship": expected_ship_tag.get_text(strip=True) if expected_ship_tag else None,
        "free_shipping": free_shipping,
    }

def get_sell_uom(soup: BeautifulSoup) -> list[dict]:
    rows = soup.select("table#non-accordion tbody tr")
    uom_list = []
    for row in rows:
        cols = row.find_all("td")
        if len(cols) != 2:
            continue
        min_qty = cols[0].select_one("span.min-qty")
        max_qty = cols[0].select_one("span.max-qty")
        price_span = cols[1].select_one("span.reg-price span")
        per_unit_val = cols[1].find(string=True, recursive=False)
        per_unit_val_normalized = per_unit_val.replace("(", "").replace(")", "").strip() if per_unit_val else None

        min_val = min_qty.get_text(strip=True) if min_qty else None
        max_val = max_qty.get_text(strip=True) if max_qty else None
        price_val = price_span.get_text(strip=True) if price_span else None

        if min_val:
            qty_range = f"{min_val}-{max_val}" if max_val else f"{min_val}+"
            uom_list.append({"qty_range": qty_range, "price": f"${price_val}", "price_per_unit": per_unit_val_normalized})
    return uom_list

def get_product_specs(soup: BeautifulSoup) -> dict:
    specs = {}
    parent = soup.select_one("div#product-description-grid")
    if not parent:
        return specs

    ul = parent.select_one("ul")
    if not ul:
        return specs

    for li in ul.find_all("li"):
        title_el = li.select_one("span[class*='tooltip-title']")
        value_el = li.select_one("span[class*='desc-data-value']")
        if title_el:
            key = title_el.find(string=True, recursive=False)
            val = value_el.get_text(strip=True) if value_el else None
            specs[key] = val
    return specs

def get_capacity_and_uom(product_name: str | None) -> tuple[str | None, str | None]:
    if not product_name:
        return None, None
    match = re.search(r"(\d+(?:\.\d+)?)\s*(oz|ml|L|gallon)", product_name, re.IGNORECASE)
    if not match:
        return None, None
    return match.group(1), match.group(2).lower()

def get_each_price(product_name: str | None, selluom: list[dict]) -> float | None:
    if not product_name or not selluom:
        return None
    try:
        case_match = re.search(r"(\d+)\s*/\s*(cs|case)", product_name, re.IGNORECASE)
        if not case_match:
            return None
        qty_per_case = int(case_match.group(1))
        first_price = float(selluom[0]["price"])
        return float(f"{first_price / qty_per_case:.2f}")
    except Exception:
        return None

def is_cap_included(product_name, product_notes) -> bool:
    """Check only the product title for 'cap included' or 'cap not included'."""
    if not product_name and not product_notes:
        return False
    name = product_name.lower().replace("-", " ")
    if "cap not included" in name:
        return False
    if "cap included" in name:
        return True
    notes = " ".join(product_notes).replace("*",'').replace("(",'').replace(")",'')
    if "sold separately" in notes:
        return False
    return False

def get_product_associated_accessories(soup: BeautifulSoup) -> list[dict]:
    accessories = []

    section = soup.select_one("div#accessories-wrap")
    if not section:
        print("No accessories section found.")
        return accessories

    accessory_div = section.select_one("div.recommended-products")
    if not accessory_div:
        print("No recommended products section found.")
        return accessories

    items = accessory_div.select("div.slick-slide")

    for item in items:
        name_tag = item.select_one("span.itemTitle.card-title a")
        if not name_tag:
            continue  # Skip if no link found

        name = name_tag.get_text(strip=True)
        url = name_tag.get("href")

        # Skip the "Add a Custom Label" card
        if name.lower() == "add a custom label":
            continue

        # Ensure URLs are absolute
        if url and not str(url).startswith("http"):
            url = f"https://www.berlinpackaging.com{url}"

        sku = name.rsplit('-', 1)[-1].strip()

        accessories.append({
            "sku" : f"Item #{sku}",
            "name": name,
            "url": url
        })

    return accessories

# -----------------------------------------------
# MAIN SCRAPER
# -----------------------------------------------

def scrape_berlin(url: str) -> dict:
    start_time = time.time()
    html = load_html_with_playwright(url)
    soup = BeautifulSoup(html, "html.parser")

    product_name = get_product_name(soup)
    product_id = get_product_id(soup)
    product_description = get_description(soup)
    product_notes = get_product_notes(soup)
    product_image = get_product_images(soup)
    free_shipping = get_free_shipping(soup)
    product_availability = get_availability(soup, free_shipping)
    product_selluom = get_sell_uom(soup)
    product_specs = get_product_specs(soup)
    product_specs["is_cap_included"] = is_cap_included(product_name,product_notes)
    product_capacity, product_uom = get_capacity_and_uom(product_name)
    product_accessory = get_product_associated_accessories(soup)

    print(product_capacity, product_uom)

    normalized_uom = {
                    "product_capacity_uom": product_uom,
                    "product_capacity_value":product_capacity ,
                    "normalized_capacity_uom": "ml",
                    "normalized_capacity_value": f"{uom_to_ml(product_uom,product_capacity)}" if product_capacity else None,
                }

    all_fields = {
        "product_url": url,
        "product_id": product_id,
        "product_name": product_name,
        "product_description": product_description,
        "product_notes": product_notes,
        "product_images": product_image,
        "product_availability": product_availability,
        "product_sell_uom": product_selluom,
        "product_specs": product_specs,
        "product_capacity": product_capacity,
        "product_uom": product_uom,
        "product_accessories" : product_accessory,
        "product_normalised_value": normalized_uom
    }

    missing_fields = [k for k, v in all_fields.items() if not v or v == [] or v == {}]
    processing_time = round(time.time() - start_time, 2)

    product_metadata = {
        "scraped_at": datetime.now().isoformat(),
        "processing_time": processing_time,
        "is_missing_fields": len(missing_fields) > 0,
        "missing_fields": missing_fields,
        "company_name": "Berlin Packaging",
    }

    return {**all_fields, "product_metadata": product_metadata}

# -----------------------------------------------
# MAIN
# -----------------------------------------------

def check_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        return False
    return True

def main():
    if not check_data_dir():
        print(f"Data directory '{DATA_DIR}' created. Please add product URLs to scrape.")
        return

    product_link_dir = "data/berlin_packing_glass_product_links"

    for i in range(1, 7):  # file index (page number)
        product_urls = []
        file_path = f"{product_link_dir}/berlin_glassbottles_pg={i}.json"
        with open(file_path, "r", encoding="utf-8") as f:
            links = json.load(f)
            for item in links:
                if "url" in item and valid_berlin_url(item["url"]):
                    product_urls.append(item["url"])

        filename = f"berlin_products_pg={i}"
        filepath = os.path.join(DATA_DIR, f"{filename}.json")

        # Load existing data if available
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                    print("existing data len:", len(data))
                except json.JSONDecodeError:
                    data = []
        else:
            data = []

        # Collect already scraped URLs
        scraped_urls = {p.get("product_url") for p in data if "product_url" in p}

        print(len(scraped_urls))

        try:
            for idx, url in enumerate(product_urls, start=1):
                if url in scraped_urls:
                    print(f"⚠️  Skipping duplicate ({idx}/{len(product_urls)}) from page {i}: {url}")
                    continue

                print(f"🚀 [{i}:{idx}] Scraping started for: {url}")
                product = scrape_berlin(url)
                product["url"] = url  # ensure URL saved in data
                data.append(product)
                print(f"✅ [{i}:{idx}] Scraped: {product['product_name']}")

                # Save progress incrementally
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4, ensure_ascii=False)

                time.sleep(2)

        except Exception as e:
            print(f"❌ Error during scraping (page {i}): {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
