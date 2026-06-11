"""Phase 3c — Matching sémantique profil ↔ offres + analyse LLM profonde.

v6 (8 juin 2026) — Ajout filtrage strict par type de contrat AVANT l'analyse LLM.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import torch
from sentence_transformers import SentenceTransformer

from . import config
from .cerebras_client import call_llm


# ─── Embedding du profil ─────────────────────────────────────────────
_embedding_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """Lazy-load du modèle e5-small. Utilise MPS si dispo, sinon CPU."""
    global _embedding_model
    if _embedding_model is None:
        if torch.backends.mps.is_available():
            device = "mps"
        elif torch.cuda.is_available():
            device = "cuda"
        else:
            device = "cpu"
        m = SentenceTransformer(config.EMBEDDING_MODEL, device=device)
        m.max_seq_length = 256
        _embedding_model = m
    return _embedding_model


def embed_profile(profil: dict) -> np.ndarray:
    """Embedde la 'synthese_pour_matching' du profil pour le matching."""
    synthese = profil.get("synthese_pour_matching", "")
    if not synthese:
        raise ValueError("Profil sans 'synthese_pour_matching' — refais la Phase 3b.")
    model = get_embedding_model()
    vec = model.encode(
        [f"query: {synthese}"],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )[0]
    return vec


# ─── SQLite : détection de schéma flexible ───────────────────────────
def detect_schema(con: sqlite3.Connection) -> dict[str, str | None]:
    """Trouve les colonnes dans la table 'offres' quelle que soit la variante."""
    cols = pd.read_sql("PRAGMA table_info(offres)", con)["name"].tolist()

    def find(*candidates):
        for cand in candidates:
            for c in cols:
                if cand.lower() in c.lower():
                    return c
        return None

    return {
        "id":          find("id"),
        "intitule":    find("intitule"),
        "description": find("description"),
        "ville":       find("lieuTravail.libelle", "lieutravail_libelle", "ville"),
        "cp":          find("codePostal"),
        "contrat":     find("typeContrat") if not find("typeContratLibelle") else find("typeContrat"),
        "contrat_lib": find("typeContratLibelle", "typecontratlibelle"),
        "salaire":     find("salaire.libelle", "salaire_libelle", "salaire"),
        "entreprise":  find("entreprise.nom", "entreprise_nom", "entreprise"),
        "competences": find("competences"),
        "experience":  find("experienceLibelle", "experience"),
        "url":         find("origineOffre.urlOrigine", "url"),
    }


# ─── Filtre sémantique top 100 ───────────────────────────────────────
def semantic_top_k(
    profil_vec: np.ndarray,
    emb_offres: np.ndarray,
    ids_offres: np.ndarray,
    k: int = config.TOP_K_SEMANTIC,
) -> tuple[np.ndarray, np.ndarray]:
    """Retourne (ids_top_k, scores_top_k) triés par score décroissant."""
    scores = emb_offres @ profil_vec
    top_idx = np.argpartition(-scores, k)[:k]
    top_idx = top_idx[np.argsort(-scores[top_idx])]
    return ids_offres[top_idx], scores[top_idx]


def fetch_offres_details(
    con: sqlite3.Connection,
    ids: np.ndarray,
    scores: np.ndarray,
    schema: dict,
) -> pd.DataFrame:
    """Va chercher les détails des offres dans SQLite et conserve l'ordre des scores."""
    id_col = schema["id"]
    placeholders = ",".join("?" * len(ids))
    query = f'SELECT * FROM offres WHERE "{id_col}" IN ({placeholders})'
    df = pd.read_sql(query, con, params=ids.tolist())
    df["_sem_score"] = df[id_col].astype(str).map(
        dict(zip(ids.astype(str), scores))
    )
    return df.sort_values("_sem_score", ascending=False).reset_index(drop=True)


# ─── 🆕 Filtrage strict par type de contrat ──────────────────────────
#
# Mapping préférences candidat → codes France Travail + mots-clés à chercher
# dans l'intitulé / la description quand le code seul ne suffit pas
# (cas Alternance et Stage qui sont noyés dans le code CDD chez FT).
CONTRAT_MAPPING = {
    "cdi": {
        "codes":    {"CDI", "DIN"},   # DIN = CDI intérimaire, on l'inclut
        "keywords": [],               # le code suffit
    },
    "cdd": {
        "codes":    {"CDD", "DDI", "DDT"},
        "keywords": [],
    },
    "interim": {
        "codes":    {"MIS", "TTI"},
        "keywords": ["intérim", "interim", "mission temporaire"],
    },
    "alternance": {
        "codes":    set(),  # pas de code dédié chez FT
        "keywords": [
            "alternance",
            "apprentissage",
            "apprenti",
            "contrat pro",
            "contrat de professionnalisation",
            "professionnalisation",
        ],
    },
    "stage": {
        "codes":    set(),  # pas de code dédié chez FT
        "keywords": ["stage", "stagiaire", "internship"],
    },
    "saisonnier": {
        "codes":    {"SAI"},
        "keywords": ["saisonnier", "saisonnière"],
    },
    "freelance": {
        "codes":    {"LIB", "FRA"},
        "keywords": ["freelance", "indépendant", "consultant indépendant"],
    },
}


def _normalize_contrat_pref(pref: str) -> str | None:
    """Normalise une préférence candidat (libre) vers une clé du mapping."""
    if not pref:
        return None
    p = pref.lower().strip()
    # Mapping souple
    if "cdi" in p:                                                  return "cdi"
    if "cdd" in p:                                                  return "cdd"
    if "altern" in p or "apprenti" in p or "pro " in p:             return "alternance"
    if "stage" in p or "stagia" in p or "intern" in p:              return "stage"
    if "interim" in p or "intérim" in p or "mission" in p:          return "interim"
    if "saison" in p:                                               return "saisonnier"
    if "freelance" in p or "indép" in p or "libér" in p:            return "freelance"
    return None


def _offre_matches_contrats(
    row: pd.Series,
    schema: dict,
    accepted_codes: set[str],
    accepted_keywords: list[str],
) -> bool:
    """Renvoie True si l'offre matche au moins une des préférences contrat."""
    code = str(row.get(schema["contrat"], "") or "").strip().upper()

    # Cas 1 : le code suffit (ex: CDI, MIS, CDD)
    if code in accepted_codes:
        return True

    # Cas 2 : on cherche les mots-clés (alternance, stage…)
    if accepted_keywords:
        haystack = " ".join([
            str(row.get(schema["intitule"], "") or ""),
            str(row.get(schema["contrat_lib"], "") or ""),
            str(row.get(schema["description"], "") or "")[:1500],  # limite pour perf
        ]).lower()
        for kw in accepted_keywords:
            if kw in haystack:
                return True

    return False


def filter_by_contract(
    df: pd.DataFrame,
    profil: dict,
    schema: dict,
) -> tuple[pd.DataFrame, dict]:
    """Filtre strictement les offres selon types_de_contrats_acceptes du profil.

    Retourne (df_filtré, stats_filtre).
    Si la préférence est vide ou absente, retourne df inchangé.
    """
    prefs_raw = profil.get("preferences", {}).get("types_de_contrats_acceptes", [])
    if not prefs_raw or not isinstance(prefs_raw, list):
        return df, {"filtered": False, "reason": "Aucune préférence contrat"}

    # Normalise chaque préférence candidat vers une clé du mapping
    normalized = {_normalize_contrat_pref(p) for p in prefs_raw if p}
    normalized.discard(None)

    if not normalized:
        return df, {"filtered": False, "reason": "Préférences contrat non reconnues"}

    # Union des codes et mots-clés acceptés
    accepted_codes: set[str] = set()
    accepted_keywords: list[str] = []
    for key in normalized:
        m = CONTRAT_MAPPING[key]
        accepted_codes |= m["codes"]
        accepted_keywords.extend(m["keywords"])

    # Application du filtre
    mask = df.apply(
        lambda row: _offre_matches_contrats(row, schema, accepted_codes, accepted_keywords),
        axis=1,
    )
    df_kept = df[mask].reset_index(drop=True)

    stats = {
        "filtered":           True,
        "preferences_raw":    prefs_raw,
        "preferences_norm":   list(normalized),
        "accepted_codes":     sorted(accepted_codes),
        "accepted_keywords":  accepted_keywords,
        "n_before":           len(df),
        "n_after":            len(df_kept),
        "n_excluded":         len(df) - len(df_kept),
    }
    return df_kept, stats


# ─── Analyse LLM profonde ────────────────────────────────────────────
_SYSTEM_ANALYSE = """Tu es un expert en recrutement et conseil en carrière, spécialiste du raisonnement profond sur l'adéquation profil-offre.

Tu analyses la pertinence d'une offre pour un candidat en raisonnant sur :
- Les compétences EXPLICITES du candidat (formations, expériences, certifications)
- Les compétences DÉDUITES de son parcours (contextes des expériences, secteurs traversés, type d'école)
- Ses préférences (zones géographiques, salaire, contrat, secteurs voulus/rejetés)
- Ses ambitions et la cohérence trajectoire ↔ offre (junior/senior, secteur d'intérêt déclaré)

RÈGLE STRICTE — TYPE DE CONTRAT :
Le candidat précise les types de contrats acceptés dans son profil. Si l'offre n'est pas
dans un type de contrat accepté, BAISSE FORTEMENT LE SCORE (max 40/100) et mentionne-le
clairement dans points_faibles. L'inadéquation contrat est rédhibitoire dans 90% des cas.

Méthode :
- Tu déduis les compétences implicites depuis les contextes (école, secteur, type d'expérience)
- Tu considères la cohérence trajectoire ↔ offre (junior/senior, secteur d'intérêt déclaré)
- Tu pèses les préférences explicites du candidat (zones, salaire, contrat, secteurs)
- Tu identifies à la fois les forces du match et les zones de tension

Réponds UNIQUEMENT en JSON valide, schéma exact :
{
  "score": <int 0-100>,
  "fit_level": "<Excellent|Bon|Correct|Faible>",
  "points_forts": ["<point 1>", "<point 2>", "<point 3>"],
  "points_faibles": ["<point 1>", "<point 2>"],
  "raisonnement": "<3-4 phrases qui expliquent en profondeur pourquoi ça match (ou non)>"
}

Sois CONCIS dans les listes (3 points forts max, 2 points faibles max).
Le score doit refléter la qualité du fit global, en pondérant compétences (40%),
préférences explicites (30%), trajectoire et ambitions (30%)."""


def _build_offer_user_prompt(profil_str: str, row: pd.Series, schema: dict) -> str:
    titre        = str(row.get(schema["intitule"], "") or "")[:200]
    ville        = str(row.get(schema["ville"], "") or "")
    contrat_code = str(row.get(schema["contrat"], "") or "")
    contrat_lib  = str(row.get(schema["contrat_lib"], "") or "")
    contrat_aff  = f"{contrat_lib} (code {contrat_code})" if contrat_lib else contrat_code
    salaire      = str(row.get(schema["salaire"], "") or "")
    entreprise   = str(row.get(schema["entreprise"], "") or "")
    experience   = str(row.get(schema["experience"], "") or "")
    desc         = str(row.get(schema["description"], "") or "")[:2500]
    return (
        f"PROFIL CANDIDAT (JSON complet) :\n{profil_str}\n\n"
        f"OFFRE À ANALYSER :\n"
        f"Intitulé : {titre}\n"
        f"Entreprise : {entreprise}\n"
        f"Lieu : {ville}\n"
        f"Contrat : {contrat_aff}\n"
        f"Salaire : {salaire}\n"
        f"Expérience requise : {experience}\n"
        f"Description :\n{desc}\n\n"
        "Produis ton analyse en JSON."
    )


def profile_state_path(profil: dict) -> Path:
    """Path du fichier de state du matching, dérivé du hash du profil (multi-candidats safe)."""
    raw = json.dumps(profil, ensure_ascii=False, sort_keys=True).encode()
    h = hashlib.md5(raw).hexdigest()[:8]
    return config.STATE_DIR / f"analyses_{h}.json"


def run_deep_analysis(
    profil: dict,
    top_df: pd.DataFrame,
    schema: dict,
    progress_cb: Callable[[int, int, str], None] | None = None,
    sleep_s: float = config.SLEEP_BETWEEN_LLM_CALLS,
) -> dict[str, dict]:
    """Analyse en profondeur les offres du top sémantique (déjà filtré).
    Reprenable : le state est sauvegardé après chaque appel.
    """
    state_file = profile_state_path(profil)
    if state_file.exists():
        analyses: dict[str, dict] = json.loads(state_file.read_text(encoding="utf-8"))
    else:
        analyses = {}

    profil_str = json.dumps(profil, ensure_ascii=False, indent=2)
    id_col = schema["id"]
    total = len(top_df)

    for i, row in top_df.iterrows():
        offre_id = str(row[id_col])
        if offre_id in analyses:
            if progress_cb:
                progress_cb(i + 1, total, f"déjà fait : {offre_id}")
            continue

        user_prompt = _build_offer_user_prompt(profil_str, row, schema)
        try:
            result = call_llm(
                messages=[
                    {"role": "system", "content": _SYSTEM_ANALYSE},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=2000,
                temperature=0.3,
            )
            result["sem_score"] = float(row["_sem_score"])
            analyses[offre_id] = result
        except Exception as e:
            if progress_cb:
                progress_cb(i + 1, total, f"erreur : {e}")
            state_file.write_text(
                json.dumps(analyses, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            raise

        state_file.write_text(
            json.dumps(analyses, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if progress_cb:
            progress_cb(
                i + 1, total,
                f"{row.get(schema['intitule'], '')[:50]} → {result.get('score', '?')}/100",
            )
        time.sleep(sleep_s)

    return analyses


def build_top10(
    analyses: dict[str, dict],
    top_df: pd.DataFrame,
    schema: dict,
    k: int = config.TOP_K_FINAL,
) -> list[dict]:
    """Construit la liste finale top-K à partir des analyses LLM."""
    # Ne garde que les offres présentes dans le df filtré ET analysées
    valid_ids = set(top_df[schema["id"]].astype(str))
    analyses_valid = [
        (k_, v) for k_, v in analyses.items()
        if v.get("score", 0) > 0 and str(k_) in valid_ids
    ]
    analyses_sorted = sorted(analyses_valid, key=lambda x: x[1]["score"], reverse=True)[:k]
    id_col = schema["id"]

    out = []
    for offre_id, analyse in analyses_sorted:
        match = top_df[top_df[id_col].astype(str) == str(offre_id)]
        if match.empty:
            continue
        row = match.iloc[0]
        contrat_lib = str(row.get(schema["contrat_lib"], "") or "")
        contrat_code = str(row.get(schema["contrat"], "") or "")
        out.append({
            "id":             offre_id,
            "intitule":       str(row.get(schema["intitule"], "") or ""),
            "entreprise":     str(row.get(schema["entreprise"], "") or ""),
            "ville":          str(row.get(schema["ville"], "") or ""),
            "contrat":        contrat_lib or contrat_code,
            "contrat_code":   contrat_code,
            "salaire":        str(row.get(schema["salaire"], "") or ""),
            "experience":     str(row.get(schema["experience"], "") or ""),
            "url":            str(row.get(schema["url"], "") or ""),
            "description":    str(row.get(schema["description"], "") or "")[:3000],
            "competences":    str(row.get(schema["competences"], "") or ""),
            "score_final":    analyse["score"],
            "fit_level":      analyse["fit_level"],
            "points_forts":   analyse.get("points_forts", []),
            "points_faibles": analyse.get("points_faibles", []),
            "raisonnement":   analyse.get("raisonnement", ""),
            "sem_score":      analyse.get("sem_score", 0.0),
        })
    return out


def save_top10(top10: list[dict], path: Path = config.TOP10_PATH) -> None:
    path.write_text(json.dumps(top10, ensure_ascii=False, indent=2), encoding="utf-8")


def load_top10(path: Path = config.TOP10_PATH) -> list[dict] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ─── Pipeline complet ────────────────────────────────────────────────
def run_full_matching(
    profil: dict,
    progress_cb: Callable[[int, int, str], None] | None = None,
) -> list[dict]:
    """Pipeline complet : embedding profil → top 100 sémantique → filtre contrat
    → analyse LLM → top 10 final.
    """
    if not config.assets_present():
        raise RuntimeError(
            "Assets manquants. Lance le téléchargement depuis Settings."
        )

    emb_offres = np.load(config.EMB_PATH)
    ids_offres = np.load(config.IDS_PATH, allow_pickle=True)

    if emb_offres.shape[1] != config.EMBEDDING_DIM:
        raise RuntimeError(
            f"Dimension embeddings = {emb_offres.shape[1]}, attendu {config.EMBEDDING_DIM}"
        )

    profil_vec = embed_profile(profil)
    top_ids, top_scores = semantic_top_k(profil_vec, emb_offres, ids_offres)

    con = sqlite3.connect(config.DB_PATH)
    try:
        schema = detect_schema(con)
        top_df = fetch_offres_details(con, top_ids, top_scores, schema)

        # 🆕 FILTRAGE STRICT par type de contrat avant l'analyse LLM
        top_df_filtered, filter_stats = filter_by_contract(top_df, profil, schema)

        if filter_stats.get("filtered") and progress_cb:
            n_excl = filter_stats["n_excluded"]
            prefs = filter_stats["preferences_norm"]
            progress_cb(
                0, max(1, len(top_df_filtered)),
                f"Filtre contrat : {n_excl}/{filter_stats['n_before']} offres écartées "
                f"(garde : {', '.join(prefs)})"
            )
            time.sleep(1.5)  # laisse le user voir le message

        if len(top_df_filtered) == 0:
            raise RuntimeError(
                "Aucune offre dans le top 100 sémantique ne correspond aux types de "
                "contrats acceptés. Élargis tes préférences en page Profil, ou augmente "
                "TOP_K_SEMANTIC dans config.py."
            )

        analyses = run_deep_analysis(
            profil, top_df_filtered, schema, progress_cb=progress_cb
        )
        top10 = build_top10(analyses, top_df_filtered, schema)
        save_top10(top10)
    finally:
        con.close()

    return top10
