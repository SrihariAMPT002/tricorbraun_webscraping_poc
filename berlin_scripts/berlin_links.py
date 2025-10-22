#scrape_product_links.py
import os
import json
import time
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- Constants ---
BASE_URL = "https://www.berlinpackaging.com/bottles/?material_group=Glass"
DATA_DIR = "data"
TOTAL_PAGES = 7
DELAY_BETWEEN_PAGES = 2  # seconds
os.makedirs(DATA_DIR, exist_ok=True)


def get_page_html(url):
    """Render the given page with Playwright and wait for product cards to load."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/116.0.0.0 Safari/537.36"
        ))

        print(f"🌐 Loading: {url}")
        page.goto(url, wait_until="domcontentloaded")

        # Wait until product cards are visible
        page.wait_for_selector("a.s-hawk-item.plp-product-card", timeout=20000)

        html = page.content()
        browser.close()
    return html


def extract_products(html):
    """Extract full product data from the page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    products = []

    for card in soup.select("a.s-hawk-item.plp-product-card"):
        # URL
        href = card.get("href")
        full_url = f"https://www.berlinpackaging.com{href}" if href else None

        # Image
        img_tag = card.select_one("img")
        img = img_tag.get("data-src") or img_tag.get("src") if img_tag else None

        # Name
        name_tag = card.select_one(".s-hawk-prod-title")
        name = name_tag.get_text(strip=True) if name_tag else None

        # Price
        price_tag = card.select_one(".s-hawk-prod-price, .s-hawk-price-wrap")
        price = price_tag.get_text(strip=True) if price_tag else None

        # SKU
        sku_tag = card.select_one(".s-hawk-prod-sku")
        sku = sku_tag.get_text(strip=True).replace("SKU", "").strip() if sku_tag else None

        if full_url and name:
            products.append({
                "name": name,
                "url": full_url,
                "price": price,
                "sku": f"#{sku}" if sku else None,
                "image": img
            })

    return products


def scrape_all_pages():
    """Scrape all 7 pages of glass bottle listings and save product data."""
    all_total = 0

    for pg in range(1, TOTAL_PAGES + 1):
        url = BASE_URL if pg == 1 else f"{BASE_URL}&pg={pg}"
        print(f"\n🔍 Scraping page {pg}: {url}")

        try:
            html = get_page_html(url)
            products = extract_products(html)
            all_total += len(products)

            filename = f"berlin_glassbottles_pg={pg}.json"
            filepath = os.path.join(DATA_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(products, f, indent=4, ensure_ascii=False)

            # Print a small preview
            print(f"✅ Page {pg}: {len(products)} products saved → {filename}")
            print(f"📦 Total so far: {all_total} products")
            for p in products[:2]:
                print(f"   🧴 {p['name']} | {p['price']} | {p['sku']}")

            if pg < TOTAL_PAGES:
                print(f"⏳ Waiting {DELAY_BETWEEN_PAGES}s before next page...")
                time.sleep(DELAY_BETWEEN_PAGES)

        except Exception as e:
            print(f"❌ Error scraping page {pg}: {e}")


if __name__ == "__main__":
    scrape_all_pages()
