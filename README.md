# MDI Intelligence Platform

Streamlit application for **Vietnam chemical import intelligence**: clean customs data (ETL), interactive analytics dashboards, multi-task model training, and batch prediction for **PMDI** and **TDI** product lines.

The repository root contains only the app entrypoint and run instructions. All business logic lives under `config/`, `services/`, and `ui/`.

---

## What it does

| Area | Description |
|------|-------------|
| **Data Analysis** | Load PMDI/TDI datasets, filter by sale channel, year, supplier, and material type; charts and shipment detail tables |
| **Train Model** | K-fold multi-task PyTorch training with preview, class rules, and progress in the UI |
| **Predict new** | Run PMDI or TDI production models to fill missing target columns on import data |

### Analysis tabs (sidebar → Analysis mode)

| Tab | Name | Highlights |
|-----|------|------------|
| 1 | **Market overview** | Yearly stacked volume (top 5 suppliers) + market-share line; supplier pie; monthly deep dive (all suppliers + selected supplier); top customers / suppliers |
| 2 | **Supplier deep dive** | Import volume by month/quarter; customer volume bar chart with hover; period filters |
| 3 | **Customer deep dive** | Placeholder — roadmap for customer comparison charts |

Analytics require **`BRAND NAME`**, **`SUPPLIER`**, and **`TYPE`** on the loaded dataset. If those columns are missing after upload, use **Predict new** first, then return to analysis.

---

## End-to-end workflow

```text
Raw customs CSV/Excel (Vietnamese headers)
              │
              ▼
     Data Analysis (ETL on load + dashboards)
              │
     ┌────────┴────────┐
     ▼                 ▼
Rows with targets   Rows missing BRAND NAME / SUPPLIER / TYPE
     │                 │
     │                 ▼
     │            Predict new (PMDI or TDI model)
     │                 │
     └────────┬────────┘
              ▼
     Train Model (labeled history)  ──►  models/…/model.pt
```

---

## Repository layout

```text
TRAIN_CUSTOM_MODEL/
├── app.py                 # Streamlit entrypoint
├── run_app.bat            # Windows launcher (venv + streamlit run)
├── requirements.txt
├── README.md
│
├── config/
│   └── settings.py        # Paths, HS codes, column names, ETL maps
│
├── services/              # All Python business logic
│   ├── data_process.py    # Core ETL pipeline
│   ├── etl_service.py     # ETL orchestration for the app
│   ├── analysis_service.py
│   ├── data_loader_service.py
│   ├── sale_channel_service.py
│   ├── ml_columns.py      # BRAND NAME / SUPPLIER / TYPE normalization
│   ├── train_service.py
│   ├── train_preview.py
│   ├── predict_service.py
│   ├── model_registry.py
│   ├── k_fold_muilti_task.py
│   └── utils.py
│
├── ui/                    # Streamlit pages and charts
│   ├── analysis.py
│   ├── analysis_data.py
│   ├── sidebar_analysis.py
│   ├── dashboard_market.py
│   ├── dashboard_supplier.py
│   ├── dashboard_customer.py
│   ├── chart_volume.py
│   ├── train_page.py
│   ├── predict_page.py
│   └── theme.py
│
├── data/                  # User datasets only (CSV / Excel)
├── app_config/            # ETL reference files (not user uploads)
│   ├── delete_description.csv
│   └── list_remove.csv
└── models/
    ├── MDI_production_material_predictor_muilti/   # PMDI
    └── TDI_production_material_predictor_muilti/    # TDI
```

---

## Requirements

- **Python** 3.10+ (3.12 recommended)
- **OS:** Windows, macOS, or Linux
- **Optional:** NVIDIA GPU for faster training

### Python packages (`requirements.txt`)

| Package | Role |
|---------|------|
| streamlit, plotly | Dashboard UI and charts |
| pandas, numpy, openpyxl | Data I/O and processing |
| torch, scikit-learn, joblib | Training and inference pipeline |

For GPU training, install a CUDA-enabled PyTorch build from [pytorch.org](https://pytorch.org) inside your virtual environment.

---

## Installation

```bash
cd TRAIN_CUSTOM_MODEL

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

---

## Run the app

**Windows (recommended):**

```bat
run_app.bat
```

**Manual:**

```bash
streamlit run app.py
```

Open **http://localhost:8501**.

The app starts on **Data Analysis** (`nav_page = insights`). Use the sidebar to switch analysis tab, dataset, uploads, **Train Model**, or **Predict new**.

### Sidebar (Data Analysis)

| Section | Purpose |
|---------|---------|
| **Analysis mode** | Market overview · Supplier deep dive · Customer deep dive |
| **Market / Supplier overview filters** | Year and supplier (when on the matching tab) |
| **Dataset & data source** | PMDI/TDI dataset, default file or upload |
| **Model tools** | Train Model · Predict new |

---

## Data and folders

### `data/` — user files

Place **CSV** or **Excel** import files here. The file picker excludes `app_config` reference files and temporary `_upload_*` names.

Default analysis files (configurable in `config/settings.py`):

| Mode | Default file |
|------|----------------|
| PMDI | `data/final_pmdi_2022_2025_30_may.csv` |
| TDI | `data/final_tdi_2022_2025_27_May.csv` |

Do **not** put `delete_description.csv` or `list_remove.csv` in `data/` — use `app_config/` (see below).

### `app_config/` — ETL reference only

| File | Role |
|------|------|
| `delete_description.csv` | Rows/descriptions removed during ETL |
| `list_remove.csv` | Extra words stripped from product descriptions |

### `models/` — trained weights

Each product line folder should contain:

| File | Description |
|------|-------------|
| `model.pt` | PyTorch weights |
| `pipeline_artifacts.joblib` | Encoders, transformers, training config |

Paths are defined in `config/settings.py` as `MDI_MODEL_DIR` and `TDI_MODEL_DIR`.

---

## Column standards

Targets are matched **by column name**, not column position.

| Canonical name | Aliases accepted |
|----------------|------------------|
| **BRAND NAME** | `label`, `brand_name`, predicted brand columns |
| **SUPPLIER** | `supplier`, `predicted_supplier` |
| **TYPE** | `type`, `material_type`, `predicted_type` |

### Raw / ETL input (typical)

Vietnamese headers are mapped via `COLUMN_RENAME_MAP` in settings, for example:

- `hs code` → `hs_code`
- `chung loai hang hoa xuat nhap` → `description`
- `luong` → `volume` (analytics also use `volume_ton`)

### Prediction input (minimum)

- `hs_code`, `description`, `saler`, `country_origin`

### Training input

- Labeled **`BRAND NAME`**, **`TYPE`**, **`SUPPLIER`** (plus feature columns used by `ML_COLUMN_CONFIG`)

---

## Configuration

Edit **`config/settings.py`** for:

- `ANALYSIS_DATASET_OPTIONS` / `ANALYSIS_HS_CODE_OPTIONS` (PMDI vs TDI)
- `PREDICTION_MODEL_OPTIONS` (model directories)
- `MDI_HS_CODES`, `TDI_HS_CODES`
- `SALE_CHANNEL_FILTER_OPTIONS` (Indent / Local)
- `ML_COLUMN_CONFIG`, training defaults (`DEFAULT_TRAIN_EPOCHS`, folds, etc.)
- `BLACKLIST_FILE`, `LIST_REMOVE_FILE` (under `app_config/`)

Use **Settings** in the app (if enabled in navigation) to view paths and clear the analytics session cache.

---

## Sale channel

**Sale channel** is derived from transport mode (`Phuong tien van tai`):

- **Indent** — sea transport labels configured in settings  
- **Local** — all other values  

Volume KPIs and charts respect the sale-channel filter on Market and Supplier tabs.

---

## Troubleshooting

| Issue | What to check |
|-------|----------------|
| `No module named 'torch'` | Activate `.venv` and `pip install -r requirements.txt` |
| Analytics says missing columns | Run **Predict new** or use a file that already has BRAND NAME, SUPPLIER, TYPE |
| Empty charts after upload | Click **Update data** in the sidebar; confirm `year` / `month` exist after ETL |
| Wrong ETL blacklist | Ensure `app_config/delete_description.csv` exists (not only a copy in `data/`) |
| Predict: model not found | Train or copy `model.pt` + `pipeline_artifacts.joblib` into the correct `models/…` folder |
| TDI vs PMDI mismatch | Match **Dataset** and **Predict** product line (PMDI/TDI) and HS code filters |

---

## Development notes

- **Entrypoint:** `app.py` only at repository root.  
- **Do not re-add** duplicate root copies of `data_process.py`, `k_fold_muilti_task.py`, or `utils.py` — import from `services.*`.  
- **UI** should stay thin; put new analytics in `services/` and charts in `ui/`.

---

## License

Internal / project use. Add license terms before external distribution.
