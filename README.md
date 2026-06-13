# MDI Data Analysis

Standalone Streamlit app for **Vietnam chemical import analytics** — ETL, merge uploads, Market / Supplier / Customer dashboards.

## Run

**Windows:**

```bat
run_app.bat
```

**Manual:**

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501** (Streamlit default port).

---

## Train & Predict (separate app)

ML training and batch prediction live in a **self-contained folder** you can copy anywhere:

| Folder | Purpose |
|--------|---------|
| [`ml_app/`](ml_app/) | Train models + **Predict new** (PMDI / TDI) |

Copy the entire `ml_app/` folder to another machine or path, then run `run_app.bat` inside it. It does not depend on this repo root.

**Handoff between apps:** Predict in `ml_app` → download CSV → upload here → **Update data**. No shared session.

See [`ml_app/README.md`](ml_app/README.md) for ML setup.

---

## Repository layout

```text
TRAIN_CUSTOM_MODEL/          ← Data Analysis (this app)
├── app.py
├── run_app.bat
├── requirements.txt
├── config/settings.py
├── services/
├── ui/
├── data/                    # User uploads / merged datasets
├── app_data/                # Default PMDI/TDI seed CSVs
├── app_config/              # customer_list.csv, ETL reference files
└── temp/                    # _upload_* staging

ml_app/                      ← Portable Train & Predict (copy folder to run alone)
```

---

## Analysis tabs

| Tab | Highlights |
|-----|------------|
| **Market overview** | Yearly volume, market share, monthly deep dive, top customers/suppliers |
| **Supplier deep dive** | Volume by month/quarter, customer bar charts |
| **Customer deep dive** | Customer search, comparison charts |

Analytics require **`BRAND NAME`**, **`SUPPLIER`**, and **`TYPE`**. If missing, run **Predict new** in `ml_app`, download the CSV, then upload here.

---

## Data folders

| Folder | Purpose |
|--------|---------|
| `data/` | User CSV/Excel uploads |
| `app_data/` | Default seed datasets (PMDI/TDI) |
| `app_config/` | `customer_list.csv`, `list_remove.csv` (reference only) |
| `temp/` | Temporary upload staging |

---

## Requirements

- Python 3.10+ (3.12 recommended)
- Packages: streamlit, plotly, pandas, numpy, openpyxl (see `requirements.txt`)

---

## License

Internal / project use.
