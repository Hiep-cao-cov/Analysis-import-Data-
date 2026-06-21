"""Central configuration for ETL, ML, and Streamlit app."""
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
# User datasets (merged uploads) — CSV/Excel only
DATA_DIR = PROJECT_ROOT / "data"
# App seed datasets (MDI/TDI defaults) — read by app, not listed in user pickers
DEFAULT_DATASETS_DIR = PROJECT_ROOT / "app_data"
# Temporary uploads / predict staging (_upload_*, _predict_*, …)
TEMP_DIR = PROJECT_ROOT / "temp"
# App reference files (blacklists, customer list, rules) — not user datasets
APP_CONFIG_DIR = PROJECT_ROOT / "app_config"

DATA_DIR.mkdir(exist_ok=True)
DEFAULT_DATASETS_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)
APP_CONFIG_DIR.mkdir(exist_ok=True)

# ── ETL ────────────────────────────────────────────────────────────────────
UNWANTED_COLS = [
    "Phan loai", "Chi cuc hai quan", "Cang xuat nhap", "Ten lo hang",
    "Tri gia", "Ty gia VND", "Tri gia VND", "Thue_XNK", " TS_TTDB ",
    "Thue_TTDB ", "TS_VAT", "Thue_VAT", "Phu_Thu", "MienThue",
    "Phuong tien van tai", "Ten phuong tien van tai", "Nuoc nhap khau",
    "Cang nuoc ngoai", "Phan loai trang thai",
]
ALLOWED_UNITS = ["kg", "tấn", "Thùng"]
MDI_HS_CODES = [
    "39093999", "39095000", "39093100", "39093190", "39093110",
]
TDI_HS_CODES = [
    "29291020",
    "29291010",
    "29291090",
]

# ── Upload ingest ────────────────────────────────────────────────────────────
# Sidebar uploads must match the ML prediction export schema (e.g. data/predictions_pmdi_etl.csv):
# English columns, BRAND NAME / SUPPLIER / TYPE, optional marked_for_delete (Yes rows are dropped).

# Filenames that must not live under data/ (kept in app_config/)
APP_REFERENCE_DATA_FILENAMES = frozenset({"customer_list.csv"})

CUSTOMER_LIST_FILE = APP_CONFIG_DIR / "customer_list.csv"

# ── Saler name standardization (ETL + ingest) ────────────────────────────────
# General rules apply to every saler (column `saler`). Company-specific overrides are optional.
#
# Pipeline:
#   1. Lowercase + fold accents (Công → cong)
#   2. Remove (... ) blocks when inner text contains a keyword (e.g. MST)
#   3. SALER_NAME_REGEX_REMOVE — strip legal suffixes / prefixes (general patterns)
#   4. Remove SALER_NAME_STRIP_CHARACTERS ( . ( ) , etc. ) + collapse spaces
#   5. Remove remaining punctuation → single spaces
#   6. Optional SALER_NAME_REGEX_MAP — pattern → canonical (first match wins)
#   7. Optional SALER_NAME_MAP — exact normalized key → canonical
#   8. Uppercase final saler label

# Step 2 — drop entire "(...)" segments when inner text contains any of these (case-insensitive)
# Example: "acme (MST: 0123456789) (VIETNAM)" → "acme (VIETNAM)" → later → "acme vietnam"
SALER_NAME_PAREN_REMOVE_KEYWORDS: list[str] = ["mst"]

# Step 3 — general legal-entity fragments (order matters; longest phrases first)
SALER_NAME_REGEX_REMOVE: list[str] = [
    # Vietnamese
    r"\bcong\s+ty\s+tnhh\b",
    r"\bcong\s+ty\s+cp\b",
    r"\bcong\s+ty\b",
    r"\bcty\b",
    r"\btnhh\b",
    # English / Singapore / international (longest phrases first)
    r"\bthe\b",
    r"\bprivate\s+limited\b",
    r"\bpri\s+vate\b",  # split OCR/typo for PRIVATE
    r"\bprivate\b",  # standalone, e.g. DOW CHEMICAL PACIFIC SINGAPORE PRIVATE
    r"\bpublic\s+limited\s+company\b",
    r"\bpte\.?\s*ltd\.?\b",
    r"\bpvt\.?\s*ltd\.?\b",
    r"\bco\.?\s*,?\s*ltd\.?\b",
    r"\bsdn\.?\s+bhd\.?\b",
    r"\bincorporated\b",
    r"\bcorporation\b",
    r"\blimited\b",
    r"\bcompany\b",
    r"\bpte\.?\b",
    r"\binc\.?\b",
    r"\bcorp\.?\b",
    r"\bllc\.?\b",
    r"\bplc\.?\b",
    r"\bgmbh\b",
    r"\bltd\.?\b",
    r"\bco\.?\b",
    # Jurisdiction boilerplate (e.g. Covestro Hong Kong legal entity lines)
    r"\bincorporated\s+in\s+(?:the\s+)?hong\s*kong\s*sar\b",
    r"\bin\s+(?:the\s+)?hong\s*kong\s*sar\b",
]

# Step 4 — strip these characters (each → space, then spaces collapsed to one)
SALER_NAME_STRIP_CHARACTERS = ".,()/-&"

# Step 6 — optional overrides only (leave empty to rely on general rules above)
SALER_NAME_REGEX_MAP: list[tuple[str, str]] = []

# Step 7 — optional exact alias overrides (canonical → extra spellings)
SALER_NAME_MAP: dict[str, list[str]] = {
    "COVESTRO HONG KONG": [
        "COVESTRO HONG KONG IN HONG KONG SAR",
    ],
}

# App seed dataset filenames (full files live in DEFAULT_DATASETS_DIR / app_data)
DEFAULT_DATASET_FILENAMES = {
    "MDI": "final_pmdi_2022_2025_30_may.csv",
    "TDI": "final_tdi_2022_2025_27_May.csv",
}

# Sidebar dataset modes (MDI / TDI)
ANALYSIS_DATASET_OPTIONS = {
    "MDI": DEFAULT_DATASET_FILENAMES["MDI"],
    "TDI": DEFAULT_DATASET_FILENAMES["TDI"],
}

ANALYSIS_HS_CODE_OPTIONS = {
    "MDI": MDI_HS_CODES,
    "PMDI": MDI_HS_CODES,
    "TDI": TDI_HS_CODES,
}

COLUMN_RENAME_MAP = {
    "nam": "year",
    "ngay": "date",
    "thang": "month",
    "quy": "quarter",
    "ma doanh nghiep": "customer_id",
    "doanh nghiep xuat nhap": "customer_name",
    "don vi doi tac": "saler",
    "nuoc xuat xu": "country_origin",
    "hs code": "hs_code",
    "chung loai hang hoa xuat nhap": "description",
    "luong": "volume",
    "ngoai te thanh toan": "currency",
    "dvt": "unit",
    "don gia": "unit_price",
    "ty gia usd": "exchange_rate_usd",
    "tri gia usd": "total_usd",
    "dieu kien giao hang": "incore_term",
    "dieu kien thanh toan": "payment_term",
    "ts_xnk": "tax_rate",
    "nuoc xuat khau": "country_export",
    "so to khai": "transaction",
}

# ── Sale channel (Sale_chanel) ─────────────────────────────────────────────
# Indent when phuong tien van tai matches INDENT_TRANSPORT_LABELS below.
# Local when transport does not match OR currency (ngoai te thanh toan / currency) is VND.
SALE_CHANNEL_COLUMN = "Sale_chanel"
SALE_CHANNEL_TRANSPORT_COLUMN = "phuong tien van tai"
SALE_CHANNEL_CURRENCY_COLUMNS = ("currency", "ngoai te thanh toan")
SALE_CHANNEL_INDENT_VALUE = "Indent"
SALE_CHANNEL_LOCAL_VALUE = "Local"
SALE_CHANNEL_LOCAL_CURRENCY_VALUES = frozenset({"vnd"})
INDENT_TRANSPORT_LABELS = [
    "Đường biển",
    "Đường biển (container)",
    "Đường biển (hàng rời, lỏng...)",
]
# Sale channel filter options (Tab 1 & Tab 2) — volumes use selected channel only
SALE_CHANNEL_FILTER_OPTIONS = [SALE_CHANNEL_INDENT_VALUE, SALE_CHANNEL_LOCAL_VALUE]

# ── type_sale (direct vs indirect via saler name) ───────────────────────────
TYPE_SALE_COLUMN = "type_sale"
TYPE_SALE_DIRECT = "DIRECT"
TYPE_SALE_INDIRECT = "INDIRECT"
TYPE_SALE_FILTER_ALL = "All"
TYPE_SALE_FILTER_OPTIONS = [TYPE_SALE_FILTER_ALL, TYPE_SALE_DIRECT, TYPE_SALE_INDIRECT]
TYPE_SALE_CHART_COLORS: dict[str, str] = {
    TYPE_SALE_DIRECT: "#10B981",
    TYPE_SALE_INDIRECT: "#F59E0B",
}
# Optional regex overrides per supplier label (default: escaped supplier name substring)
TYPE_SALE_SUPPLIER_PATTERNS: dict[str, str] = {
    "DOW": r"\bdow\b",
    "KMC": r"\bkmc\b",
}

# ── Supplier filter lists (Tab 1 & Tab 2 sidebar) ───────────────────────────
# Fixed order for selectbox. Suppliers not listed roll up to OTHER in charts/KPIs.
MDI_PMDI_SUPPLIER_LIST = [
    "COVESTRO",
    "TOSOH",
    "WANHUA",
    "BASF",
    "DOW",
    "KMC",
    "HUNTSMAN",
    "SABIC",
    "OTHER",
]

TDI_TDI_SUPPLIER_LIST = [
    "COVESTRO",
    "WANHUA",
    "BASF",
    "MCNS",
    "HANWHA",
    "SABIC",
    "OTHER",
]

CURATED_SUPPLIER_FILTER_RULES: dict[tuple[str, str], list[str]] = {
    ("MDI", "PMDI"): MDI_PMDI_SUPPLIER_LIST,
    ("TDI", "TDI"): TDI_TDI_SUPPLIER_LIST,
}

# MDI dataset + material type other than PMDI: show suppliers with avg yearly share > this %
SUPPLIER_MIN_AVG_MARKET_SHARE_PCT = 3.0

# Compare suppliers mode (Tab 2) — grouped bar colors by supplier name (uppercase keys)
SUPPLIER_COMPARE_BAR_COLORS: dict[str, str] = {
    "COVESTRO": "#3B82F6",   # blue
    "WANHUA": "#10B981",     # green
    "BASF": "#F97316",       # orange
    "MCNS": "#A855F7",       # purple
    "MCSN": "#A855F7",       # alias
    "HANWHA": "#9CA3AF",     # grey
    "TOSOH": "#EF4444",      # red
    "DOW": "#06B6D4",        # cyan
    "KMC": "#FACC15",        # yellow
    "HUNTSMAN": "#EC4899",   # pink
    "SABIC": "#84CC16",      # lime
    "OTHER": "#4B5563",      # dark grey
}

# Tab 2 single supplier — top customers chart: user-selectable N
SUPPLIER_TOP_CUSTOMER_OPTIONS = [5, 10]
SUPPLIER_TOP_CUSTOMERS_OTHERS_LABEL = "Others"

# Tab 3 — customer sidebar: top N buyers by volume in scoped filters
CUSTOMER_FILTER_TOP_N = 50

# Compare customers mode — distinct bar/line colors (no fixed brand mapping)
CUSTOMER_COMPARE_FALLBACK_COLORS = [
    "#3B82F6",
    "#10B981",
    "#F97316",
    "#A855F7",
    "#9CA3AF",
    "#EF4444",
    "#06B6D4",
    "#FACC15",
    "#EC4899",
    "#84CC16",
    "#14B8A6",
    "#818CF8",
]

# Extra colors for suppliers not in SUPPLIER_COMPARE_BAR_COLORS (e.g. MDI non-PMDI rule)
SUPPLIER_COMPARE_FALLBACK_COLORS = [
    "#14B8A6",
    "#F472B6",
    "#818CF8",
    "#FB7185",
    "#22D3EE",
    "#A78BFA",
    "#FBBF24",
]

# ── ML / analytics targets (same names for PMDI and TDI; match by name not column index) ──
COL_BRAND_NAME = "BRAND NAME"
COL_SUPPLIER = "SUPPLIER"
COL_TYPE = "TYPE"

# Rare / unknown brand bucket (training merge label + predict display name)
UNKNOWN_BRAND_LABEL = "UNKNOW"
LEGACY_UNKNOWN_BRAND_LABELS = frozenset({"OTHER_CHEMICAL", "UNKNOW", "UNKNOWN"})

# Softmax confidence for the argmax class (0–1), added by Predict new export
COL_BRAND_CONFIDENCE = "brand_confidence"
COL_TYPE_CONFIDENCE = "type_confidence"
COL_SUPPLIER_CONFIDENCE = "supplier_confidence"
PREDICT_CONFIDENCE_COLUMNS = (
    COL_BRAND_CONFIDENCE,
    COL_TYPE_CONFIDENCE,
    COL_SUPPLIER_CONFIDENCE,
)

