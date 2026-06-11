"""Configuration centrale de JoBFlow — chemins, clés API, constantes."""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Charge le .env du dossier racine du projet
ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# ─── Dossiers de données ─────────────────────────────────────────────
# Tout est stocké dans ~/.jobflow par défaut (override possible via MIA_DATA_DIR)
DATA_DIR = Path(os.getenv("MIA_DATA_DIR", Path.home() / ".jobflow")).expanduser()
DATA_DIR.mkdir(parents=True, exist_ok=True)

OUTPUTS_CV_DIR = DATA_DIR / "outputs_cv"
OUTPUTS_LM_DIR = DATA_DIR / "outputs_lm"
LM_EXAMPLES_DIR = DATA_DIR / "lm_exemples"
STATE_DIR = DATA_DIR / "matching_state"
USER_DIR = DATA_DIR / "user"  # cv, profil, top10 du candidat actif

for d in (OUTPUTS_CV_DIR, OUTPUTS_LM_DIR, LM_EXAMPLES_DIR, STATE_DIR, USER_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ─── Fichiers d'assets téléchargés depuis Hugging Face ───────────────
ASSETS_DIR = DATA_DIR / "assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = ASSETS_DIR / "offres.db"
EMB_PATH = ASSETS_DIR / "offres_embeddings.npy"
IDS_PATH = ASSETS_DIR / "offres_ids.npy"
ASSETS_FILES = [DB_PATH, EMB_PATH, IDS_PATH]

# ─── Fichiers utilisateur (CV, profil, etc.) ─────────────────────────
CV_PDF_PATH = USER_DIR / "mon_cv.pdf"
PROFIL_PATH = USER_DIR / "profil_enrichi.json"
TOP10_PATH = USER_DIR / "top10_matching.json"

# ─── Clés API ────────────────────────────────────────────────────────
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "").strip()
FRANCE_TRAVAIL_CLIENT_ID = os.getenv("FRANCE_TRAVAIL_CLIENT_ID", "").strip()
FRANCE_TRAVAIL_CLIENT_SECRET = os.getenv("FRANCE_TRAVAIL_CLIENT_SECRET", "").strip()

# ─── Repo Hugging Face où sont hébergés les assets ───────────────────
HF_REPO_ID = os.getenv("HF_REPO_ID", "gabinsrg/mia-france-travail").strip()

# ─── Modèles ─────────────────────────────────────────────────────────
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
CEREBRAS_MODEL = "gpt-oss-120b"

# ─── Paramètres pipeline matching (Phase 3c) ─────────────────────────
TOP_K_SEMANTIC = 100
TOP_K_FINAL = 10
SLEEP_BETWEEN_LLM_CALLS = 2.5  # rate limit Cerebras free tier

# ─── Métadonnées ─────────────────────────────────────────────────────
APP_NAME = "JoBFlow"
APP_TAGLINE = "Matching d'offres + génération CV/LM"


def has_cerebras_key() -> bool:
    return bool(CEREBRAS_API_KEY)


def has_france_travail_keys() -> bool:
    return bool(FRANCE_TRAVAIL_CLIENT_ID and FRANCE_TRAVAIL_CLIENT_SECRET)


def has_hf_repo() -> bool:
    return bool(HF_REPO_ID)


def assets_present() -> bool:
    return all(p.exists() for p in ASSETS_FILES)


def missing_assets() -> list[Path]:
    return [p for p in ASSETS_FILES if not p.exists()]
