"""Page Profil — Phase 3b interactive en Streamlit."""
import json

import streamlit as st

from jobflow_core import config, profile as core_profile
from pages._styles import header


header()
st.markdown("## Profil candidat")
st.caption("Charge ton CV, dialogue avec l'IA, et obtiens un profil enrichi prêt pour le matching.")

if not config.has_cerebras_key():
    st.error("Configure ta clé Cerebras dans **Réglages** avant de continuer.")
    st.stop()


# ─── État de la page ────────────────────────────────────────────────
if "profile_v1" not in st.session_state:
    st.session_state.profile_v1 = None
if "profile_final" not in st.session_state:
    # Charge depuis disque si existe
    st.session_state.profile_final = core_profile.load_profile()


# ─── Étape 1 : upload CV ────────────────────────────────────────────
st.markdown("### 1. Charge ton CV (PDF)")

col1, col2 = st.columns([3, 2])
with col1:
    uploaded = st.file_uploader("Glisse ton CV ici", type=["pdf"], label_visibility="collapsed")
    if uploaded:
        config.CV_PDF_PATH.write_bytes(uploaded.getbuffer())
        st.success(f"CV sauvegardé ({len(uploaded.getbuffer()) // 1024} Ko).")
with col2:
    if config.CV_PDF_PATH.exists():
        st.info(f"CV actuel : `{config.CV_PDF_PATH.name}` "
                f"({config.CV_PDF_PATH.stat().st_size // 1024} Ko)")


# ─── Étape 2 : analyse du CV (pass 1) ───────────────────────────────
st.markdown("### 2. Analyse du CV")

if config.CV_PDF_PATH.exists():
    col_a, col_b = st.columns([1, 3])
    with col_a:
        run_pass1 = st.button("Analyser le CV", type="primary", use_container_width=True)
    if run_pass1:
        with st.spinner("Lecture du PDF + analyse par Cerebras…"):
            try:
                cv_text = core_profile.extract_cv_text(config.CV_PDF_PATH)
                st.session_state.profile_v1 = core_profile.pass1_analyze_cv(cv_text)
                st.session_state.profile_final = None  # invalide l'ancien profil final
                st.success("Analyse terminée.")
            except Exception as e:
                st.error(f"Erreur : {e}")
else:
    st.warning("Charge d'abord un CV.")


# ─── Étape 3 : dialogue Q/R ─────────────────────────────────────────
if st.session_state.profile_v1:
    st.markdown("### 3. Réponds à quelques questions")
    st.caption("L'IA a généré ces questions pour combler ce qu'elle n'a pas pu déduire du CV.")

    v1 = st.session_state.profile_v1
    questions = v1.get("questions_pour_le_candidat", [])

    if "answers" not in st.session_state:
        st.session_state.answers = {q["id"]: "" for q in questions}

    with st.form("qa_form"):
        for q in questions:
            qid = q.get("id", "?")
            qtxt = q.get("question", "")
            pourquoi = q.get("pourquoi", "")
            st.markdown(f"**Q{qid}. {qtxt}**")
            if pourquoi:
                st.caption(pourquoi)
            st.session_state.answers[qid] = st.text_area(
                label=f"Réponse {qid}",
                value=st.session_state.answers.get(qid, ""),
                height=90,
                key=f"ans_{qid}",
                label_visibility="collapsed",
            )

        submit = st.form_submit_button("Générer le profil enrichi", type="primary")

    if submit:
        unanswered = [k for k, v in st.session_state.answers.items() if not v.strip()]
        if unanswered:
            st.warning(f"Questions non remplies : {unanswered}. "
                       "Tu peux soumettre quand même mais le profil sera moins précis.")
        with st.spinner("Génération du profil final…"):
            try:
                final = core_profile.pass2_enrich_with_answers(v1, st.session_state.answers)
                core_profile.save_profile(final)
                st.session_state.profile_final = final
                # Invalide le top10 existant (différent profil)
                if config.TOP10_PATH.exists():
                    config.TOP10_PATH.unlink()
                st.success("Profil enrichi sauvegardé ! Tu peux passer à l'onglet Matching.")
            except Exception as e:
                st.error(f"Erreur : {e}")


# ─── Étape 4 : aperçu du profil final ───────────────────────────────
if st.session_state.profile_final:
    st.markdown("### 4. Profil enrichi")
    final = st.session_state.profile_final

    info = final.get("informations", {})
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Nom",          info.get("nom") or "—")
    with col2: st.metric("Localisation", info.get("localisation") or "—")
    with col3:
        prefs = final.get("preferences", {})
        salaire = prefs.get("salaire_minimum_annuel_brut_euros", 0)
        st.metric("Salaire min", f"{salaire:,} €" if salaire else "—")

    with st.expander("Synthèse pour matching", expanded=True):
        st.write(final.get("synthese_pour_matching", "—"))

    with st.expander("Compétences déduites"):
        comp = final.get("competences_techniques_deduites", [])
        st.write(", ".join(comp) if comp else "—")

    with st.expander("JSON complet", expanded=False):
        st.json(final)

    st.download_button(
        "Télécharger profil_enrichi.json",
        data=json.dumps(final, ensure_ascii=False, indent=2),
        file_name="profil_enrichi.json",
        mime="application/json",
    )
