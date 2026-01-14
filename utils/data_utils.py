import pandas as pd
import unicodedata
import re
import os

# =================================================
# CONFIGURATION DES CHEMINS (SOURCE DE VÉRITÉ)
# =================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "..", "data", "csv_fusionne.csv")


# =================================================
# NORMALISATION TEXTE
# =================================================

def normalize_text(value) -> str:
    if not isinstance(value, str):
        value = str(value)

    value = value.strip()
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower()
    value = re.sub(r"\s+", " ", value)

    return value


# =================================================
# PARSING DES DATES
# =================================================

def parse_start_from_datetime(text):
    if not isinstance(text, str) or not text.strip():
        return pd.NaT

    parts = re.split(r"[–\-—to]+", text)
    try:
        return pd.to_datetime(parts[0], errors="coerce", dayfirst=True)
    except Exception:
        return pd.NaT


# =================================================
# CHARGEMENT DES ÉVÉNEMENTS
# =================================================

def load_events() -> pd.DataFrame:
    print("📂 CSV utilisé :", CSV_PATH)
    print("📁 Fichier existe ?", os.path.exists(CSV_PATH))

    if not os.path.exists(CSV_PATH):
        print("❌ CSV introuvable")
        return pd.DataFrame()

    try:
        df = pd.read_csv(CSV_PATH)
    except Exception as e:
        print("❌ Erreur lecture CSV :", e)
        return pd.DataFrame()

    required_columns = ["Category", "City", "EventName", "Description"]
    if not all(col in df.columns for col in required_columns):
        print("❌ Colonnes requises manquantes")
        return pd.DataFrame()

    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    df["DateTime_start"] = df["DateTime"].apply(parse_start_from_datetime)

    if "DateTime_end" in df.columns:
        mask = df["DateTime_start"].isna() & df["DateTime_end"].notna()
        df.loc[mask, "DateTime_start"] = pd.to_datetime(
            df.loc[mask, "DateTime_end"], errors="coerce"
        )

    def fallback_year(row):
        year = row.get("Année_start") or row.get("Annee_start")
        if pd.notna(year):
            try:
                return pd.Timestamp(year=int(year), month=1, day=1)
            except Exception:
                return pd.NaT
        return pd.NaT

    df["DateTime_start"] = df["DateTime_start"].fillna(
        df.apply(fallback_year, axis=1)
    )

    for col in ["Category", "City", "EventName", "Description"]:
        df[col] = df[col].fillna("").astype(str)

    return df


# =================================================
# FILTRAGE PAR CATÉGORIE / INTÉRÊTS
# =================================================

def filter_by_category(df: pd.DataFrame, interests_param: str) -> pd.DataFrame:
    if df.empty or not interests_param or "Category" not in df.columns:
        return df

    interests = {}
    for part in interests_param.split(","):
        if ":" in part:
            name, weight = part.split(":", 1)
            try:
                interests[normalize_text(name)] = int(weight)
            except ValueError:
                continue

    if not interests:
        return df

    def compute_score(category):
        category_norm = normalize_text(category)
        return sum(
            weight for name, weight in interests.items()
            if name in category_norm
        )

    df = df.copy()
    df["interest_score"] = df["Category"].apply(compute_score)

    return df[df["interest_score"] > 0]


# =================================================
# FILTRAGE PAR DATE (SANS EXCLUSION AUTOMATIQUE)
# =================================================

def filter_by_date(df: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """
    Filtre uniquement selon les paramètres utilisateur (start / end).
    Les événements passés sont CONSERVÉS.
    """

    if df.empty or "DateTime_start" not in df.columns:
        return df

    if start:
        try:
            start = pd.to_datetime(start)
            df = df[df["DateTime_start"] >= start]
        except Exception:
            pass

    if end:
        try:
            end = pd.to_datetime(end)
            df = df[df["DateTime_start"] <= end]
        except Exception:
            pass

    return df
