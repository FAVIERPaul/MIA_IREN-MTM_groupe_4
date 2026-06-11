"""Page Réglages — clés API, repo HF, téléchargement des assets."""
from pathlib import Path

import streamlit as st

from jobflow_core import assets, config
from pages._styles import header, pill


header()
st.markdown("## Réglages")
st.caption("Clés API, base de données, gestion locale.")


# ─── Section 1 : clés API ──────────────────────────────────────────
st.markdown("### Clés API")
st.caption(
    "Les clés sont lues depuis le fichier `.env` à la racine du projet. "
    "Tu peux les modifier ci-dessous ; ça créera/écrasera `.env` au prochain redémarrage."
)

env_path = Path(__file__).resolve().parent.parent / ".env"
existing_env = {}
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            existing_env[k.strip()] = v.strip().strip('"').strip("'")

with st.form("api_keys_form"):
    cere = st.text_input(
        "CEREBRAS_API_KEY",
        value=existing_env.get("CEREBRAS_API_KEY", config.CEREBRAS_API_KEY or ""),
        type="password",
        help="Gratuit sur https://cloud.cerebras.ai (1M tokens/jour)",
    )
    hf_repo = st.text_input(
        "HF_REPO_ID",
        value=existing_env.get("HF_REPO_ID", config.HF_REPO_ID or ""),
        help="Défaut : gabinsrg/mia-france-travail (public, pas besoin de changer)",
    )

    submitted = st.form_submit_button("Sauvegarder", type="primary")

if submitted:
    lines = []
    if cere:      lines.append(f'CEREBRAS_API_KEY="{cere}"')
    if hf_repo:   lines.append(f'HF_REPO_ID="{hf_repo}"')
    # Préserve les clés France Travail si elles existent déjà
    ft_id = existing_env.get("FRANCE_TRAVAIL_CLIENT_ID", "")
    ft_secret = existing_env.get("FRANCE_TRAVAIL_CLIENT_SECRET", "")
    if ft_id:     lines.append(f'FRANCE_TRAVAIL_CLIENT_ID="{ft_id}"')
    if ft_secret: lines.append(f'FRANCE_TRAVAIL_CLIENT_SECRET="{ft_secret}"')
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    st.success(f"Sauvegardé dans `{env_path}`. Redémarre Streamlit pour appliquer.")


# ─── Section 2 : assets ────────────────────────────────────────────
st.markdown("---")
st.markdown("### Base d'offres (assets Hugging Face)")

local_size = assets.total_assets_size_bytes()
present = config.assets_present()
missing = config.missing_assets()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("État local", "Complet" if present else f"{3 - len(missing)}/3 fichiers")
with col2:
    st.metric("Taille locale", assets.format_size(local_size))
with col3:
    if config.has_hf_repo():
        st.metric("Repo HF", config.HF_REPO_ID)
    else:
        st.metric("Repo HF", "Non configuré")

if missing:
    st.warning("Fichiers manquants : " + ", ".join(p.name for p in missing))

if config.has_hf_repo():
    cdl, _, _ = st.columns([2, 1, 1])
    with cdl:
        if st.button(
            "Télécharger / mettre à jour les assets",
            type="primary",
            use_container_width=True,
            disabled=present,
        ):
            progress = st.progress(0.0)
            status = st.empty()

            def cb(msg: str, pct: float):
                progress.progress(min(pct, 1.0))
                status.markdown(f"`{int(pct*100)}%` · {msg}")

            try:
                with st.spinner("Téléchargement depuis Hugging Face…"):
                    downloaded = assets.download_all_missing(progress_cb=cb)
                progress.progress(1.0)
                status.success(f"{len(downloaded)} fichier(s) téléchargé(s).")
                st.rerun()
            except Exception as e:
                status.error(f"Erreur : {e}")

    # Reset
    with st.expander("Actions avancées"):
        if st.button("Supprimer les assets locaux (forcer re-téléchargement)"):
            for p in config.ASSETS_FILES:
                if p.exists():
                    p.unlink()
            st.success("Assets locaux supprimés.")
            st.rerun()
else:
    st.info(
        "Pour télécharger les assets, configure `HF_REPO_ID` ci-dessus puis redémarre Streamlit. "
        "Voir le README pour créer ton propre dataset Hugging Face."
    )


# ─── Section 3 : chemins ───────────────────────────────────────────
st.markdown("---")
st.markdown("### Chemins locaux")

st.code(
    f"""
DATA_DIR        = {config.DATA_DIR}
ASSETS_DIR      = {config.ASSETS_DIR}
USER_DIR        = {config.USER_DIR}
OUTPUTS_CV_DIR  = {config.OUTPUTS_CV_DIR}
OUTPUTS_LM_DIR  = {config.OUTPUTS_LM_DIR}
LM_EXAMPLES_DIR = {config.LM_EXAMPLES_DIR}
""".strip(),
    language="text",
)


# ─── Section 4 : reset utilisateur ─────────────────────────────────
st.markdown("---")
st.markdown("### Reset")
st.caption("Pour repartir d'un profil vierge (utile pour tester un autre candidat).")

if st.button("Effacer profil + Top 10 + state matching"):
    for p in (config.PROFIL_PATH, config.TOP10_PATH):
        if p.exists():
            p.unlink()
    for f in config.STATE_DIR.glob("*.json"):
        f.unlink()
    st.success("Reset effectué. Recharge la page.")
