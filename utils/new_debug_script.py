import json
import sys
import os


def clean_availability(input_path, output_path=None):
    if not os.path.exists(input_path):
        print(f"❌ File not found: {input_path}")
        return

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Ensure data is a list of product objects
    if not isinstance(data, list):
        print("⚠️ JSON is not a list. Wrapping it in a list for processing.")
        data = [data]

    for product in data:
        availability = product.get("product_availability")
        if isinstance(availability, dict):
            text = availability.get("availability_text", "")
            if isinstance(text, str):
                # Remove the "Availability:" prefix
                availability["availability_text"] = text.replace(
                    "Availability:", ""
                ).strip()

                # Set in_stock to False if text contains "Out Of Stock"
                if "out of stock" in text.lower():
                    availability["in_stock"] = False

    output_path = output_path or input_path  # overwrite if no output path specified
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Cleaned data saved to: {output_path}")


if __name__ == "__main__":
    clean_availability(
        "demo_batch_data/tricorbraun_new_data_normalized.json",
        "demo_batch_data/tricorbraun_new_data_normalized.json",
    )
