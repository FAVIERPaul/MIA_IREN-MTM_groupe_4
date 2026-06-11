"""Gestion des assets lourds (DB SQLite, embeddings) hébergés sur Hugging Face Hub."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from huggingface_hub import hf_hub_download, HfApi

from . import config


# Mapping nom logique -> (filename dans le repo HF, path local cible)
ASSET_MAP = {
    "db": ("offres.db", config.DB_PATH),
    "embeddings": ("offres_embeddings.npy", config.EMB_PATH),
    "ids": ("offres_ids.npy", config.IDS_PATH),
}


def get_remote_metadata() -> dict | None:
    """Retourne la liste des fichiers du repo HF avec leur taille et date.
    None si pas de repo configuré ou erreur."""
    if not config.has_hf_repo():
        return None
    try:
        api = HfApi()
        info = api.repo_info(repo_id=config.HF_REPO_ID, repo_type="dataset")
        files = {}
        for sibling in info.siblings:
            files[sibling.rfilename] = {
                "size": getattr(sibling, "size", None),
                "blob_id": getattr(sibling, "blob_id", None),
            }
        return {"files": files, "last_modified": info.lastModified}
    except Exception:
        return None


def download_one(
    asset_key: str,
    progress_cb: Callable[[str, float], None] | None = None,
) -> Path:
    """Télécharge un asset depuis HF Hub et le copie au bon endroit."""
    if not config.has_hf_repo():
        raise RuntimeError(
            "Aucun repo Hugging Face configuré (HF_REPO_ID dans .env). "
            "Voir le README pour créer ton dataset."
        )

    filename, target_path = ASSET_MAP[asset_key]
    if progress_cb:
        progress_cb(f"Téléchargement de {filename}…", 0.0)

    # huggingface_hub télécharge dans son cache, on copie ensuite à l'emplacement attendu
    cache_path = hf_hub_download(
        repo_id=config.HF_REPO_ID,
        filename=filename,
        repo_type="dataset",
    )

    if progress_cb:
        progress_cb(f"Copie de {filename}…", 0.9)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cache_path, target_path)

    if progress_cb:
        progress_cb(f"{filename} prêt", 1.0)

    return target_path


def download_all_missing(progress_cb: Callable[[str, float], None] | None = None) -> list[Path]:
    """Télécharge tous les assets manquants. Retourne la liste de ce qui a été téléchargé."""
    downloaded = []
    missing = config.missing_assets()
    if not missing:
        return downloaded

    # Mapping reverse pour trouver la clé asset à partir du path
    path_to_key = {target: key for key, (_, target) in ASSET_MAP.items()}

    for i, missing_path in enumerate(missing):
        key = path_to_key.get(missing_path)
        if key:
            inner_cb = None
            if progress_cb:
                base = i / len(missing)
                step = 1 / len(missing)
                inner_cb = lambda msg, pct, b=base, s=step: progress_cb(msg, b + pct * s)
            download_one(key, inner_cb)
            downloaded.append(missing_path)
    return downloaded


def total_assets_size_bytes() -> int:
    """Taille totale des assets locaux (0 si absents)."""
    return sum(p.stat().st_size for p in config.ASSETS_FILES if p.exists())


def format_size(n: int) -> str:
    """Formate une taille en bytes en string lisible."""
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} To"
