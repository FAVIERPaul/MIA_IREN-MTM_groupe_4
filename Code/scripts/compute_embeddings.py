"""Script CLI — Calcul des embeddings de toutes les offres (Phase 3a).

Lance :
    python -m scripts.compute_embeddings              # full
    python -m scripts.compute_embeddings --resume     # reprend les chunks restants
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

from jobflow_core import config


CHUNK_SIZE = 5000
BATCH_SIZE = 64
EMB_DIR = config.ASSETS_DIR / "embeddings_chunks"


def build_passage_text(row: dict, schema: dict) -> str:
    """Construit le texte à embedder pour une offre — concis et orienté matching."""
    parts = []
    if row.get(schema["intitule"]):
        parts.append(f"Poste: {row[schema['intitule']]}")
    if row.get(schema["entreprise"]):
        parts.append(f"Entreprise: {row[schema['entreprise']]}")
    if row.get(schema["ville"]):
        parts.append(f"Lieu: {row[schema['ville']]}")
    if row.get(schema["contrat"]):
        parts.append(f"Contrat: {row[schema['contrat']]}")
    if row.get(schema["experience"]):
        parts.append(f"Expérience: {row[schema['experience']]}")
    if row.get(schema["competences"]):
        try:
            comp = json.loads(row[schema["competences"]]) if isinstance(row[schema["competences"]], str) else row[schema["competences"]]
            if isinstance(comp, list):
                libelles = [c.get("libelle", "") for c in comp if isinstance(c, dict)]
                if libelles:
                    parts.append(f"Compétences: {', '.join(libelles[:15])}")
        except Exception:
            pass
    if row.get(schema["description"]):
        desc = str(row[schema["description"]])[:1500]
        parts.append(f"Description: {desc}")
    return "passage: " + " | ".join(parts)


def detect_schema(con: sqlite3.Connection) -> dict[str, str | None]:
    cols = pd.read_sql("PRAGMA table_info(offres)", con)["name"].tolist()
    def find(*c):
        for cand in c:
            for col in cols:
                if cand.lower() in col.lower(): return col
        return None
    return {
        "id":          find("id"),
        "intitule":    find("intitule"),
        "description": find("description"),
        "ville":       find("lieuTravail.libelle", "lieutravail_libelle", "ville"),
        "contrat":     find("typeContrat", "typecontrat"),
        "entreprise":  find("entreprise.nom", "entreprise_nom"),
        "competences": find("competences"),
        "experience":  find("experienceLibelle", "experience"),
    }


def main(resume: bool = False):
    if not config.DB_PATH.exists():
        sys.exit(f"DB introuvable ({config.DB_PATH}) — lance scripts.build_db d'abord")

    EMB_DIR.mkdir(parents=True, exist_ok=True)

    # Device
    if torch.backends.mps.is_available():
        device = "mps"
    elif torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    print(f"🖥️  Device : {device}")

    print(f"📚 Chargement modèle {config.EMBEDDING_MODEL}…")
    model = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
    model.max_seq_length = 256

    con = sqlite3.connect(config.DB_PATH)
    schema = detect_schema(con)
    id_col = schema["id"]

    # Charger tous les IDs
    print("📊 Lecture des IDs…")
    ids_df = pd.read_sql(f'SELECT "{id_col}" FROM offres', con)
    n_total = len(ids_df)
    print(f"✅ {n_total:,} offres à embedder")

    n_chunks = (n_total + CHUNK_SIZE - 1) // CHUNK_SIZE
    print(f"📦 {n_chunks} chunks de {CHUNK_SIZE} offres")

    existing_chunks = set()
    if resume:
        existing_chunks = {int(p.stem.split("_")[1]) for p in EMB_DIR.glob("chunk_*.npz")}
        print(f"♻️  {len(existing_chunks)} chunks déjà calculés (resume)")

    for chunk_idx in tqdm(range(n_chunks), desc="Chunks"):
        if chunk_idx in existing_chunks:
            continue

        offset = chunk_idx * CHUNK_SIZE
        df_chunk = pd.read_sql(
            f'SELECT * FROM offres LIMIT {CHUNK_SIZE} OFFSET {offset}', con
        )
        passages = [build_passage_text(row, schema) for _, row in df_chunk.iterrows()]
        ids_chunk = df_chunk[id_col].astype(str).values

        embs = model.encode(
            passages,
            batch_size=BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        np.savez_compressed(
            EMB_DIR / f"chunk_{chunk_idx:05d}.npz",
            embeddings=embs.astype(np.float32),
            ids=ids_chunk,
        )

    # Consolidation
    print("\n🔗 Consolidation des chunks…")
    all_embs = []
    all_ids = []
    for chunk_file in tqdm(sorted(EMB_DIR.glob("chunk_*.npz")), desc="Loading"):
        data = np.load(chunk_file, allow_pickle=True)
        all_embs.append(data["embeddings"])
        all_ids.append(data["ids"])
    all_embs = np.concatenate(all_embs, axis=0)
    all_ids = np.concatenate(all_ids, axis=0)

    np.save(config.EMB_PATH, all_embs)
    np.save(config.IDS_PATH, all_ids)
    print(f"\n🎉 {config.EMB_PATH} : {all_embs.shape}")
    print(f"🎉 {config.IDS_PATH} : {all_ids.shape}")
    print(f"💾 Total : {(all_embs.nbytes + all_ids.nbytes) / 1024 / 1024:.0f} Mo")

    con.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="Reprend les chunks manquants")
    args = ap.parse_args()
    main(resume=args.resume)
