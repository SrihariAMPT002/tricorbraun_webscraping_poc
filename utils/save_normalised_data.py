import json
import sys, os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard_utils.data_utils import (
    process_berlin_data,
    process_cary_data,
    process_tricor_data,
)


def load_data():
    """Load and process all company data"""
    companies = {}

    # Load Berlin Packaging data
    try:
        with open("demo_batch_data/berlin_packing_data.json", "r") as f:
            berlin_data = json.load(f)
            companies["Berlin Packaging"] = process_berlin_data(berlin_data)
    except FileNotFoundError:
        print("Warning: Berlin Packaging data not found. Skipping this company.")
        companies["Berlin Packaging"] = []

    # Load Cary Company data
    try:
        with open("demo_batch_data/cary_company_data.json", "r") as f:
            cary_data = json.load(f)
            companies["Cary Company"] = process_cary_data(cary_data)
    except FileNotFoundError:
        print("Warning: Cary Company data not found. Skipping this company.")
        companies["Cary Company"] = []

    # Load TricorBraun data
    try:
        with open("demo_batch_data/tricorbraun_data.json", "r") as f:
            tricor_data = json.load(f)
            companies["TricorBraun"] = process_tricor_data(tricor_data)
    except FileNotFoundError:
        print("Warning: TricorBraun data not found. Skipping this company.")
        companies["TricorBraun"] = []

    # Filter out empty companies
    companies = {k: v for k, v in companies.items() if v}

    if not companies:
        raise FileNotFoundError(
            "No data files found. Please ensure the JSON data files are in the demo_batch_data/ directory."
        )

    processed_data_output(companies)
    return companies


def processed_data_output(companies_data):
    """Output processed data to JSON file for external use."""
    all_data = []
    for company, data in companies_data.items():
        all_data.extend(data)

    with open("processed_data/processed_data_new.json", "w") as f:
        json.dump(all_data, f, indent=4)


load_data()
