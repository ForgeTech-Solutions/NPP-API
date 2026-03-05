"""Excel file parser for nomenclature import."""
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import openpyxl
import pandas as pd
from io import BytesIO

logger = logging.getLogger("nomenclature.parser")

# Sheet name to category mapping
SHEET_CATEGORY_MAP = {
    "nomenclature": "NOMENCLATURE",
    "non renouvelé": "NON_RENOUVELE",
    "non renouvelés": "NON_RENOUVELE",
    "non renouveles": "NON_RENOUVELE",
    "retrait": "RETRAIT",
    "retraits": "RETRAIT",
}

# Type normalization
TYPE_NORMALIZATION = {
    "GÉ": "GE", "Gé": "GE", "gé": "GE", "ge": "GE",
    "RE": "RE", "Re": "RE", "re": "RE",
    "BIO": "BIO", "Bio": "BIO", "bio": "BIO",
}

# Pays normalization (accent removal)
PAYS_NORMALIZATION = {
    "ALGÉRIE": "ALGERIE", "Algérie": "ALGERIE", "algerie": "ALGERIE", "Algerie": "ALGERIE",
    "ÉTATS-UNIS": "ETATS-UNIS", "États-Unis": "ETATS-UNIS",
}


def detect_category_from_sheet_name(sheet_name: str) -> str:
    """Detect the category from sheet name."""
    name_lower = sheet_name.strip().lower()
    for key, cat in SHEET_CATEGORY_MAP.items():
        if key in name_lower:
            return cat
    return "NOMENCLATURE"


def normalize_type_value(value: str) -> str:
    """Normalize type_medicament value."""
    if not value:
        return "ND"
    v = value.strip()
    return TYPE_NORMALIZATION.get(v, v.upper())


def normalize_pays_value(value: str) -> str:
    """Normalize pays_laboratoire value."""
    if not value:
        return "ND"
    v = value.strip()
    return PAYS_NORMALIZATION.get(v, v.upper())


def get_available_sheets(file_content: bytes) -> List[Dict[str, Any]]:
    """
    Get list of available sheets in Excel file with metadata.
    """
    try:
        excel_file = pd.ExcelFile(BytesIO(file_content))
        sheets = []
        
        for sheet_name in excel_file.sheet_names:
            try:
                header_row = detect_header_row(file_content, sheet_name)
                df_full = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name, header=header_row)
                sheet_type = detect_sheet_type(df_full)
                category = detect_category_from_sheet_name(sheet_name)
                
                sheets.append({
                    "name": sheet_name,
                    "rows": len(df_full),
                    "detected_type": sheet_type,
                    "detected_category": category,
                    "columns": [str(c) for c in df_full.columns.tolist()] if header_row is not None else []
                })
            except Exception as e:
                sheets.append({
                    "name": sheet_name,
                    "rows": 0,
                    "detected_type": "error",
                    "detected_category": "unknown",
                    "columns": [],
                    "error": str(e)
                })
        
        return sheets
    except Exception as e:
        raise ValueError(f"Error reading Excel file: {str(e)}")


def detect_header_row(file_content: bytes, sheet_name: str) -> Optional[int]:
    """
    Detect which row contains the header in an Excel sheet.
    """
    try:
        df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name, header=None, nrows=25)
        key_columns = ['N', 'CODE', 'DCI', 'DENOMINATION COMMUNE INTERNATIONALE', 'NOM DE MARQUE']
        
        for idx, row in df.iterrows():
            row_values = [str(val).strip().upper() for val in row if pd.notna(val)]
            matches = sum(1 for key in key_columns if any(key in val for val in row_values))
            if matches >= 2:
                return idx
        
        return 0
    except Exception:
        return 0


def detect_sheet_type(df: pd.DataFrame) -> str:
    """Detect the type of data in a sheet based on column names."""
    columns_str = ' '.join([str(col).upper() for col in df.columns])
    medicament_indicators = ['CODE', 'DCI', 'DENOMINATION COMMUNE', 'NOM DE MARQUE', 'MARQUE']
    matches = sum(1 for indicator in medicament_indicators if indicator in columns_str)
    
    if matches >= 2:
        return "medicaments"
    return "unknown"


def parse_excel_file(file_content: bytes, sheet_name: str = None) -> List[Dict[str, Any]]:
    """
    Parse Excel file and extract medicament data from a specific sheet.
    Handles all 3 sheet types: Nomenclature, Non Renouvelés, Retraits.
    """
    try:
        if sheet_name is None:
            excel_file = pd.ExcelFile(BytesIO(file_content))
            sheet_name = excel_file.sheet_names[0]
        
        # Detect category from sheet name
        category = detect_category_from_sheet_name(sheet_name)
        logger.info(f"Parsing sheet '{sheet_name}' as category '{category}'")
        
        header_row = detect_header_row(file_content, sheet_name)
        df = pd.read_excel(BytesIO(file_content), sheet_name=sheet_name, header=header_row)
        df.columns = df.columns.str.strip()
        
        # Flexible column mapping with multiple possible names
        column_mapping = {}
        for col in df.columns:
            col_upper = str(col).upper().strip()
            
            if col_upper in ['N', 'N°']:
                column_mapping[col] = 'n'
            elif 'ENREGISTREMENT' in col_upper and 'N°' in col_upper:
                column_mapping[col] = 'num_enregistrement'
            elif col_upper in ['CODE', 'CODE PRODUIT']:
                column_mapping[col] = 'code'
            elif 'DCI' in col_upper or 'DENOMINATION COMMUNE' in col_upper:
                column_mapping[col] = 'dci'
            elif 'NOM' in col_upper and 'MARQUE' in col_upper:
                column_mapping[col] = 'nom_marque'
            elif col_upper in ['FORME', 'FORME PHARMACEUTIQUE']:
                column_mapping[col] = 'forme'
            elif col_upper in ['DOSAGE', 'TITRE']:
                column_mapping[col] = 'dosage'
            elif 'CONDITIONNEMENT' in col_upper or 'PRÉSENTATION' in col_upper or col_upper == 'COND':
                column_mapping[col] = 'conditionnement'
            elif col_upper == 'LISTE':
                column_mapping[col] = 'liste'
            elif col_upper == 'P1':
                column_mapping[col] = 'p1'
            elif col_upper == 'P2':
                column_mapping[col] = 'p2'
            elif col_upper in ['OBS', 'OBSERVATION', 'OBSERVATIONS']:
                column_mapping[col] = 'obs'
            elif 'LABORATOIRE' in col_upper and 'PAYS' not in col_upper:
                column_mapping[col] = 'laboratoire'
            elif 'PAYS' in col_upper and 'LABORATOIRE' in col_upper:
                column_mapping[col] = 'pays_laboratoire'
            elif 'DATE' in col_upper and 'INITIAL' in col_upper:
                column_mapping[col] = 'date_enregistrement_initial'
            elif 'DATE' in col_upper and ('FINAL' in col_upper or 'VALIDITÉ' in col_upper):
                column_mapping[col] = 'date_enregistrement_final'
            elif 'DATE' in col_upper and 'RETRAIT' in col_upper:
                column_mapping[col] = 'date_retrait'
            elif 'MOTIF' in col_upper and 'RETRAIT' in col_upper:
                column_mapping[col] = 'motif_retrait'
            elif col_upper in ['TYPE', 'TYPE MEDICAMENT']:
                column_mapping[col] = 'type_medicament'
            elif col_upper == 'STATUT' or col_upper == 'ÉTAT':
                column_mapping[col] = 'statut'
            elif ('STABILITE' in col_upper or 'STABILITÉ' in col_upper) and ('DUREE' in col_upper or 'DURÉE' in col_upper):
                column_mapping[col] = 'duree_stabilite'
        
        # Rename columns
        df = df.rename(columns=column_mapping)
        df = df.dropna(how='all')
        
        records = []
        mapped_fields = set(column_mapping.values())
        
        for _, row in df.iterrows():
            record = {}
            
            for db_field in mapped_fields:
                value = row.get(db_field)
                
                if pd.isna(value):
                    record[db_field] = None
                elif db_field in ['date_enregistrement_initial', 'date_enregistrement_final', 'date_retrait']:
                    if isinstance(value, (datetime, pd.Timestamp)):
                        record[db_field] = value.date()
                    else:
                        # Try to parse string dates
                        try:
                            parsed = pd.to_datetime(value, errors='coerce')
                            record[db_field] = parsed.date() if pd.notna(parsed) else None
                        except Exception:
                            record[db_field] = None
                elif db_field == 'n':
                    try:
                        record[db_field] = int(value) if value is not None else None
                    except (ValueError, TypeError):
                        record[db_field] = None
                else:
                    record[db_field] = str(value).strip() if value is not None else None
            
            # Set category from sheet name
            record['categorie'] = category
            
            # Normalize type_medicament
            if record.get('type_medicament'):
                record['type_medicament'] = normalize_type_value(record['type_medicament'])
            
            # Normalize pays_laboratoire
            if record.get('pays_laboratoire'):
                record['pays_laboratoire'] = normalize_pays_value(record['pays_laboratoire'])
            
            records.append(record)
        
        logger.info(f"Parsed {len(records)} records from sheet '{sheet_name}' (category: {category})")
        return records
        
    except Exception as e:
        raise ValueError(f"Error parsing Excel file: {str(e)}")


def validate_medicament_record(record: Dict[str, Any]) -> tuple[bool, List[str]]:
    """
    Validate a medicament record.
    """
    errors = []
    
    # Only code is truly required
    if not record.get('code'):
        errors.append("Missing required field: code")
        return False, errors
    
    # Set default "ND" for missing required string fields
    default_fields = [
        'dci', 'nom_marque', 'forme', 'dosage',
        'conditionnement', 'laboratoire', 'pays_laboratoire',
        'type_medicament', 'statut'
    ]
    
    for field in default_fields:
        if not record.get(field):
            record[field] = 'ND'
    
    # Ensure categorie is set
    if not record.get('categorie'):
        record['categorie'] = 'NOMENCLATURE'
    
    # Field length validation
    max_lengths = {
        'code': 100,
        'num_enregistrement': 255,
        'liste': 100,
        'type_medicament': 100,
        'statut': 50,
        'pays_laboratoire': 255,
        'categorie': 50,
    }
    
    for field, max_length in max_lengths.items():
        value = record.get(field)
        if value and len(str(value)) > max_length:
            errors.append(f"Field {field} exceeds maximum length of {max_length}")
    
    is_valid = len(errors) == 0
    return is_valid, errors
