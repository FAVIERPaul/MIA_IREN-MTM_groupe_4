"""Script CLI — Publication des assets sur Hugging Face Hub.

Pré-requis :
1. Compte HuggingFace : https://huggingface.co/join
2. Token "write" : https://huggingface.co/settings/tokens
3. Login local :    huggingface-cli login   (colle ton token)
4. Crée le dataset : huggingface-cli repo create mia-france-travail --type dataset
   (ou via UI : https://huggingface.co/new-dataset)

Lance :
    python -m scripts.publish_to_hf
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from huggingface_hub import HfApi, login

from jobflow_core import config


REPO_ID = config.HF_REPO_ID

FILES_TO_PUSH = [
    (config.DB_PATH,  "offres.db"),
    (config.EMB_PATH, "offres_embeddings.npy"),
    (config.IDS_PATH, "offres_ids.npy"),
]


def fmt_size(n: int) -> str:
    for u in ("o", "Ko", "Mo", "Go"):
        if n < 1024: return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} To"


def main():
    if not REPO_ID:
        sys.exit(
            "HF_REPO_ID non défini dans .env (ex: HF_REPO_ID=tonpseudo/mia-france-travail)"
        )

    missing = [src for src, _ in FILES_TO_PUSH if not src.exists()]
    if missing:
        sys.exit(f"Fichier(s) absent(s) : {[str(p) for p in missing]}")

    api = HfApi()

    # Vérifie auth
    try:
        whoami = api.whoami()
        print(f"✅ Connecté en tant que : {whoami['name']}")
    except Exception:
        print("⚠️ Pas connecté à HF. Lance : huggingface-cli login")
        sys.exit(1)

    # Vérifie/crée le repo
    try:
        api.repo_info(repo_id=REPO_ID, repo_type="dataset")
        print(f"✅ Repo trouvé : {REPO_ID}")
    except Exception:
        print(f"📦 Création du repo {REPO_ID}…")
        api.create_repo(repo_id=REPO_ID, repo_type="dataset", exist_ok=True)

    print(f"\n📤 Upload de {len(FILES_TO_PUSH)} fichiers vers {REPO_ID}\n")
    for src, target_name in FILES_TO_PUSH:
        size = src.stat().st_size
        print(f"  · {target_name} ({fmt_size(size)})…", flush=True)
        t0 = time.time()
        api.upload_file(
            path_or_fileobj=str(src),
            path_in_repo=target_name,
            repo_id=REPO_ID,
            repo_type="dataset",
            commit_message=f"Update {target_name}",
        )
        print(f"    ✅ {time.time() - t0:.0f}s")

    print(f"\n🎉 Tout est en ligne : https://huggingface.co/datasets/{REPO_ID}")


if __name__ == "__main__":
    main()
