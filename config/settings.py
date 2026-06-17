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

# ── Row delete / filter rules (central config) ───────────────────────────────
# Used by ETL, Predict, and Analysis ingest. Edit rules here only.
#
# Upload Full ETL default: skip description blacklist (keep all rows).
# Uncheck sidebar checkbox to apply DESCRIPTION_BLACKLIST_TERMS below.
UPLOAD_SKIP_DESCRIPTION_BLACKLIST_DEFAULT = True
#
# Rule types:
#   1. description_blacklist — delete/mark row when description matches a term below
#   2. hs_code_filter       — keep only MDI_HS_CODES or TDI_HS_CODES (by product line)
#   3. unit_filter          — keep ALLOWED_UNITS only; tấn → kg conversion in ETL
#   4. missing_total_usd      — drop/mark rows with empty tri gia usd / total_usd
#   5. unknown_brand         — after predict: mark when BRAND NAME = UNKNOW and TYPE is empty
#
# Blacklist matching:
#   - Phrases (len > DESCRIPTION_BLACKLIST_SHORT_TERM_MAX_LEN): substring match
#   - Short terms (len <= max len) OR FORCE_WORD_BOUNDARY set: whole-word match only
#     (avoids false hits like "can" in CANGZHOU, "hạt" in "nhạt")
#
# Legacy CSV app_config/delete_description.csv is no longer loaded — edit lists below.

DESCRIPTION_BLACKLIST_SHORT_TERM_MAX_LEN = 4

# Always use whole-word match for these (even when longer than max len)
DESCRIPTION_BLACKLIST_FORCE_WORD_BOUNDARY = frozenset({
    "cast",
    "polyol",
})

# Core blacklist — descriptions containing these products/chemicals are excluded
DESCRIPTION_BLACKLIST_TERMS = [
    # Packaging / form (use phrases — do NOT add bare "can" or "hạt")
    "3kg/can",
    "5kg/bình",
    "9kg/thùng",
    "10kg/drum,",
    "20kg/drum,",
    "kg/can",
    "dạng hạt",
    "hạt nhựa",
    "Granules",
    "Powder",
    "powder",
    # Polymers / coatings / non-target materials
    "tpu",
    "TPU",
    "TPE",
    "ETPU",
    "(TPU)",
    "Thermoplastic",
    "thermoplastic",
    "THERMOPLASTIC",
    "nhiệt dẻo",
    "dẻo",
    "polyol",
    "baydur",
    "Desmopan",
    "DESMOPAN",
    "Vestagon",
    "Vesmody",
    "PROMUL",
    "HIRESOL",
    "AQUACE",
    "LOCTITE",
    "TAKENATE",
    "TAKELAC",
    "TOLONATE",
    "DM-70A",
    "42bd005",
    " MR-3860",
    "25Kg)",
    "9007-34-5",
    "51852-81-4",
    "28476-49-5",
    "24938-37-2",
    "85940-94-9",
    "26570-73-0",
    "190976-43-3",
    "28182-81-2",
    "2634-33-5",
    "141-78-6",
    "123-86-4",
    "107-21-1",
    "1330-20-7",
    # Paints / adhesives / leather / textiles
    "EPOXY",
    "acrylate",
    "DISPERSION",
    "spray coat",
    "Water based",
    "Water-based polyurethane",
    "Water Decoloring Agent",
    "WATER-BASE",
    "WATER BASE",
    "waterbase",
    "MELAMINE",
    "Formaldehyde",
    "Decoloring agent",
    "Polymethylolamine Dicyandiamide",
    "formamine",
    "dimethyl formamine",
    "Ethyl acetate",
    "Ethyl Acetate",
    "Acetone",
    "chống thấm",
    "chống thấm polyurethane",
    "chong tham",  # same rule when customs text drops Vietnamese accents
    "da thuộc",
    "da tổng hợp",
    "da nhân tạo",
    "GIẢ DA",
    "thuộc da",
    "phủ bảo vệ",
    "nganh det",
    "dán màng",
    "mực",
    "bao bì",
    "băng",
    "gioăng",
    "gioăng, ",
    "làm Jig",
    "khuôn",
    # Misc excluded
    "điện",
    "bột",
    "Bột",
    "pvc",
    "titanium",
    "mài",
    "mòn",
    "kích",
    "nở",
    "khử",
    "CATALYST",
    "3D,",
    "Bag",
]

# Extra terms by product line (merged on top of DESCRIPTION_BLACKLIST_TERMS)
DESCRIPTION_BLACKLIST_EXTRA_BY_PRODUCT: dict[str, list[str]] = {
    "MDI": [],
    "PMDI": [],
    "TDI": [],
}

# Deprecated — blacklist terms live in DESCRIPTION_BLACKLIST_* above

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
]

# Step 4 — strip these characters (each → space, then spaces collapsed to one)
SALER_NAME_STRIP_CHARACTERS = ".,()/-&"

# Step 6 — optional overrides only (leave empty to rely on general rules above)
SALER_NAME_REGEX_MAP: list[tuple[str, str]] = []

# Step 7 — optional exact alias overrides (canonical → extra spellings)
SALER_NAME_MAP: dict[str, list[str]] = {}

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
# Column "Phuong tien van tai" → Sale_chanel:
#   match any value below → Indent; otherwise → Local
SALE_CHANNEL_COLUMN = "Sale_chanel"
SALE_CHANNEL_TRANSPORT_COLUMN = "phuong tien van tai"
SALE_CHANNEL_INDENT_VALUE = "Indent"
SALE_CHANNEL_LOCAL_VALUE = "Local"
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

DEFAULT_RAW_DATASET = DATA_DIR / "raw_mdi_q1_2026.csv"
DEFAULT_INFERENCE_DATASET = DATA_DIR / "raw_mdi_q1_2026_dataset.csv"

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

# ── ML features + targets ──────────────────────────────────────────────────
ML_COLUMN_CONFIG = {
    "hs_code": "hs_code",
    "product_description": "description",
    "saler": "saler",
    "country_origin": "country_origin",
    "label": COL_BRAND_NAME,
    "type_col": COL_TYPE,
    "supplier_col": COL_SUPPLIER,
}
