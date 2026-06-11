"""Script CLI — Construction de la base SQLite à partir du checkpoint pickle.

Lance :
    python -m scripts.build_db
"""
from __future__ import annotations

import json
import pickle
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

from jobflow_core import config


CHECKPOINT_FILE = config.ASSETS_DIR / "checkpoint_offres.pkl"
DB_PATH = config.DB_PATH

COLS_KEEP = [
    "id", "intitule", "dateCreation", "dateActualisation",
    "typeContrat", "typeContratLibelle", "natureContratLibelle",
    "experienceLibelle", "qualificationLibelle", "dureeTravailLibelleConverti",
    "lieuTravail.libelle", "lieuTravail.codePostal", "lieuTravail.departement",
    "entreprise.nom", "entreprise.secteurActiviteLibelle",
    "salaire.libelle",
    "appellationlibelle", "secteurActiviteLibelle", "romeCode",
    "contexteTravail.typesTravail",
    "competences", "formations", "langues", "permis",
    "description",
    "agence.libelle", "agence.urlPostulation",
    "origineOffre.urlOrigine",
]


def main():
    if not CHECKPOINT_FILE.exists():
        sys.exit(f"{CHECKPOINT_FILE} introuvable — lance d'abord scripts.collect_offres")

    print(f"📂 Chargement {CHECKPOINT_FILE}…")
    with open(CHECKPOINT_FILE, "rb") as f:
        all_offres = pickle.load(f)
    df_full = pd.json_normalize(list(all_offres.values()), sep=".")
    print(f"✅ {len(df_full):,} offres")

    cols_present = [c for c in COLS_KEEP if c in df_full.columns]
    df = df_full[cols_present].copy()
    print(f"📊 {df.shape[1]} colonnes conservées sur {df_full.shape[1]} brutes")

    for col in df.columns:
        if df[col].apply(lambda x: isinstance(x, list)).any():
            df[col] = df[col].apply(
                lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, list) else x
            )

    df.columns = [c.replace(".", "_") for c in df.columns]
    if "lieuTravail_codePostal" in df.columns:
        df["dept"] = df["lieuTravail_codePostal"].astype(str).str[:2]

    if DB_PATH.exists():
        DB_PATH.unlink()
        print("🗑️  Ancienne DB supprimée")

    con = sqlite3.connect(DB_PATH)
    print("💾 Écriture SQLite…")
    df.to_sql("offres", con, if_exists="replace", index=False)
    cur = con.cursor()

    # Index
    for name, col in [("idx_dept", "dept"), ("idx_type", "typeContrat"),
                      ("idx_rome", "romeCode"), ("idx_date_creat", "dateCreation"),
                      ("idx_date_actu", "dateActualisation")]:
        if col in df.columns:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {name} ON offres({col})")
    con.commit()

    # FTS5
    print("🔎 Création FTS5…")
    cur.execute("DROP TABLE IF EXISTS offres_fts")
    cur.execute("""
        CREATE VIRTUAL TABLE offres_fts USING fts5(
            id UNINDEXED,
            intitule, description, competences,
            appellationlibelle, entreprise_nom,
            tokenize = 'unicode61 remove_diacritics 2'
        )
    """)
    fts_cols = ["id", "intitule", "description", "competences",
                "appellationlibelle", "entreprise_nom"]
    fts_cols_present = [c for c in fts_cols if c in df.columns]
    df_fts = df[fts_cols_present].fillna("").astype(str)
    df_fts.to_sql("offres_fts", con, if_exists="append", index=False)
    con.commit()

    size_mb = DB_PATH.stat().st_size / 1024 / 1024
    print(f"\n🎉 {DB_PATH} prête — {len(df):,} offres, {size_mb:.0f} Mo")
    con.close()


if __name__ == "__main__":
    main()
