"""Page Lettre de motivation — pipeline 100% Cerebras (pas d'aller-retour manuel)."""
import streamlit as st

from jobflow_core import config, lm_generator as lmg, matching as core_matching, profile as core_profile
from pages._styles import header, pill


header()
st.markdown("## Lettre de motivation")
st.caption("Génération automatique avec Cerebras + few-shot de tes LM existantes.")


# ─── Pré-requis ────────────────────────────────────────────────────
profil = core_profile.load_profile()
top10  = core_matching.load_top10()

issues = []
if not config.has_cerebras_key():
    issues.append("Clé Cerebras manquante (Réglages).")
if not profil:
    issues.append("Profil enrichi absent (page Profil).")
if not top10:
    issues.append("Top 10 absent (page Matching).")
if not config.CV_PDF_PATH.exists():
    issues.append("CV PDF absent (page Profil).")

if issues:
    for i in issues:
        st.error(i)
    st.stop()


# ─── Sélection de l'offre ──────────────────────────────────────────
default_idx = st.session_state.get("selected_offre_idx", 0)
default_idx = max(0, min(default_idx, len(top10) - 1))

options = [
    f"#{i+1} · [{o.get('score_final', 0)}/100] {o.get('intitule', '')[:55]} — {o.get('entreprise', '')[:30]}"
    for i, o in enumerate(top10)
]
chosen_label = st.selectbox("Offre cible", options, index=default_idx, key="lm_offre_choice")
offre_idx = options.index(chosen_label)
offre = top10[offre_idx]


# ─── Sidebar de cette page : identité candidat + sources web ───────
with st.expander("Identité signature LM", expanded=False):
    info = profil.get("informations", {})
    col1, col2 = st.columns(2)
    with col1:
        nom = st.text_input("Nom complet", value=info.get("nom", ""))
        tel = st.text_input("Téléphone",   value=info.get("telephone", ""))
    with col2:
        adresse = st.text_input("Adresse",  value=info.get("localisation", ""))
        email   = st.text_input("Email",    value=info.get("email", ""))

candidat = {"nom_complet": nom, "adresse": adresse, "telephone": tel, "email": email}

with st.expander("Sources web (optionnel) — pour enrichir la fiche entreprise"):
    st.caption("Si vide, la fiche entreprise sera basée uniquement sur la description de l'offre.")
    website = st.text_input("URL site corporate", placeholder="https://www.example.com")
    articles = st.text_area("URLs articles (1 par ligne)", height=80, placeholder="https://...")

# Few-shot
lm_files = sorted(config.LM_EXAMPLES_DIR.glob("*.docx"))
if lm_files:
    st.markdown(pill(f"{len(lm_files)} LM exemples chargées (few-shot)", "ok"), unsafe_allow_html=True)
else:
    st.markdown(
        pill(f"Aucune LM exemple dans {config.LM_EXAMPLES_DIR}", "warn"),
        unsafe_allow_html=True,
    )
    st.caption(
        "Pour une LM qui reproduit fidèlement ton style, ajoute 2-3 LM "
        f"`.docx` dans `{config.LM_EXAMPLES_DIR}` (créé automatiquement)."
    )


# ─── Génération ────────────────────────────────────────────────────
st.markdown("---")
run = st.button("Générer la lettre", type="primary")

if run:
    if not nom or not email:
        st.error("Renseigne au moins le nom et l'email.")
        st.stop()

    status_box = st.empty()
    progress_bar = st.progress(0.0)
    steps = ["Fiche entreprise", "Angles stratégiques", "Rédaction LM", "Auto-critique", "Export .docx"]
    completed = {"n": 0}

    def on_progress(msg: str):
        completed["n"] += 1
        progress_bar.progress(min(completed["n"] / len(steps), 1.0))
        status_box.markdown(f"`{completed['n']}/{len(steps)}` · {msg}")

    try:
        # Fetch des URLs optionnel
        website_text = ""
        articles_text = ""
        if website.strip():
            try:
                import requests
                from bs4 import BeautifulSoup
                r = requests.get(website.strip(), timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                soup = BeautifulSoup(r.text, "html.parser")
                for t in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
                    t.decompose()
                website_text = soup.get_text(separator=" ", strip=True)
            except Exception as e:
                st.warning(f"Échec fetch site web ({e}). On continue sans.")

        with st.spinner("Génération en cours… ~30s"):
            result = lmg.generate_lm_for_offre(
                offre=offre,
                profil=profil,
                candidat=candidat,
                cv_pdf_path=config.CV_PDF_PATH,
                website_text=website_text,
                articles_text=articles_text,
                progress_cb=on_progress,
            )
        progress_bar.progress(1.0)
        st.session_state.last_lm_result = result
    except Exception as e:
        status_box.error(f"Erreur : {e}")


# ─── Affichage du résultat ────────────────────────────────────────
result = st.session_state.get("last_lm_result")
if result:
    st.markdown("---")
    st.markdown("### Lettre générée")

    # Critique en tête
    critique = result.get("critique")
    if critique:
        col1, col2, col3 = st.columns(3)
        with col1: st.metric("Score global",  f"{critique.get('score_global', 0)}/10")
        with col2: st.metric("Nb mots",       critique.get("axes", {}).get("longueur", {}).get("nb_mots", "—"))
        with col3:
            verdict = critique.get("verdict_final", "—")
            variant = "ok" if verdict == "GO" else "warn"
            st.markdown(f"<br>{pill(verdict, variant)}", unsafe_allow_html=True)

    # Édition inline
    edited = st.text_area(
        "Tu peux éditer avant de télécharger :",
        value=result["lm_text"],
        height=440,
        key="lm_edited",
    )

    cdl1, cdl2 = st.columns(2)
    with cdl1:
        st.download_button(
            "Télécharger .txt",
            data=edited,
            file_name="lettre_motivation.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with cdl2:
        # Régénère le docx si l'utilisateur a édité
        try:
            from jobflow_core.lm_generator import export_to_docx
            updated_docx = result["docx_path"]
            if edited != result["lm_text"]:
                # Reconstruire le .docx avec le texte édité
                lm_files = sorted(config.LM_EXAMPLES_DIR.glob("*.docx"))
                template = lm_files[0] if lm_files else None
                export_to_docx(edited, updated_docx, template)
            docx_bytes = updated_docx.read_bytes()
            st.download_button(
                "Télécharger .docx",
                data=docx_bytes,
                file_name="lettre_motivation.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True,
            )
        except Exception as e:
            st.error(f"Erreur export docx : {e}")

    # Détails
    with st.expander("Fiche entreprise utilisée"):
        st.json(result.get("fiche", {}))
    with st.expander("Angles stratégiques"):
        st.json(result.get("angles", {}))
    if critique:
        with st.expander("Critique détaillée"):
            st.json(critique)

    st.caption(f"Fichiers sauvegardés dans : `{result['out_dir']}`")
