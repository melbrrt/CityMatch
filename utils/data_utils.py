import pandas as pd
import unicodedata
import re
import os

# =================================================
# CONFIGURATION PATH
# =================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.abspath(
    os.path.join(BASE_DIR, "..", "data", "csv_fusionne.csv")
)

# =================================================
# TEXT NORMALIZATION
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
# LOAD EVENTS (ROBUST & SAFE)
# =================================================

def load_events() -> pd.DataFrame:
    print("CSV utilisé :", CSV_PATH)
    print("Fichier existe ?", os.path.exists(CSV_PATH))

    if not os.path.exists(CSV_PATH):
        print("CSV introuvable")
        return pd.DataFrame()

    try:
        df = pd.read_csv(
            CSV_PATH,
            sep=";",
            engine="python",       
            encoding="utf-8",
            on_bad_lines="skip"    
        )
    except Exception as e:
        print("Erreur lecture CSV :", e)
        return pd.DataFrame()

    # Colonnes minimales attendues
    required_columns = ["Category", "City", "EventName", "Description"]
    if not all(col in df.columns for col in required_columns):
        print("Colonnes requises manquantes :", df.columns.tolist())
        return pd.DataFrame()

    # Coordonnées
    df["lat"] = pd.to_numeric(df.get("lat"), errors="coerce")
    df["lon"] = pd.to_numeric(df.get("lon"), errors="coerce")

    # =================================================
    # PARSING DES DATES — JOURNÉE SEULE (SANS HEURE)
    # =================================================

    if "DateTime_start" in df.columns:
        df["DateTime_start"] = (
            pd.to_datetime(
                df["DateTime_start"],    
                dayfirst=True,
                errors="coerce"
            )
            .dt.normalize()        
        )
    else:
        df["DateTime_start"] = pd.NaT

    if "DateTime_end" in df.columns:
        df["DateTime_end"] = (
            pd.to_datetime(
                df["DateTime_end"],
                dayfirst=True,
                errors="coerce"
            )
            .dt.normalize()
        )
    else:
        df["DateTime_end"] = pd.NaT

    # Sécurité texte
    for col in ["Category", "City", "EventName", "Description"]:
        df[col] = df[col].fillna("").astype(str)

    print("Lignes chargées :", len(df))
    print("Colonnes :", df.columns.tolist())
    print("Type DateTime_start :", df["DateTime_start"].dtype)

    return df


# =================================================
# FILTER BY CATEGORY
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
# FILTER BY DATE 
# =================================================

def filter_by_date(df: pd.DataFrame, start=None, end=None) -> pd.DataFrame:
    """
    Filtre selon DateTime_start.
    - Par défaut : exclut les événements passés
    - Si start/end sont fournis : respecte le filtre utilisateur
    """

    if df.empty or "DateTime_start" not in df.columns:
        return df

    df = df.copy()


    df["DateTime_start"] = pd.to_datetime(
        df["DateTime_start"], errors="coerce"
    )

    today = pd.Timestamp.now().normalize()


    if not start:
        df = df[df["DateTime_start"] >= today]
    else:
        start = pd.to_datetime(start, errors="coerce")
        if pd.notna(start):
            df = df[df["DateTime_start"] >= start]


    if end:
        end = pd.to_datetime(end, errors="coerce")
        if pd.notna(end):
            df = df[df["DateTime_start"] <= end]

    return df
