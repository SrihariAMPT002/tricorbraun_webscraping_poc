## Glass Product Competitor Analysis Dashboard

An interactive Streamlit dashboard for analyzing glass product data across Berlin Packaging, Cary Company, and TricorBraun.

### How to Run
- **Install**: `pip install -r requirements.txt`
- **Start**: `streamlit run dashboard.py`

### Navigation
- **Top Navigation**: Use the page selector to switch between `Homepage`, `Pricing Analysis`, `Assortment Analysis`, `Product Matching`, and `Chatbot`.
- **Sidebar (Global Filters)**:
  - **Companies**: Multiselect to include one or more companies. If none selected, all are applied.
  - **Market Segment**: Choose `All Segments` or a specific segment to filter all pages.

## Global vs Local Controls
- **Global Filters (Sidebar)** apply to all pages:
  - **Companies** and **Market Segment**.
- **Local Filters/Controls (Per Page)** are scoped to the page/section where they appear:
  - Search fields, capacity/price bin selectors, pagination controls, similarity threshold, etc.

## Page-by-Page Guide

### 🏠 Homepage
- **Purpose**: Quick overview per company plus cross-company comparison.
- **Local Controls**:
  - **Company selector (single)**: Choose one company to focus the overview section.
  - **Pricing Data section**:
    - **Capacity bins** and **Pricing bins**: Filter products with tiered pricing.
    - **Search**: Filter by SKU, product name, or quantity tier.
    - Shows up to 10 matching products; use search/filters to refine.
- **Sections**:
  - **Overview Metrics**: Total SKUs, Average Price (computed from non-zero prices), Category count, In-Stock count.
  - **Products Table**: AgGrid with sortable/filterable columns (SKU, Name, UOM, Capacity, Avg Price Per Item, Color, Material, Neck Finish, Shape, Stock).
  - **Pricing Data (per-product expanders)**: Quantity breaks table (Quantity, Unit, Unit Quantity, Price, Price/Each).
  - **Cross-Company Comparison**: Table summarizing SKUs, Avg Price (non-zero), Category count, Market Segments, and stock breakdowns.
- **Tips**:
  - AgGrid supports column sort, filter, and resize; use the header filters for quick slicing.

### 💰 Pricing Analysis
- **Purpose**: Understand pricing patterns by capacity, category, and case tiers.
- **Local Controls**: None (uses global filters). Each chart is inside an expander.
- **Charts**:
  - **Average Price by Capacity Range**: Grouped bar by company across capacity bins.
  - **Min–Max Price Range by Capacity Bin**: Lines with error bars showing min/max of Avg Price Per Item by bin and company.
  - **Average Price by Category and Company**: Grouped bar by category.
  - **Case Price Tiers (Min vs Max)**: Grouped bars for min/max case prices by capacity bin, faceted by company.
- **Notes**:
  - Prices are normalized per ml (capacity normalization) where applicable.
  - Plotly toolbar allows zoom, pan, and PNG download.

### 📦 Assortment Analysis
- **Purpose**: Coverage and distribution of SKUs across attributes and segments.
- **Local Controls**: None (uses global filters). Visuals are grouped in expanders.
- **Visuals & Tables**:
  - **SKU Count by Color**: Grouped bar by company.
  - **SKU Count by Material**: Grouped bar by company.
  - **SKU Count by Capacity Range**: Grouped bar by capacity bins.
  - **Capacity Range Summary**: Dataframe with SKU count, Avg Price, and Avg Capacity by bin and company.
  - **Market Segment Distribution**: Pie chart of segments.
  - **Competitor Comparison Matrix**: Heatmap of SKU count by company x market segment.
  - **Assortment Coverage Metrics**: Table of unique counts (Colors, Materials, Shapes, Market Segments, Capacity Ranges) per company.
  - **SKU's by Country of Manufacture**: Grouped bar (note: Berlin Packaging not available for this field).
  - **Stock Availability Details**: Counts by stock status category per company with grouped bar and table.
- **Notes**:
  - Capacity bins are derived using normalized ml values.
  - Use Plotly toolbar for image download if needed.

### 🔎 Product Matching
- **Purpose**: Find similar products to TricorBraun items; also run batch matching.
- **Tabs**:
  - **Per Item**:
    - **Local Filters**:
      - **Exclude Zero Price Products** (checkbox)
      - **Capacity bins** and **Pricing bins** (local, via bin pickers)
      - **Compare Companies** (multiselect; defaults to other companies)
      - **TricorBraun Product** (selectbox)
    - **Actions**:
      - **Find Similar Products** button computes similarity (≥ 85%).
      - **Filter Matched Products** search and **pagination** (items per page, page number).
    - **Output**:
      - Results grouped by company, with expanders showing details and diffs vs TricorBraun (capacity and price deltas).

  - **All Products (Batch)**:
    - **Local Controls**:
      - **Batch Similarity Threshold** slider (0.85–0.95)
      - **Exclude Zero Price Products** (checkbox)
    - **Actions**:
      - **Find All Similar Products (Batch)** triggers computation and caches results to disk.
      - **Download All Similar Products JSON** button (exports the full batch results).
    - **Output**:
      - **Summary metrics** (Total TricorBraun, Filtered Products, With Matches, Total Matches).
      - Results grouped by normalized capacity with **pagination** (groups per page, page number).

### 🤖 Chatbot
- **Purpose**: Ask data questions using the Hybrid RAG chatbot (Gemini + MongoDB + Pinecone).
- **Local Controls**:
  - **Query input** and **Send** button.
  - Sample usage cards are shown for inspiration.
- **Notes**:
  - Responses are cached in Redis per session for faster repeats.

## Downloads, Export, and Interactions
- **Chart exports**: Use the Plotly toolbar to save images (PNG) and control zoom/pan.
- **Batch matching export**: Use the `Download All Similar Products JSON` button on the Product Matching → All Products tab.
- **Tables**: AgGrid tables support sort/filter/resize in place; copy rows via standard selection + clipboard.

## Data Expectations
- Input JSON/processed data are loaded via `dashboard_utils.data_utils.load_data()` and filtered by global controls.
- Capacity normalization and binning are derived from product `capacity` + `unit` fields.

## Tech Stack
- **Streamlit** for UI and state, **Plotly** for charts, **Pandas** for data.
- **RapidFuzz** and custom logic for similarity; **Redis** optional cache for chatbot.

## Troubleshooting
- If you see “Only one company data selected” on Product Matching, select at least two companies in the sidebar.
- If a section shows no data, adjust global filters (company/segment) or local filters (bins/search/thresholds).
