# Glass Product Competitor Analysis Dashboard

A comprehensive Streamlit dashboard for analyzing glass product data from multiple competitors including Berlin Packaging, Cary Company, and TricorBraun.

## Features

### 🏠 Homepage
- Company selection dropdown
- Overview metrics (total SKUs, average price, categories, stock status)
- Product table with key attributes
- Cross-company comparison metrics

### 💰 Pricing Intelligence Dashboard
- Pricing tiers analysis with quantity breaks
- Normalized price per capacity (per ml/oz)
- Average price by category and closure type
- **Fuzzy product matching** using RapidFuzz and Pint for similarity scoring
- Interactive product comparison tool

### 📦 Assortment & Market KPI Dashboard
- SKU count by color, material, shape, and capacity range
- Market segment analysis
- Competitor comparison matrix
- Assortment coverage metrics

### 🤖 AI Assistant (Placeholder)
- Chatbot interface skeleton
- Sample usage examples
- Ready for integration with language models

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the dashboard:
```bash
streamlit run dashboard.py
```

## Data Structure

The dashboard expects JSON data files in the `demo_batch_data/` directory:
- `berlin_packing_all_data.json`
- `casy_all_data.json` 
- `tricorbraun_all_data.json`

If these files are not found, the dashboard will generate sample data for demonstration purposes.

## Key Technologies

- **Streamlit**: Web application framework
- **Plotly**: Interactive visualizations
- **Pandas**: Data manipulation
- **RapidFuzz**: Fuzzy string matching
- **Pint**: Unit conversion and normalization

## Fuzzy Matching Algorithm

The dashboard implements intelligent product similarity matching:

```python
def fuzzy_product_match(p1, p2):
    name_score = fuzz.token_sort_ratio(p1["name"], p2["name"]) / 100
    cap1 = normalize_capacity(p1["capacity"], p1["unit"])
    cap2 = normalize_capacity(p2["capacity"], p2["unit"])
    cap_score = 1 - min(abs(cap1 - cap2) / max(cap1, cap2), 1)
    price_score = 1 - min(abs(p1["price"] - p2["price"]) / max(p1["price"], p2["price"]), 1)
    return 0.5 * name_score + 0.3 * cap_score + 0.2 * price_score
```

This combines name similarity (50%), capacity similarity (30%), and price similarity (20%) for comprehensive product matching.

## Usage

1. **Homepage**: Select a company to view their product overview and metrics
2. **Pricing Intelligence**: Analyze pricing patterns and compare similar products
3. **Assortment KPIs**: Explore market segments and competitor positioning
4. **Chatbot**: Ask questions about the data (placeholder functionality)

## Future Enhancements

- Integration with real-time data sources
- Advanced AI chatbot with natural language processing
- Export functionality for reports
- User authentication and role-based access
- Real-time price monitoring and alerts
