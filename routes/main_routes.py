from flask import Blueprint, render_template, jsonify, request
from utils.data_utils import (
    load_events,
    filter_by_date,
    filter_by_category,
    normalize_text
)
import pandas as pd
import re


# =================================================
# LOAD DATA ONCE (CACHE GLOBAL)
# =================================================

EVENTS_DF = load_events()


# =================================================
# NORMALIZATION 
# =================================================

CATEGORY_TRANSLATIONS = {
    "concert": "Concerts",
    "concerts": "Concerts",
    "konzerte": "Concerts",
    "conciertos": "Concerts",
    "exhibition": "Expositions",
    "exhibitions": "Expositions",
    "ausstellungen": "Expositions",
    "exposiciones": "Expositions",
    "market": "Marchés",
    "markets": "Marchés",
    "marches": "Marchés",
    "marchés": "Marchés",
    "märkte": "Marchés",
    "maerkte": "Marchés",
    "mercados": "Marchés",
    "flea market": "Marchés aux puces",
    "flea markets": "Marchés aux puces",
    "flohmärkte": "Marchés aux puces",
    "flohmaerkte": "Marchés aux puces",
    "mercadillos": "Marchés aux puces",
    "christmas market": "Marchés de Noël",
    "christmas markets": "Marchés de Noël",
    "marches de noel": "Marchés de Noël",
    "marchés de noël": "Marchés de Noël",
    "weihnachtsmärkte": "Marchés de Noël",
    "weihnachtsmaerkte": "Marchés de Noël",
    "festival": "Festivals",
    "festivals": "Festivals",
    "festivales": "Festivals",
    "ferias": "Fêtes et foires",
    "fetes et foires": "Fêtes et foires",
    "trade show": "Salons professionnels",
    "trade shows": "Salons professionnels",
    "fachmessen": "Salons professionnels",
    "ferias profesionales": "Salons professionnels",
    "dance": "Spectacles de danse",
    "danza": "Spectacles de danse",
    "tanzshows": "Spectacles de danse",
    "theatre": "Théâtre",
    "theater": "Théâtre",
    "teatro": "Théâtre",
    "opera": "Opéra",
    "oper": "Opéra",
    "musical": "Comédies musicales",
    "musicals": "Comédies musicales",
    "musicales": "Comédies musicales",
    "ateliers": "Ateliers",
    "messen": "Salons",
}


def translate_category_safe(value):
    if not isinstance(value, str) or not value.strip():
        return None

    norm = normalize_text(value)
    tokens = [
        t.strip()
        for t in re.split(r"[;,/|-]", norm)
        if t.strip()
    ]

    for token in tokens:
        if token in CATEGORY_TRANSLATIONS:
            return CATEGORY_TRANSLATIONS[token]

    return value


# =================================================
# BLUEPRINT
# =================================================

bp = Blueprint("main", __name__)


# =================================================
# FILTRES COMMUNS
# =================================================

def apply_filters(df, args):
    df = df.copy()

    interests = args.get("interests", "")
    query_raw = args.get("q", "")
    query = normalize_text(query_raw)
    city = normalize_text(args.get("city", ""))
    start_date = args.get("start_date", "")
    end_date = args.get("end_date", "")

    # -----------------------------
    # Weighted interests
    # -----------------------------
    if interests:
        df = filter_by_category(df, interests)

    # -----------------------------
    # City
    # -----------------------------
    if city and "City" in df.columns:
        df = df[
            df["City"]
            .apply(normalize_text)
            .str.contains(city, na=False)
        ]

    # -----------------------------
    # Multi-word free-text search
    # -----------------------------
    if query:
        keywords = [k for k in query.split() if len(k) > 1]

        def keyword_score(row):
            text = normalize_text(
                f"{row.get('EventName','')} {row.get('Description','')}"
            )

            matches = sum(1 for k in keywords if k in text)

            if matches == 0:
                return 0

            if matches == len(keywords):
                return matches + 2

            return matches

        df["_query_score"] = df.apply(keyword_score, axis=1)
        df = df[df["_query_score"] > 0]

    # -----------------------------
    # Dates
    # -----------------------------
    df = filter_by_date(df, start_date, end_date)

    return df


# =================================================
# ROUTES
# =================================================

@bp.route("/")
def index():
    return render_template("index.html")


@bp.route("/api/categories")
def api_categories():
    df = EVENTS_DF
    if df.empty or "Category" not in df.columns:
        return jsonify([])

    categories = set()
    for c in df["Category"]:
        translated = translate_category_safe(c)
        if translated:
            categories.add(translated)

    return jsonify(sorted(categories))


@bp.route("/api/smart-search")
def smart_search():
    df = EVENTS_DF
    if df.empty:
        return jsonify([])

    df = apply_filters(df, request.args)

    # -----------------------------
    # Ticketmaster UX
    # -----------------------------
    if "Source" in df.columns:
        mask = df["Source"].str.lower().str.contains("ticketmaster", na=False)

        if "Link" in df.columns:
            df.loc[mask, "Link"] = None

        df.loc[mask, "Source"] = "Billetterie disponible sur Ticketmaster"

    # -----------------------------
    # Final ranking (relevance)
    # -----------------------------
    sort_cols = []

    if "interest_score" in df.columns:
        sort_cols.append("interest_score")

    if "_query_score" in df.columns:
        sort_cols.append("_query_score")

    if sort_cols:
        df = df.sort_values(sort_cols, ascending=False)

    if "Category" in df.columns:
        df["Category"] = df["Category"].apply(translate_category_safe)

    if request.args.get("sort") == "date":
        df = df.sort_values("DateTime_start", ascending=True)

    df = df.head(500)
    df = df.astype(object)
    df = df.where(pd.notna(df), None)

    return jsonify(df.to_dict(orient="records"))


@bp.route("/api/cities-by-llm")
def cities_by_llm():
    df = EVENTS_DF
    if df.empty or "City" not in df.columns:
        return jsonify([])

    df = apply_filters(df, request.args)

    df["City"] = df["City"].astype(str).str.strip()
    df = df[df["City"] != ""]

    interests_param = request.args.get("interests", "")
    requested_interests = {
        part.split(":")[0]
        for part in interests_param.split(",")
        if ":" in part
    }

    df["_cat_norm"] = df["Category"].apply(
        lambda x: normalize_text(x) if isinstance(x, str) else ""
    )

    rows = []

    for city, g in df.groupby("City"):
        covered = set()

        for interest in requested_interests:
            if g["_cat_norm"].str.contains(interest, na=False).any():
                covered.add(interest)

        rows.append({
            "City": city,
            "count": len(g),
            "coverage_score": len(covered)
        })

    city_df = pd.DataFrame(rows)

    city_df = city_df.sort_values(
        ["coverage_score", "count"],
        ascending=[False, False]
    )

    return jsonify(city_df.to_dict(orient="records"))

