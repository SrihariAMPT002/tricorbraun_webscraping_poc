from datetime import datetime
import os
from pathlib import Path
import scrapy
import time
import json
import re
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import Rule
from utils.normalise_uom import normalize_uom_values


class PkSpiderSpider(scrapy.Spider):
    name = "pk_spider"
    allowed_domains = ["thecarycompany.com"]
    base_url = "https://www.thecarycompany.com"

    custom_settings = {"PLAYWRIGHT_BROWSER_TYPE": "chromium"}
    BASE_DIR = Path(__file__).resolve().parents[4]
    data_dir = os.path.join(
        BASE_DIR, "data/cary_company_glass_product_links/cary_glass_bottles_links.json"
    )
    with open(data_dir, "r") as f:
        product_links = json.load(f)

    start_urls = [link["url"] for link in product_links]
    rules = (Rule(LinkExtractor(), callback="parse", follow=False),)

    # --- Helper Functions ---
    def extract_basic_info(self, product_view):
        product_id = product_view.xpath(
            ".//div[contains(@class, 'product-info-stock-sku')]//span[@itemprop='sku']/text()"
        ).get()
        product_name = product_view.css(
            "span[data-ui-id='page-title-wrapper']::text"
        ).get()
        short_description = product_view.xpath(
            ".//div[contains(@class, 'short-description')]//div[@class='std']/text()"
        ).get()
        special_msg = product_view.xpath(
            ".//div[contains(@class, 'special-msg')]/text()"
        ).getall()
        company_name = "The Cary Company"
        return product_id, product_name, short_description, special_msg, company_name

    def extract_materials(self, product_view):
        description_tab = product_view.xpath(
            ".//div[contains(@class, 'description-tab-container')]"
        )

        # Get all material divs
        material_divs = description_tab.xpath(".//div[contains(@class, 'materials')]")

        if not material_divs:
            return {"material_kw": {}, "material_description": ""}

        # Prefer the second div (index 1), fallback to first (index 0)
        material_div = material_divs[1] if len(material_divs) > 1 else material_divs[0]

        # Full text
        all_text = material_div.xpath(".//text()").getall()
        material_description = " ".join(
            [t.strip() for t in all_text if t.strip() and "{" not in t]
        )

        # Links
        a_texts = material_div.xpath(".//a/text()").getall()
        a_hrefs = (
            material_div.xpath(".//a/@data-uw-original-href").getall()
            or material_div.xpath(".//a/@href").getall()
        )

        a_dict = {
            t.strip(): (
                f"{self.base_url}{h.strip()}"
                if h.strip().startswith("/")
                else h.strip()
            )
            for t, h in zip(a_texts, a_hrefs)
            if t.strip() and h.strip()
        }

        return {"material_kw": a_dict, "material_description": material_description}

    def extract_specifications(self, response):
        specs_table = response.xpath(
            '//div[contains(@class, "specifications-tab-container")]//table[@id="product-attribute-specs-table"]'
        )
        product_information = {}

        for row in specs_table.xpath(".//tr"):
            key = row.xpath("./th/text()").get(default="").strip()
            value = " ".join(
                [v.strip() for v in row.xpath("./td//text()").getall() if v.strip()]
            )
            if key and value:
                product_information[key] = value

        return product_information

    def extract_images_from_product_view(self, product_view):
        """Extract all product image URLs from the product view section."""
        images = []

        # Select all <img> tags under product view that are part of product media
        img_elements = product_view.xpath(
            ".//img[contains(@src, '/media/catalog/product')]"
        )

        for img in img_elements:
            src = img.xpath("./@src").get()
            if src and src not in [i["image_url"] for i in images]:
                images.append({"image_url": src})

        return images

    def extract_stock_status(self, product_view):
        from bs4 import BeautifulSoup

        stock_form_html = product_view.xpath(
            ".//form[@id='product_addtocart_form']"
        ).get()
        if not stock_form_html:
            return {"AvailabilityText": "", "Availability": "", "InStock": False}

        soup = BeautifulSoup(stock_form_html, "lxml")
        avail_block = soup.find("div", id="availability_block")

        stock_value = ""
        stock_text = ""
        in_stock = False

        if avail_block:
            # Try to read the data-mage-init JSON
            mage_init_attr = avail_block.get("data-mage-init")

            if mage_init_attr:
                try:
                    # Parse the JSON safely
                    mage_data = json.loads(str(mage_init_attr))
                    print("DEBUG: Parsed mage_data keys:", list(mage_data.keys()))

                    availability_info = mage_data.get(
                        "Cary_Catalog/js/widget/availability", {}
                    )
                    print("DEBUG: Parsed availability_info:", availability_info)

                    stock_value = str(availability_info.get("qty", "")).strip()
                    stock_text = availability_info.get("availability", "").strip()

                    # Determine stock boolean
                    in_stock = (
                        stock_value.isdigit() and int(stock_value) > 0
                    ) or stock_text.lower() in ["in stock", "available", "yes"]

                except json.JSONDecodeError as e:
                    print("DEBUG: JSON parse error:", e)

        result = {
            "availability_text": stock_text,
            "stock_count": stock_value,
            "in_stock": in_stock,
        }
        return result

    def extract_packing_details(self, product_view):
        packing_dict = {}
        packing_details = product_view.xpath(
            ".//div[contains(@class, 'packaging-detail')]"
        )
        for li in packing_details.xpath(".//ul/li"):
            text = li.xpath(".//span/text()").get(default="").strip()
            if ":" in text:
                key, value = map(str.strip, text.split(":", 1))
                packing_dict[key] = value
        return packing_dict

    def extract_sell_uom(self, product_view):
        sell_uom_dict = []
        uom_ul = product_view.xpath(
            ".//div[contains(@class, 'product-info')]//ul[contains(@class, 'tier-prices')]"
        )
        for li in uom_ul.xpath(".//li"):
            qty = (
                li.xpath(".//span[contains(@class, 'tier-qty')]/text()")
                .get(default="")
                .strip()
            )
            price = (
                li.xpath(".//span[contains(@class, 'price')]/text()")
                .get(default="")
                .strip()
            )
            if qty and price:
                sell_uom_dict.append({"qty": qty, "price": price})
        return sell_uom_dict

    def extract_metadata(self, start_time, product_object):
        end_time = time.time()
        missing_fields = [
            k for k, v in product_object.items() if not v or v == [] or v == {}
        ]
        return {
            "scraped_at": datetime.now().isoformat(),
            "processing_time": f"{end_time - start_time:.2f} seconds",
            "is_missing_fields": bool(missing_fields),
            "missing_fields": missing_fields,
        }

    def is_cap_included(
        self, specifications, product_name, short_description, product_notes
    ) -> bool:
        if "cap not included" in product_name.lower():
            return False
        if "cap not included" in short_description.lower():
            return False
        if specifications["Note:"]:
            if "*Caps and closures sold separately" in specifications["Note:"]:
                return False
        if product_notes:
            notes = " ".join(product_notes)
            if "*Caps and closures sold separately. " in notes:
                return False
        return True

    def get_product_accessories(self, product_view):
        related_products = []

        # Select the table correctly (not its text nodes)
        related_product_table = product_view.xpath(
            "//table[@id='related-product-table']"
        )

        # Loop through each table row
        for tr in related_product_table.xpath(".//tr"):
            # SKU (Part #)
            sku = (
                tr.xpath(".//div[contains(@class, 'extra-info related-part')]/text()")
                .get(default="")
                .strip()
            )

            # Product name + link
            name = (
                tr.xpath(".//p[@class='name-wrapper']/a/text()").get(default="").strip()
            )
            href = (
                tr.xpath(".//p[@class='name-wrapper']/a/@href").get(default="").strip()
            )

            # Availability
            availability = (
                tr.xpath(".//span[contains(@class, 'tooltip toggle value')]/text()")
                .get(default="")
                .strip()
            )

            # Price tiers (optional — captures all price/qty pairs)
            price_tiers = []
            for li in tr.xpath(
                ".//ul[contains(@class,'tier-prices')]/li[contains(@class,'tier-price')]"
            ):
                qty = (
                    li.xpath(".//span[@class='tier-qty']/text()")
                    .get(default="")
                    .strip()
                )
                price = (
                    li.xpath(".//span[@class='price']/text()").get(default="").strip()
                )
                if qty and price:
                    price_tiers.append({"qty": qty, "price": price})

            related_products.append(
                {
                    "name": name,
                    "href": href,
                    "sku": sku,
                    "availability": availability,
                    "price_tiers": price_tiers,
                }
            )

        return related_products

    # --- Main parse function ---
    def parse(self, response):
        start_time = time.time()

        product_view = response.xpath(
            "//body[@data-container='body']//div[@class='page-wrapper']//main[@id='maincontent']//div[contains(@class, 'columns')]//div[contains(@class, 'column main')]//div[@class='product-view'][1]"
        )

        product_id, product_name, short_description, special_msg, company_name = (
            self.extract_basic_info(product_view)
        )
        materials = self.extract_materials(product_view)
        specifications = self.extract_specifications(response)
        normalised_uom_data = normalize_uom_values(
            specifications.get("Capacity"), product_name
        )
        stock_status = self.extract_stock_status(product_view)
        packing_details = self.extract_packing_details(product_view)
        sell_uom = self.extract_sell_uom(product_view)
        specifications["is_cap_Included"] = self.is_cap_included(
            specifications, product_name, short_description, special_msg
        )
        product_accessories = self.get_product_accessories(product_view)

        images = self.extract_images_from_product_view(product_view)

        product_object_without_metadata = {
            "product_url": response.url,
            "product_id": f"Part#: {product_id}",
            "product_name": product_name,
            "product_description": short_description,
            "product_images": images,
            "product_notes": special_msg,
            "product_materials": materials,
            "product_specs": specifications,
            "product_availability": stock_status,
            "product_packing_details": packing_details,
            "product_sell_uom": sell_uom,
            "product_accessories": product_accessories,
            "product_normalized_data": normalised_uom_data,
        }

        metadata = self.extract_metadata(start_time, product_object_without_metadata)
        metadata["company_name"] = company_name
        product_object_without_metadata["product_metadata"] = metadata

        product_object = product_object_without_metadata

        yield product_object
