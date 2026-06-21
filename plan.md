# MDI Data Analysis — Build Plan for LLM

This document is a **complete specification** for rebuilding the **MDI Data Analysis** Streamlit app from scratch. An LLM (or developer) should follow phases in order, implement modules as listed, and verify acceptance criteria at each phase.

**Reference implementation:** existing repo at project root. **User guide:** `README.md`.

---

## 1. Product summary

### Purpose

Standalone **Vietnam chemical import analytics** for **MDI** and **TDI** product lines. Users explore customs/import data through three dashboard tabs: Market, Supplier, and Customer.

### Out of scope

- ML training / prediction UI (separate app exports prediction CSVs)
- User authentication
- Database (CSV files only)

### Core user flows

1. **Use default file** — load pre-built seed CSV from `app_data/`, show dashboards.
2. **Upload new file** — ingest ML prediction export, preview in sidebar, dashboards show upload-only rows.
3. **Update data** — merge upload into seed dataset (append new months only).
4. **Customer short names** — map `customer_id` → display name via `app_config/customer_list.csv`.

---

## 2. Tech stack

| Layer | Choice |
|-------|--------|
| UI | Streamlit ≥ 1.32 |
| Charts | Plotly ≥ 5.18 |
| Data | pandas ≥ 2.0, numpy ≥ 1.24 |
| Excel | openpyxl ≥ 3.1 |
| Language | Python 3.10+ |

**Entry point:** `streamlit run app.py`

---

## 3. Directory layout (target)

```text
TRAIN_CUSTOM_MODEL/
├── app.py
├── run_app.bat
├── requirements.txt
├── plan.md                    # this file
├── README.md
├── config/
│   └── settings.py            # all business rules & paths
├── services/                  # no Streamlit imports in services/
│   ├── data_paths.py
│   ├── data_loader_service.py
│   ├── upload_ingest_service.py
│   ├── upload_preview.py
│   ├── upload_dataset_validation.py
│   ├── etl_service.py         # raw customs full ETL (optional path)
│   ├── data_process.py        # OrderDataPipeline
│   ├── ml_columns.py
│   ├── analysis_service.py
│   ├── sale_channel_service.py
│   ├── saler_name_service.py
│   ├── customer_name_service.py
│   ├── type_sale_service.py
│   ├── supplier_filter_service.py
│   ├── customer_filter_service.py
│   └── brand_labels.py
├── ui/                        # Streamlit only
│   ├── analysis.py            # router
│   ├── analysis_data.py       # load, merge, session df
│   ├── sidebar_analysis.py
│   ├── upload_preview_panel.py
│   ├── customer_list_panel.py
│   ├── dashboard_market.py    # Tab 1
│   ├── dashboard_supplier.py  # Tab 2
│   ├── dashboard_customer.py  # Tab 3
│   ├── chart_volume.py        # Plotly builders
│   ├── detail_table.py
│   └── theme.py
├── app_data/                  # seed CSVs (read-only defaults)
├── data/                      # sample / working files
├── app_config/
│   └── customer_list.csv      # customer_id → short_name
└── temp/                      # upload staging
```

---

## 4. Data model

### 4.1 Required ML columns (analytics gate)

Column **names** matter; position does not.

| Column | Role |
|--------|------|
| `BRAND NAME` | Product / brand label |
| `SUPPLIER` | Producer group |
| `TYPE` | Material type (PMDI, MMDI, …) |

Gate function: `has_ml_target_columns(df)` — all three must exist with ≥1 non-empty value each.

### 4.2 Standardized storage schema (~26 columns)

After `prepare_dataset_for_storage()`. Core fields:

`year`, `date`, `customer_id`, `customer_name`, `hs_code`, `description`, `saler`, `country_origin`, `unit`, `volume`, `unit_price`, `currency`, `exchange_rate_usd`, `total_usd`, `incore_term`, `payment_term`, `tax_rate`, `country_export`, `transaction`, `Sale_chanel`, `month`, `quarter`, `BRAND NAME`, `SUPPLIER`, `TYPE`, `type_sale`

Dropped on storage: `marked_for_delete`, `delete_reason`, confidence columns, `UNWANTED_COLS`, empty columns, internal `_preserve__*`.

### 4.3 Analysis frame (`dashboard_df`, ~34 columns)

Built by `prepare_dataframe_for_analysis()` = storage schema + derived columns:

| Derived | Source |
|---------|--------|
| `volume_ton` | `volume / 1000` |
| `supplier_raw`, `supplier_group` | from `SUPPLIER` |
| `type_clean`, `material_type` | from `TYPE` |
| `material` | from `BRAND NAME` |
| `month_num`, `quarter_num` | sort keys |

### 4.4 Upload file format

Must pass `is_standardized_dataset()`: ≥3 of `{hs_code, description, customer_id, total_usd}`.

Reference file: `data/predictions_pmdi_etl.csv`.

Optional: `marked_for_delete` (`Yes` → row removed on ingest).

---

## 5. Configuration (`config/settings.py`)

Centralize **all** business rules here.

### Paths

- `DATA_DIR` → `data/`
- `DEFAULT_DATASETS_DIR` → `app_data/`
- `TEMP_DIR` → `temp/`
- `APP_CONFIG_DIR` → `app_config/`
- `CUSTOMER_LIST_FILE` → `app_config/customer_list.csv`

### Product lines

- `MDI_HS_CODES` — list of HS strings
- `TDI_HS_CODES` — list of HS strings
- `DEFAULT_DATASET_FILENAMES` — MDI/TDI seed filenames
- `ANALYSIS_HS_CODE_OPTIONS` — map mode → HS list

### ETL

- `UNWANTED_COLS` — dropped on storage / raw ETL
- `ALLOWED_UNITS` — `kg`, `tấn`, `Thùng`
- `COLUMN_RENAME_MAP` — Vietnamese → English (raw ETL only)

### Sale channel

- `INDENT_TRANSPORT_LABELS` — sea transport strings (Vietnamese)
- **Indent:** transport matches label AND currency ≠ VND
- **Local:** otherwise
- Column: `Sale_chanel`

### Saler standardization

- `SALER_NAME_REGEX_REMOVE`, `SALER_NAME_STRIP_CHARACTERS`, `SALER_NAME_MAP`, etc.
- Output: uppercase canonical `saler`

### Supplier filters (Tab 1 & 2)

- `MDI_PMDI_SUPPLIER_LIST`, `TDI_TDI_SUPPLIER_LIST`
- `CURATED_SUPPLIER_FILTER_RULES`
- `SUPPLIER_COMPARE_BAR_COLORS`

### Customer filters (Tab 3)

- `CUSTOMER_FILTER_TOP_N` — default 50

### type_sale (Tab 2)

- `DIRECT` / `INDIRECT` from saler vs supplier match
- `TYPE_SALE_FILTER_OPTIONS`

---

## 6. Processing pipeline (critical)

Three layers — **same for default and upload** after layer 1.

```text
Layer 1: Ingest / load     → storage-shaped DataFrame
Layer 2: Storage prep      → prepare_dataset_for_storage()
Layer 3: Analysis prep     → prepare_dataframe_for_analysis() → dashboard_df
```

### 6.1 Path A — Use default file

```
default_dashboard_dataset_path(mode)     # app_data/*.csv
  → load_file()
  → prepare_dataframe_for_analysis()
      → apply_customer_short_names()      # app_config/customer_list.csv
      → apply_saler_name_standardization()
      → apply_type_sale_column()
      → prepare_analysis_frame()
      → add_volume_ton()
  → finish_dashboard_load()               # session + filter sync
```

**Disk file is never modified** on load.

### 6.2 Path B — Upload new file

```
ingest_upload_file()
  → validate is_standardized_dataset()
  → load_and_standardize(unit_filter="kg")
      → add_sale_channel_column()
      → apply_customer_short_names()
      → apply_saler_name_standardization()
      → apply_type_sale_column()
  → prepare_dataset_for_storage()
      → drop marked_for_delete=Yes
      → drop unknown brand rows
      → drop noise columns
  → prepare_dataframe_for_analysis()       # same as Path A layer 3
```

Preview: `upload_preview_panel.py` → collapsible sidebar summary + dry-run merge.

Merge (**Update data**):

```
ingest_upload_file() → load_storage_dataset(base)
→ reject overlapping year-month keys
→ append_only_new_rows()
→ save to app_data seed path
→ reload dashboard_df
```

### 6.3 Path C — Raw customs full ETL (optional, not sidebar upload)

```
run_etl() → OrderDataPipeline.run()
  → clean, units (tấn→kg), HS filter, rename columns
  → add_sale_channel, customer, saler, type_sale
```

Use when `is_raw_customs_export()` or `force_etl=True`.

### 6.4 Customer mapping rule (always)

On **every** load (default or upload):

1. Load `customer_list.csv` → `id_to_short`, `name_to_short`
2. Match row by `customer_id` (10-digit normalized) or normalized full `customer_name`
3. If match → replace `customer_name` with `short_name`
4. If no match → keep file value; show in sidebar **Customer short names** panel

---

## 7. Streamlit app architecture

### 7.1 Startup order (`app.py`)

```text
init_session_state()
migrate_storage_layout()
clear_temp_dir_on_startup()
sync_dataset_mode_from_sidebar()          # before widgets
apply_data_source_selection()             # BEFORE sidebar (needs dashboard_df)
render sidebar
render_analysis_page()                    # main area
```

**Critical:** `apply_data_source_selection()` runs **before** sidebar widgets so filters can read `dashboard_df`. `apply_pending_analysis_filter_sync()` runs at start of sidebar render **before** filter widgets.

### 7.2 Session state keys

| Key | Purpose |
|-----|---------|
| `dashboard_df` | Active analysis DataFrame |
| `dashboard_source` | Label / upload_preview:filename |
| `dashboard_ml_ready` | ML columns valid |
| `dashboard_msg` | Status banner |
| `analysis_mode` | MDI or TDI |
| `dash_source_mode` | Use default file \| Upload new file |
| `analysis_subtab` | market \| supplier \| customer |
| `analysis_sale_channel` | Indent \| Local |
| `analysis_year` | Filter year |
| `analysis_supplier` | Tab 1/2 supplier |
| `analysis_customer` | Tab 3 customer_id |
| `analysis_mtype` | Material type |
| `analysis_type_sale` | All \| DIRECT \| INDIRECT |
| `dash_sidebar_upload` | Uploaded file bytes |
| `dash_merge_requested` | Update data clicked |

### 7.3 Sidebar sections

1. **Analysis mode** — subtab selector (Market / Supplier / Customer)
2. **Dataset & data source** — MDI/TDI, default vs upload, file uploader, upload preview expander, Update data
3. **Tab-specific filters** — only show expander for active subtab:
   - Market: sale channel, year, supplier, material type
   - Supplier: + type_sale
   - Customer: sale channel, year, customer search selectbox, material type
4. **Customer short names** — unmapped customers, add to CSV

### 7.4 Filter sync rules

`queue_analysis_filter_sync(df, source_name)` when dataset loads:

- Pick sale channel with **most rows**
- Latest year
- Default material type (PMDI for MDI, TDI for TDI)
- First supplier in curated list
- First customer by **volume** in scope (not alphabetical)

Do **not** re-sync filters on every rerun if dataset signature unchanged.

---

## 8. Dashboard tabs (acceptance criteria)

### Tab 1 — Market (`dashboard_market.py`)

- Yearly volume & market share charts
- Monthly / quarterly drill-down
- Top customers & suppliers
- Filters: sale channel, year, supplier, material type
- Optional detail table (`show_detail_data`)

### Tab 2 — Supplier (`dashboard_supplier.py`)

- **Single supplier:** volume by period, type_sale pie, top customers, customer volume chart (yearly/quarterly/monthly)
- **Compare suppliers:** multi-supplier charts; detail table in compare mode (all years/quarters/months in scope)
- Filters: sale channel, year, supplier, material type, type_sale
- Supplier list from `resolve_supplier_filter_options()` (curated + data-driven)

### Tab 3 — Customer (`dashboard_customer.py`)

- **Single customer:** import volume, supplier mix, period comparison
- **Compare customers:** multi-customer mode
- Default customer = **top volume** in filtered scope (not first alphabetically)
- Customer selectbox: searchable (`filter_mode="contains"`)

### Shared chart module

`ui/chart_volume.py` — Plotly figures; accept scoped DataFrames; use `volume_ton`.

### Theme

`ui/theme.py` — CSS inject, KPI chips, headers, supplier/customer colors.

---

## 9. Key service contracts

Implement these functions with the signatures below.

### `services/ml_columns.py`

```python
def has_ml_target_columns(df) -> bool
def prepare_dataset_for_storage(df) -> pd.DataFrame
def normalize_ml_column_names(df) -> pd.DataFrame
```

### `services/customer_name_service.py`

```python
def apply_customer_short_names(df) -> pd.DataFrame
def find_unmapped_customers(df) -> pd.DataFrame
def append_customers_to_list(entries) -> tuple[int, int]
def reload_customer_short_name_map() -> dict
```

### `services/sale_channel_service.py`

```python
def add_sale_channel_column(df) -> pd.DataFrame
def filter_by_sale_channel(df, sale_channel) -> pd.DataFrame
```

### `services/upload_ingest_service.py`

```python
def ingest_upload_file(source, *, hs_codes) -> pd.DataFrame
def load_storage_dataset(source, *, hs_codes) -> pd.DataFrame
def classify_upload_format(preview) -> str
```

### `ui/analysis_data.py`

```python
def apply_data_source_selection(dataset_mode, hs_codes) -> None
def prepare_dataframe_for_analysis(df, *, hs_codes, path) -> pd.DataFrame
def finish_dashboard_load(df, source_name, *, message) -> None
def get_dataframe() -> pd.DataFrame | None
```

---

## 10. Implementation phases (for LLM)

### Phase 0 — Scaffold

- [ ] Create directory layout, `requirements.txt`, `config/settings.py` with paths + HS codes
- [ ] Empty `app.py` with page config + theme inject
- [ ] `services/data_paths.py` — path helpers, temp cleanup

### Phase 1 — Load & storage

- [ ] `data_loader_service.load_file()`, `is_standardized_dataset()`
- [ ] `ml_columns.py` — ML gate, storage prep, marked_for_delete filter
- [ ] `customer_name_service.py` — customer_list.csv lookup
- [ ] `saler_name_service.py`, `type_sale_service.py`, `sale_channel_service.py`
- [ ] `analysis_service.prepare_analysis_frame()`
- [ ] `analysis_data.prepare_dataframe_for_analysis()`, `load_default_data()`

**Verify:** Load seed CSV → `dashboard_df` with 34 columns; ML gate passes.

### Phase 2 — App shell & sidebar

- [ ] `sidebar_analysis.py` — dataset, subtab, shared filters
- [ ] `analysis_data.apply_data_source_selection()` default path
- [ ] `analysis.py` router
- [ ] Filter sync (`queue_analysis_filter_sync`, pending apply before widgets)

**Verify:** Default file loads; sale channel / year / supplier filters work.

### Phase 3 — Tab 1 Market

- [ ] `dashboard_market.py` + core charts in `chart_volume.py`
- [ ] `detail_table.py` with HS code as text (no `.000000`)

**Verify:** Charts render for MDI seed; filters slice data.

### Phase 4 — Tab 2 Supplier

- [ ] `supplier_filter_service.py`
- [ ] `dashboard_supplier.py` — single + compare modes
- [ ] Period scopes: yearly / quarterly / monthly
- [ ] Compare mode: detail table, no quarter/month sub-selectors in sidebar

**Verify:** Top salers use selected period; customer volume chart on yearly too.

### Phase 5 — Tab 3 Customer

- [ ] `customer_filter_service.py` — volume-ranked options, `default_customer_id()`
- [ ] `dashboard_customer.py` — single + compare
- [ ] Default customer = first with data in scope

**Verify:** No stale "3 KINGS" zero-data default.

### Phase 6 — Upload & merge

- [ ] `upload_ingest_service.py`, `upload_preview.py`, `upload_dataset_validation.py`
- [ ] `upload_preview_panel.py` — collapsible preview, dry-run merge
- [ ] Upload path in `apply_data_source_selection()`
- [ ] Merge with month overlap guard
- [ ] `finish_dashboard_load()` for upload preview (same analysis prep as default)

**Verify:** Upload `predictions_pmdi_etl.csv` → preview + dashboards; Update data blocked on overlapping months.

### Phase 7 — Customer list UI

- [ ] `customer_list_panel.py` — unmapped table, append to CSV, reload mapping

### Phase 8 — Raw ETL (optional)

- [ ] `data_process.OrderDataPipeline`, `etl_service.run_etl()`
- [ ] Only if supporting non-upload raw customs tooling

### Phase 9 — Polish

- [ ] `theme.py` — full styling, chip rows
- [ ] Settings page
- [ ] `README.md` documentation
- [ ] `run_app.bat`

---

## 11. Streamlit pitfalls (must handle)

1. **Widget order:** Never write `st.session_state[key]` for a filter **after** that widget renders in the same run.
2. **Filter sync:** Queue pending filter values; apply **before** any filter widget.
3. **Upload preview cache:** Do not call `finish_dashboard_load()` on every rerun when upload already loaded — only on first load or file change.
4. **Dataset signature:** `_filter_dataset_sig` prevents filter reset when user changes sale channel / supplier.
5. **MDI/TDI switch:** Clear upload state, reset filters, reload default seed.

---

## 12. Test data

| File | Use |
|------|-----|
| `app_data/final_pmdi_2022_2025_30_may.csv` | MDI default seed |
| `app_data/final_tdi_2022_2025_27_May.csv` | TDI default seed |
| `data/predictions_pmdi_etl.csv` | Upload format reference |
| `app_config/customer_list.csv` | ~1400+ customer mappings |

**Smoke tests:**

```bash
streamlit run app.py
# Default MDI → Tab 1/2/3 render
# Upload predictions_pmdi_etl.csv → Local rows visible; check Sale_chanel counts in preview
# Customer filter → top-volume default, not alphabetical
# Saler: COVESTRO (HONG KONG) LIMITED variants → COVESTRO HONG KONG
```

---

## 13. Non-goals / constraints

- Do not require ML app in same repo
- Do not use SQL or API backend
- Sidebar upload accepts **standardized ML export only** (not raw Vietnamese-only CSV)
- Row deletion for upload comes from **`marked_for_delete`** in prediction file (not in-app description blacklist)
- Seed file on disk not modified on dashboard load (in-memory enrichment only)

---

## 14. LLM execution instructions

When rebuilding from this plan:

1. Read `config/settings.py` patterns from Phase 0 before implementing services.
2. Implement **services before ui**; keep Streamlit out of `services/`.
3. Use **name-based column access** everywhere (never column index).
4. Match existing function names where possible for drop-in compatibility.
5. After each phase, run smoke tests in §12 before continuing.
6. Prefer **minimal diffs** — do not add auth, ORM, or extra abstractions not listed here.
7. Update `README.md` if pipeline behavior changes.

---

## 15. Glossary

| Term | Meaning |
|------|---------|
| **Seed file** | Default CSV in `app_data/` |
| **Storage prep** | Rows/columns ready to save CSV |
| **Analysis frame** | `dashboard_df` with derived columns for charts |
| **Indent** | Sea-import sale channel |
| **Local** | Non-indent or VND payment channel |
| **type_sale** | DIRECT (saler = supplier) vs INDIRECT |
| **Material type** | Filter on `TYPE` / `type_clean` (PMDI, MMDI, …) |

---

*End of build plan.*
