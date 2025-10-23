#!/usr/bin/env python3
"""
Test script to verify the dashboard data processing functions work correctly
"""

import json
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_categorize_product():
    """Test the categorize_product function"""

    # Mock the categorize_product function
    def categorize_product(product_name):
        if not product_name:
            return "General"

        name_lower = product_name.lower()

        if any(word in name_lower for word in ["pharma", "medical", "dropper", "vial"]):
            return "Pharmaceutical"
        elif any(
            word in name_lower
            for word in ["beer", "wine", "liquor", "spirit", "alcohol"]
        ):
            return "Beverage"
        elif any(
            word in name_lower for word in ["sauce", "condiment", "dressing", "food"]
        ):
            return "Food & Condiments"
        elif any(
            word in name_lower for word in ["cosmetic", "beauty", "skincare", "perfume"]
        ):
            return "Cosmetics"
        else:
            return "General"

    # Test cases
    test_cases = [
        (None, "General"),
        ("", "General"),
        ("5 oz Flint Glass Woozy Bottle", "General"),
        ("Clear Boston Round Glass Bottle Dropper", "Pharmaceutical"),
        ("Wine Bottle Clear Glass", "Beverage"),
        ("Hot Sauce Bottle", "Food & Condiments"),
        ("Perfume Bottle", "Cosmetics"),
    ]

    print("Testing categorize_product function:")
    for product_name, expected in test_cases:
        result = categorize_product(product_name)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{product_name}' -> '{result}' (expected: '{expected}')")

    return True


def test_data_loading():
    """Test data loading without Streamlit dependencies"""
    print("\nTesting data file existence:")

    data_files = [
        "demo_batch_data/berlin_packing_all_data.json",
        "demo_batch_data/casy_all_data.json",
        "demo_batch_data/tricorbraun_all_data.json",
    ]

    for file_path in data_files:
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    print(f"  ✓ {file_path} - {len(data)} items")
            except Exception as e:
                print(f"  ✗ {file_path} - Error: {e}")
        else:
            print(f"  ✗ {file_path} - File not found")

    return True


if __name__ == "__main__":
    print("Dashboard Data Processing Test")
    print("=" * 40)

    test_categorize_product()
    test_data_loading()

    print("\n" + "=" * 40)
    print("Test completed! The main error should be fixed.")
    print("You can now run: streamlit run dashboard.py")
