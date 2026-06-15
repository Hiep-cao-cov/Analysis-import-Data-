# MDI Data Analysis

Standalone **Streamlit** app for Vietnam chemical import analytics — **MDI** and **TDI** product lines, ETL on upload, merge into working datasets, and Market / Supplier / Customer dashboards.

## Quick start

**Windows**

```bat
run_app.bat
```

**Manual**

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501**.

---

## What the app does

| Area | Description |
|------|-------------|
| **Market overview** | Yearly volume & market share, monthly deep dive, top customers/suppliers |
| **Supplier overview** | Supplier volume by period, direct vs indirect sales, customer mix |
| **Customer overview** | Customer search, period comparison, supplier mix charts |
| **ETL on upload** | Raw customs or prediction CSVs → standardized columns (kg, USD, month/quarter, short names, saler, `type_sale`, `Sale_chanel`) |
| **Merge** | Append-only merge into `data/` with duplicate detection |

All chart logic uses the same pipeline whether you load the **default seed file** or **preview an upload** — only the row set changes.

---

## Sidebar: dataset & data source

### Dataset (MDI / TDI)

- **MDI** — seed file `final_pmdi_2022_2025_30_may.csv`, HS codes for polyisocyanates / MDI family  
- **TDI** — seed file `final_tdi_2022_2025_27_May.csv`, HS codes for TDI  

The app loads from **`data/`** if that file exists (after a merge); otherwise from **`app_data/`** (read-only seed).

Switching **MDI ↔ TDI** clears any in-progress upload, resets to **Use default file**, and loads the default dataset for the new selection.

### Data source

| Mode | Behavior |
|------|----------|
| **Use default file** | Load seed or merged CSV from `data/` / `app_data/` |
| **Upload new file** | Full ETL on the file → **dashboards show upload rows only** → optional **Update data** to merge into `data/` |

**Upload workflow**

1. Select **Upload new file** and choose CSV or Excel.  
2. Sidebar runs ETL and shows a preview (row count, ML columns, dry-run merge stats).  
3. Dashboards update immediately with **this file only** (no merge yet).  
4. Optionally **Download processed file** to review ETL output.  
5. Click **Update data** to append new rows into `data/final_pmdi_....csv` or `data/final_tdi_....csv` (duplicates skipped).  

**MDI / TDI upload rules**

- Upload an **MDI** file (e.g. `predictions_pmdi_*.csv`) only when **Dataset: MDI** is selected.  
- Upload a **TDI** file only when **Dataset: TDI** is selected.  
- Mismatch is detected from filename and HS codes before merge.  

Seed files in `app_data/` are **never** overwritten; merges write only under `data/`.

---

## Required columns for analytics

Dashboards need these column **names** (position does not matter):

- **BRAND NAME**
- **SUPPLIER**
- **TYPE**

Files with Vietnamese customs headers plus these columns (e.g. `predictions_pmdi_4_5_2026.csv`) run through **full ETL** on upload.

If columns are missing, prepare data in an external **Train & Predict** tool, download the prediction CSV, then upload here. This repo is **Import Analytics only** — no ML training UI is bundled here.

---

## Repository layout

```text
TRAIN_CUSTOM_MODEL/
├── app.py                 # Streamlit entry point
├── run_app.bat
├── requirements.txt
├── config/
│   └── settings.py        # HS codes, blacklists, saler rules, supplier lists, paths
├── services/              # ETL, ingest, analysis, upload validation
├── ui/                    # Dashboards, sidebar, charts, theme
├── data/                  # Merged working datasets (user updates via Update data)
├── app_data/              # Default MDI/TDI seed CSVs (not modified by the app)
├── app_config/
│   └── customer_list.csv  # Customer short names (created/edited in sidebar panel)
└── temp/                  # Staging for uploads (_preview_*, _upload_*)
```

---

## Configuration

| Location | Purpose |
|----------|---------|
| `config/settings.py` | ETL rules, description blacklist, MDI/TDI HS codes, `type_sale` supplier lists, saler standardization, chart defaults |
| `app_config/customer_list.csv` | Map `customer_id` / company name → short name for charts and filters |

Description blacklist and row-filter rules are defined in **`config/settings.py`** (not separate CSV files).

---

## ETL highlights (on upload)

- Rename Vietnamese columns → English (`hs_code`, `customer_name`, `volume`, `total_usd`, …)  
- Convert tấn → kg, normalize units  
- Derive **month**, **quarter**, **Sale_chanel** (Indent / Local)  
- Apply **customer short names** from `customer_list.csv`  
- Standardize **saler** names (regex rules in settings)  
- Set **type_sale** (`DIRECT` / `INDIRECT`) from saler vs supplier list  
- Filter HS codes by MDI or TDI product line  

---

## Requirements

- Python **3.10+** (3.12 recommended)  
- See `requirements.txt`: streamlit, pandas, numpy, plotly, openpyxl  

---

## License

Internal / project use.
