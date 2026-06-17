import pandas as pd
import os
import numpy as np
import unicodedata
import re
# ==========================================
# 1. STANDALONE FLEXIBLE UTILITY FUNCTION
# ==========================================
def parse_string_to_float(value_str, decimal_digits=2):
    """
    Cleans a string representation of a number, handles thousands separators (commas),
    and converts it into a float rounded to a specified number of digits.
    
    Returns float('nan') on true missing/invalid text so pandas can track it as missing.
    """
    # Gracefully catch empty values, hyphens, or missing data (NaN)
    if pd.isna(value_str) or str(value_str).strip() in ['', '-', 'nan', 'NaN', 'None']:
        return float('nan')
    
    try:
        # Convert to string, strip hidden spaces, and eliminate thousands separator commas
        cleaned_str = str(value_str).replace(',', '').strip()
        
        # Cast to a base float and round to the precise number of requested decimal digits
        return round(float(cleaned_str), decimal_digits)
        
    except ValueError:
        # Catch unexpected text entries safely without crashing the script
        return float('nan')
# ==========================================
# 2. AUTOMATED PRODUCTION DATA PIPELINE
# ==========================================
class OrderDataPipeline:
    def __init__(
        self,
        cols_to_drop=None,
        rows_to_drop=None,
        target_units=None,
        numeric_parser=parse_string_to_float,
        default_decimals=2,
        *,
        blacklist_terms: list[str] | None = None,
        product_line: str | None = None,
        apply_description_blacklist: bool = True,
    ):
        self.cols_to_drop = [str(col).strip().lower() for col in cols_to_drop] if cols_to_drop is not None else ['cang xuat nhap', 
                                                                                                                 'phuong tien van tai', 'cang nuoc ngoai']
        self.target_units = [str(unit).strip().lower() for unit in target_units] if target_units is not None else ['kg', 'tấn', 'thùng']
        
        self.numeric_cols = ['luong', 'don gia', 'ty gia usd', 'tri gia usd']
        self.text_cols = ['ma doanh nghiep','hs code','doanh nghiep xuat nhap', 'don vi doi tac', 'nuoc xuat xu', 
                          'chung loai hang hoa xuat nhap', 'ngoai te thanh toan','so to khai']
        
        self.numeric_parser = numeric_parser
        self.default_decimals = default_decimals
        self.rows_to_drop = rows_to_drop
        self._product_line = product_line
        self._apply_description_blacklist = apply_description_blacklist
        self._blacklist_terms = self._load_blacklist_terms(blacklist_terms)

    def extend_blacklist(self, extra_terms: list[str]) -> None:
        """Append blacklist terms (prefer editing config/settings.py instead)."""
        from services.description_blacklist import normalize_description_text

        seen = {normalize_description_text(t) for t in self._blacklist_terms}
        for term in extra_terms:
            text = str(term).strip()
            normalized = normalize_description_text(text)
            if normalized and normalized not in seen:
                self._blacklist_terms.append(text)
                seen.add(normalized)

    def _snapshot_export_values(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep pre-ETL cell values so prediction export can match the input file."""
        from services.ml_columns import EXPORT_PRESERVE_PREFIX

        for col in df.columns:
            col_str = str(col)
            if col_str == "_predict_row_id" or col_str.startswith(EXPORT_PRESERVE_PREFIX):
                continue
            df[f"{EXPORT_PRESERVE_PREFIX}{col_str}"] = df[col].copy()
        return df
        
    def _normalize_text(self, text):
        """Aggressively normalize text for matching."""
        text = unicodedata.normalize('NFC', str(text).strip().lower())
        text = text.replace('\xa0', ' ')       # non-breaking space → regular space
        text = re.sub(r'\s+', ' ', text)       # collapse multiple spaces
        text = text.strip()
        return text
    
    def _load_blacklist_terms(self, blacklist_terms: list[str] | None):
        from services.description_blacklist import get_description_blacklist_terms

        if blacklist_terms is not None:
            return list(blacklist_terms)
        return get_description_blacklist_terms(product_line=self._product_line)

    def filter_by_description_blacklist(self, df):
        #print(f"🔍 DEBUG: blacklist_terms count = {len(self._blacklist_terms)}")
        #print(f"🔍 DEBUG: first 5 terms = {self._blacklist_terms[:5]}")
        #print(f"🔍 DEBUG: first 5 terms repr = {[repr(t) for t in self._blacklist_terms[:5]]}")

        if not self._blacklist_terms:
            print("[WARN] EMPTY blacklist - skipping!")
            return df

        col = 'chung loai hang hoa xuat nhap'
        if col not in df.columns:
            print(f"[WARN] Column '{col}' not found!")
            return df

        normalized_desc = df[col].astype(str).apply(self._normalize_text)
        from services.description_blacklist import mask_blacklisted_descriptions

        mask_to_delete = mask_blacklisted_descriptions(
            normalized_desc,
            self._blacklist_terms,
            product_line=self._product_line,
        )

        deleted_count = mask_to_delete.sum()
        df = df[~mask_to_delete].copy()

        print(f"[INFO] Blacklist Filter: {deleted_count:,} rows deleted, {len(df):,} rows remaining.")
        return df

    def load_data(self, file_path):
        print(f"[INFO] Loading file from: {file_path}")
        _, file_extension = os.path.splitext(file_path)
        dtype_map = {
            'ma doanh nghiep' :str,
            'hs code':str,
            'doanh nghiep xuat nhap':str, 
            'don vi doi tac':str, 
            'nuoc xuat xu':str,
            'chung loai hang hoa xuat nhap':str,
            'ngoai te thanh toan':str,
            'so to khai':str
        }
            
        
        if file_extension.lower() == '.csv':
            return pd.read_csv(file_path, low_memory=False)
        elif file_extension.lower() in ['.xlsx', '.xls']:
            return pd.read_excel(file_path)
        else:
            raise ValueError("❌ Unsupported file format!")

    def clean_text_values_to_lowercase(self, df):
        print("[INFO] Standardizing text values to lowercase...")
        for col in self.text_cols:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip().str.lower()
                if col == "hs code":
                    df[col] = df[col].str.replace(r"\.0$", "", regex=True)
        return df

    def clean_numeric_and_tax(self, df):
        print("[INFO] Auditing & parsing numeric fields using external function...")
        for col in self.numeric_cols:
            if col in df.columns:
                raw_strings = df[col].astype(str).str.replace(',', '', regex=False).str.strip()
                df[col] = df[col].apply(lambda x: self.numeric_parser(x, self.default_decimals))
        if 'ts_xnk' in df.columns:
            df['ts_xnk'] = df['ts_xnk'].apply(lambda x: self.numeric_parser(x, decimal_digits=4)).fillna(0.0)
        return df

    def process_dates(self, df):
        if 'ngay' in df.columns:
            df['ngay'] = pd.to_datetime(df['ngay'], errors='coerce')
            df['thang'] = df['ngay'].dt.strftime('%b').str.lower()
            df['quy'] = df['ngay'].dt.quarter.map(lambda x: f"q{int(x)}" if pd.notna(x) else None)
        return df

    def handle_missing_values(self, df):
        if 'tri gia usd' in df.columns:
            df = df.dropna(subset=['tri gia usd'])
        return df

    def standardize_units(self, df):
        """
        Step 8: Unit standardization.
        Converts 'tấn' (ton) rows to kg: volume × 1000, unit_price ÷ 1000, unit → kg.
        """
        if 'dvt' not in df.columns:
            return df

        df['dvt'] = df['dvt'].astype(str).str.strip().str.lower()
        clean_units = [str(u).strip().lower() for u in self.target_units]
        df = df[df['dvt'].isin(clean_units)].copy()

        is_ton = df['dvt'] == 'tấn'
        ton_count = int(is_ton.sum())
        if ton_count > 0:
            print("[INFO] Unit Conversion Report for 'tan':")
            print(f"   -> Ton rows converted to kg (volume × 1000, unit price ÷ 1000): {ton_count:,}")
            df.loc[is_ton, 'luong'] = df.loc[is_ton, 'luong'] * 1000
            df.loc[is_ton, 'don gia'] = df.loc[is_ton, 'don gia'] / 1000
            df.loc[is_ton, 'dvt'] = 'kg'

        return df

    def standardize_prices_to_usd(self, df):
        """
        Step 9: Keeps original currency intact. Creates a brand new column 
        'currency_standardized' and calculates USD prices for non-USD rows.
        """
        if 'ngoai te thanh toan' in df.columns and 'don gia' in df.columns and 'tri gia usd' in df.columns and 'luong' in df.columns:
            
            # 1. Create the NEW column by copying the original values exactly
            df['currency_standardized'] = df['ngoai te thanh toan']
            
            # 2. Identify rows where the source currency is NOT 'usd'
            non_usd_mask = (df['ngoai te thanh toan'] != 'usd') & (df['luong'] > 0)
            non_usd_count = non_usd_mask.sum()
            
            print(f"[INFO] Found {non_usd_count:,} non-USD rows. Keeping original markers and calculating standard USD prices...")
            
            if non_usd_count > 0:
                # 3. Calculate new unit price: tri gia usd / luong
                calculated_prices = df.loc[non_usd_mask, 'tri gia usd'] / df.loc[non_usd_mask, 'luong']
                df.loc[non_usd_mask, 'don gia'] = calculated_prices.round(self.default_decimals)
                
                # 4. Overwrite ONLY the NEW column to 'usd' for these rows
                df.loc[non_usd_mask, 'currency_standardized'] = 'usd'
                
            print("[INFO] Currency pricing and double-column tracking setup complete!")
        return df

    def run(self, file_path):
        """Sequential Pipeline Execution Engine."""
        df = self.load_data(file_path)
        
        df = df.loc[:, df.columns.notna()]
        df = df.loc[:, ~df.columns.astype(str).str.contains('^Unnamed')]
        
        df.columns = df.columns.astype(str).str.strip().str.lower()
        print("[INFO] Column names successfully standardized to lowercase.")

        from services.sale_channel_service import add_sale_channel_column

        df = add_sale_channel_column(df)

        existing_cols_to_drop = [col for col in self.cols_to_drop if col in df.columns]
        df = df.drop(columns=existing_cols_to_drop)

        if "_predict_row_id" not in df.columns:
            df["_predict_row_id"] = np.arange(len(df), dtype=np.int64)
        df = self._snapshot_export_values(df)

        df = self.clean_text_values_to_lowercase(df)
        df = self.clean_numeric_and_tax(df)
        df = self.process_dates(df)
        df = self.handle_missing_values(df)
        if self._apply_description_blacklist:
            df = self.filter_by_description_blacklist(df)
        df = self.standardize_units(df)
        df = self.standardize_prices_to_usd(df) # Creates the new column here
        
        df = df.reset_index(drop=True)
        print(f"[INFO] Pipeline Complete! Final Shape: {df.shape[0]:,} rows, {df.shape[1]} columns.\n")
        return df


def filter_by_hs_code(input_df, target_hs_codes):
    """
    Filters the dataframe to retain only rows matching a specific list of HS Codes.
    Completely handles string conversion and formatting for safe evaluation.
    """
    # 1. Create a safe copy of the data
    df_filtered = input_df.copy()
    
    # 2. Extract the actual column name used in your current dataframe
    hs_col = 'hs_code' if 'hs_code' in df_filtered.columns else 'hs code'
    
    if hs_col not in df_filtered.columns:
        raise KeyError(f"❌ Could not find an HS Code column. Available columns are: {list(df_filtered.columns)}")
    
    # 3. Standardize the dataframe data column (using pandas .str engine)
    df_filtered[hs_col] = df_filtered[hs_col].astype(str).str.replace('.', '', regex=False).str.strip()
    
    # 4. FIXED: Standardize your input target list using native python string methods
    clean_targets = [str(code).replace('.', '').strip() for code in target_hs_codes]
    
    # 5. Filter using .isin()
    df_filtered = df_filtered[df_filtered[hs_col].isin(clean_targets)].copy()
    
    # 6. Calculate statistics
    original_count = len(input_df)
    remaining_count = len(df_filtered)
    removed_count = original_count - remaining_count
    
    print("[INFO] HS Code Filtering Complete:")
    print(f"   -> Original records: {original_count:,}")
    print(f"   -> Retained records matching targets: {remaining_count:,}")
    print(f"   -> Removed records (unnecessary materials): {removed_count:,}")
    
    # 7. Reset index cleanly from 0
    return df_filtered.reset_index(drop=True)

def rename_dataframe_columns(input_df, mapping_dict):
    """
    Renames the columns of a dataframe using a provided dictionary.
    Ensures that the lookup keys are processed in lowercase to match the pipeline.
    
    Input:
        - input_df: The cleaned DataFrame (e.g., df_ready)
        - mapping_dict: A dictionary of {'old_lowercase_name': 'new_easy_name'}
    Output:
        - A new DataFrame with clean, simplified column names.
    """
    # 1. Create a clean copy of the dataframe
    df_renamed = input_df.copy()
    
    # 2. Convert dictionary keys to lowercase just in case of human error when typing the dict
    clean_mapping = {str(k).strip().lower(): str(v).strip() for k, v in mapping_dict.items()}
    
    # 3. Apply the mapping translation
    df_renamed = df_renamed.rename(columns=clean_mapping)
    
    print("[INFO] Column names successfully translated to your easy names!")
    return df_renamed