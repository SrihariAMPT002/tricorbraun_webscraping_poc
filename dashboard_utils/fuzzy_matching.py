"""
Fuzzy matching utilities for product comparison and similarity analysis.
This module contains all fuzzy matching, similarity scoring, and product comparison functions.
"""

import re
import streamlit as st
from rapidfuzz import fuzz
from typing import Dict, List, Any, Optional
import pint

# Initialize unit registry for capacity normalization
ureg = pint.UnitRegistry()


def normalize_capacity_fuzzy(value, unit):
    """Normalize capacity to milliliters"""
    try:
        return (value * ureg(unit)).to("milliliter").magnitude
    except:
        return value


def fuzzy_product_match(p1, p2):
    """Calculate enhanced fuzzy match score between two products based on capacity, price, and attributes"""

    # Capacity similarity (50% weight) - most important factor
    cap1 = normalize_capacity_fuzzy(p1["capacity"], p1["unit"])
    cap2 = normalize_capacity_fuzzy(p2["capacity"], p2["unit"])
    cap_score = 1 - min(abs(cap1 - cap2) / max(cap1, cap2, 1), 1)

    # Price similarity (30% weight) - second most important
    price_score = 1 - min(
        abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"], 1), 1
    )

    # Material similarity (10% weight)
    material_score = 0
    if p1.get("material") and p2.get("material"):
        material_score = (
            fuzz.ratio(p1["material"].lower(), p2["material"].lower()) / 100
        )
    elif not p1.get("material") and not p2.get("material"):
        material_score = 0.5  # Both missing, neutral score

    # Color similarity (5% weight)
    color_score = 0
    if p1.get("color") and p2.get("color"):
        color_score = fuzz.ratio(p1["color"].lower(), p2["color"].lower()) / 100
    elif not p1.get("color") and not p2.get("color"):
        color_score = 0.5  # Both missing, neutral score

    # Shape similarity (3% weight)
    shape_score = 0
    if p1.get("shape") and p2.get("shape"):
        shape_score = fuzz.ratio(p1["shape"].lower(), p2["shape"].lower()) / 100
    elif not p1.get("shape") and not p2.get("shape"):
        shape_score = 0.5  # Both missing, neutral score

    # Neck finish/closure type similarity (2% weight)
    closure_score = 0
    if p1.get("closure_type") and p2.get("closure_type"):
        closure_score = (
            fuzz.ratio(p1["closure_type"].lower(), p2["closure_type"].lower()) / 100
        )
    elif not p1.get("closure_type") and not p2.get("closure_type"):
        closure_score = 0.5  # Both missing, neutral score

    # Calculate weighted average (no name weight)
    total_score = (
        0.50 * cap_score
        + 0.30 * price_score
        + 0.10 * material_score
        + 0.05 * color_score
        + 0.03 * shape_score
        + 0.02 * closure_score
    )

    return total_score


def get_capacity_bracket(capacity_ml):
    """Get capacity bracket for a given capacity in ml"""
    if capacity_ml <= 50:
        return "0-50ml"
    elif capacity_ml <= 100:
        return "50-100ml"
    elif capacity_ml <= 250:
        return "100-250ml"
    elif capacity_ml <= 500:
        return "250-500ml"
    elif capacity_ml <= 1000:
        return "500-1000ml"
    else:
        return "1000ml+"


def group_products_by_capacity(products):
    """Group products by their capacity brackets"""
    capacity_groups = {}

    for product in products:
        capacity_ml = normalize_capacity_fuzzy(product["capacity"], product["unit"])
        bracket = get_capacity_bracket(capacity_ml)

        if bracket not in capacity_groups:
            capacity_groups[bracket] = []
        capacity_groups[bracket].append(product)

    return capacity_groups


def filter_products_by_price(products, exclude_zero_price=True):
    """Filter products based on price criteria"""
    if exclude_zero_price:
        return [p for p in products if p.get("price", 0) > 0]
    return products


def filter_products_by_search(products, search_term):
    """Filter products by search term (name, SKU, price)"""
    if not search_term:
        return products

    search_lower = search_term.lower()
    filtered = []

    for product in products:
        # Search in name
        if search_lower in product.get("name", "").lower():
            filtered.append(product)
            continue

        # Search in SKU
        if search_lower in product.get("sku", "").lower():
            filtered.append(product)
            continue

        # Search in price (exact match or range)
        try:
            price = float(product.get("price", 0))
            if (
                search_lower.replace("$", "")
                .replace(",", "")
                .replace(".", "")
                .isdigit()
            ):
                search_price = float(search_lower.replace("$", "").replace(",", ""))
                if (
                    abs(price - search_price) < 0.01
                ):  # Allow small floating point differences
                    filtered.append(product)
                    continue
        except (ValueError, TypeError):
            pass

    return filtered


@st.cache_data
def find_all_similar_products(
    companies_data, similarity_threshold=0.80, exclude_zero_price=True, search_term=""
):
    """Find all similar products for TricorBraun products across all companies"""
    if "TricorBraun" not in companies_data:
        return {}

    # Filter TricorBraun products
    tricorbraun_products = companies_data["TricorBraun"]
    tricorbraun_products = filter_products_by_price(
        tricorbraun_products, exclude_zero_price
    )
    tricorbraun_products = filter_products_by_search(tricorbraun_products, search_term)

    # Filter other companies' products
    other_companies = {}
    for k, v in companies_data.items():
        if k != "TricorBraun":
            filtered_products = filter_products_by_price(v, exclude_zero_price)
            filtered_products = filter_products_by_search(
                filtered_products, search_term
            )
            other_companies[k] = filtered_products

    all_matches = {}

    for tricor_product in tricorbraun_products:
        product_name = tricor_product["name"]
        similar_products = []

        # Compare with all other companies
        for company_name, company_products in other_companies.items():
            for other_product in company_products:
                similarity_score = fuzzy_product_match(tricor_product, other_product)

                if similarity_score >= similarity_threshold:
                    similar_products.append(
                        {
                            "company": company_name,
                            "product": other_product,
                            "similarity": similarity_score,
                            "capacity_diff_ml": abs(
                                normalize_capacity_fuzzy(
                                    tricor_product["capacity"], tricor_product["unit"]
                                )
                                - normalize_capacity_fuzzy(
                                    other_product["capacity"], other_product["unit"]
                                )
                            ),
                            "price_diff": abs(
                                tricor_product["price"] - other_product["price"]
                            ),
                        }
                    )

        # Sort by similarity score (highest first)
        similar_products.sort(key=lambda x: x["similarity"], reverse=True)

        if similar_products:
            all_matches[product_name] = {
                "tricorbraun_product": tricor_product,
                "similar_products": similar_products,
                "total_matches": len(similar_products),
            }

    return all_matches


def get_similarity_summary(all_matches, original_tricorbraun_count=0):
    """Get summary statistics for all similarity matches"""
    if not all_matches:
        return {
            "total_tricor_products": original_tricorbraun_count,
            "products_with_matches": 0,
            "total_matches": 0,
            "match_rate": 0,
            "company_stats": {},
            "filtered_products": original_tricorbraun_count,
        }

    total_tricor_products = len(all_matches)
    products_with_matches = len(
        [m for m in all_matches.values() if m["similar_products"]]
    )
    total_matches = sum(len(m["similar_products"]) for m in all_matches.values())

    # Company breakdown
    company_stats = {}
    for matches in all_matches.values():
        for match in matches["similar_products"]:
            company = match["company"]
            if company not in company_stats:
                company_stats[company] = {
                    "count": 0,
                    "avg_similarity": 0,
                    "similarities": [],
                }
            company_stats[company]["count"] += 1
            company_stats[company]["similarities"].append(match["similarity"])

    # Calculate average similarities
    for company, stats in company_stats.items():
        stats["avg_similarity"] = sum(stats["similarities"]) / len(
            stats["similarities"]
        )

    return {
        "total_tricor_products": original_tricorbraun_count,
        "filtered_products": total_tricor_products,
        "products_with_matches": products_with_matches,
        "total_matches": total_matches,
        "match_rate": (
            products_with_matches / total_tricor_products
            if total_tricor_products > 0
            else 0
        ),
        "company_stats": company_stats,
    }


@st.cache_data
def find_similar_products_with_capacity_binning(
    companies_data, similarity_threshold=0.80, exclude_zero_price=True
):
    """Find similar products using capacity binning for improved performance"""
    if "TricorBraun" not in companies_data:
        return {}

    # Filter TricorBraun products
    tricorbraun_products = companies_data["TricorBraun"]
    tricorbraun_products = filter_products_by_price(
        tricorbraun_products, exclude_zero_price
    )

    # Group TricorBraun products by capacity
    tricorbraun_by_capacity = group_products_by_capacity(tricorbraun_products)

    # Group other companies' products by capacity
    other_companies_by_capacity = {}
    for company_name, products in companies_data.items():
        if company_name != "TricorBraun":
            filtered_products = filter_products_by_price(products, exclude_zero_price)
            other_companies_by_capacity[company_name] = group_products_by_capacity(
                filtered_products
            )

    all_matches = {}

    # Compare products within the same capacity bracket
    for capacity_bracket, tricor_products in tricorbraun_by_capacity.items():
        for tricor_product in tricor_products:
            product_name = tricor_product["name"]
            similar_products = []

            # Only compare with products in the same capacity bracket
            for (
                company_name,
                company_capacity_groups,
            ) in other_companies_by_capacity.items():
                if capacity_bracket in company_capacity_groups:
                    for other_product in company_capacity_groups[capacity_bracket]:
                        similarity_score = fuzzy_product_match(
                            tricor_product, other_product
                        )

                        if similarity_score >= similarity_threshold:
                            similar_products.append(
                                {
                                    "company": company_name,
                                    "product": other_product,
                                    "similarity": similarity_score,
                                    "capacity_diff_ml": abs(
                                        normalize_capacity_fuzzy(
                                            tricor_product["capacity"],
                                            tricor_product["unit"],
                                        )
                                        - normalize_capacity_fuzzy(
                                            other_product["capacity"],
                                            other_product["unit"],
                                        )
                                    ),
                                    "price_diff": abs(
                                        tricor_product["price"] - other_product["price"]
                                    ),
                                }
                            )

            if similar_products:
                all_matches[product_name] = {
                    "tricorbraun_product": tricor_product,
                    "similar_products": similar_products,
                    "capacity_bracket": capacity_bracket,
                }

    return all_matches
