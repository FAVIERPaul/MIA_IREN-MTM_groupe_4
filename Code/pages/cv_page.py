"""Page CV — génère un CV adapté à une offre du Top 10."""
import streamlit as st

from jobflow_core import config, cv_generator as cvg, matching as core_matching, profile as core_profile
from pages._styles import header, pill


header()
st.markdown("## Génération CV")
st.caption("Sélectionne une offre du Top 10, génère un CV LaTeX adapté.")


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
chosen_label = st.selectbox(
    "Offre cible",
    options,
    index=default_idx,
    key="cv_offre_choice",
)
offre_idx = options.index(chosen_label)
offre = top10[offre_idx]

with st.expander("Détails de l'offre"):
    st.markdown(f"**{offre.get('intitule')}** chez **{offre.get('entreprise')}**")
    st.caption(f"{offre.get('ville', '')} · {offre.get('contrat', '')} · {offre.get('salaire', '')}")
    st.write(offre.get("description", "")[:1500] + "…")


# ─── pdflatex check ────────────────────────────────────────────────
if not cvg.has_pdflatex():
    st.markdown(
        pill("pdflatex non détecté — tu auras seulement le .tex (à compiler ailleurs, ex Overleaf)", "warn"),
        unsafe_allow_html=True,
    )


# ─── Génération ────────────────────────────────────────────────────
st.markdown("---")
run = st.button("Générer le CV", type="primary")

if run:
    status_box = st.empty()
    progress_bar = st.progress(0.0)
    steps = ["Lecture du CV PDF", "Extraction mots-clés ATS", "Audit profil vs mots-clés",
             "Parsing structuré du CV", "Génération du CV adapté",
             "Construction LaTeX", "Compilation PDF"]
    completed = {"n": 0}

    def on_progress(msg: str):
        completed["n"] += 1
        progress_bar.progress(min(completed["n"] / len(steps), 1.0))
        status_box.markdown(f"`{completed['n']}/{len(steps)}` · {msg}")

    try:
        with st.spinner("Génération en cours… ~30s"):
            result = cvg.generate_cv_for_offre(
                offre=offre,
                profil=profil,
                cv_pdf_path=config.CV_PDF_PATH,
                progress_cb=on_progress,
            )
        progress_bar.progress(1.0)
        st.session_state.last_cv_result = result
    except Exception as e:
        status_box.error(f"Erreur : {e}")


# ─── Affichage du résultat ────────────────────────────────────────
result = st.session_state.get("last_cv_result")
if result:
    st.markdown("---")
    st.markdown("### Résultat")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Statut", "OK" if result.get("pdf_path") else "TEX seulement")
    with col2:
        st.metric("Pages PDF", result.get("nb_pages") or "—")
    with col3:
        st.metric("Mots-clés top 5", len(result.get("keywords", {}).get("mots_cles_critiques_top5", [])))

    # Téléchargements
    cdl1, cdl2 = st.columns(2)
    with cdl1:
        tex_bytes = result["tex_path"].read_bytes()
        st.download_button(
            "Télécharger cv.tex",
            data=tex_bytes,
            file_name="cv.tex",
            mime="text/plain",
            use_container_width=True,
        )
    with cdl2:
        if result.get("pdf_path") and result["pdf_path"].exists():
            pdf_bytes = result["pdf_path"].read_bytes()
            st.download_button(
                "Télécharger cv.pdf",
                data=pdf_bytes,
                file_name="cv.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.button("PDF indisponible (pas de pdflatex)", disabled=True, use_container_width=True)

    # Mots-clés et audit
    with st.expander("Mots-clés ATS extraits de l'offre"):
        kw = result.get("keywords", {})
        st.markdown("**Top 5 critiques :** " + ", ".join(kw.get("mots_cles_critiques_top5", [])))
        st.markdown("**Hard skills :** " + ", ".join(kw.get("hard_skills", [])))
        st.markdown("**Soft skills :** " + ", ".join(kw.get("soft_skills", [])))

    with st.expander("Audit profil vs mots-clés"):
        audit = result.get("audit", {}).get("recommandations", {})
        st.markdown("**À mettre en avant :** " + ", ".join(audit.get("a_mettre_en_avant", [])))
        st.markdown("**À intégrer naturellement :** " + ", ".join(audit.get("a_integrer_naturellement", [])))
        st.markdown("**Gaps honnêtes :** " + ", ".join(audit.get("gaps_honnetes", [])))

    with st.expander("Données structurées du CV"):
        st.json(result.get("cv_data", {}))

    st.caption(f"Fichiers sauvegardés dans : `{result['out_dir']}`")
