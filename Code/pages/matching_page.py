"""Page Matching — Phase 3c en Streamlit avec affichage Top 10."""
import streamlit as st

from jobflow_core import config, matching as core_matching, profile as core_profile
from pages._styles import header, pill, score_class, safe_html


header()
st.markdown("## Matching offres")
st.caption("Compare ton profil aux 560 000+ offres et obtiens un Top 10 expliqué.")


# ─── Pré-requis ────────────────────────────────────────────────────
profil = core_profile.load_profile()

issues = []
if not config.has_cerebras_key():
    issues.append("Clé Cerebras manquante (Réglages).")
if not profil:
    issues.append("Profil enrichi absent — fais d'abord la page Profil.")
if not config.assets_present():
    issues.append("Assets manquants — télécharge-les depuis Réglages.")

if issues:
    for i in issues:
        st.error(i)
    st.stop()


# ─── Lancer le matching ────────────────────────────────────────────
existing_top10 = core_matching.load_top10()
state_file = core_matching.profile_state_path(profil)
already_analysed = 0
if state_file.exists():
    try:
        import json
        already_analysed = len(json.loads(state_file.read_text(encoding="utf-8")))
    except Exception:
        already_analysed = 0

col_info, col_action = st.columns([3, 1.2])
with col_info:
    if existing_top10:
        st.markdown(
            f"{pill(f'Top 10 existant : {len(existing_top10)} offres', 'ok')} "
            f"{pill(f'Cache analyses : {already_analysed}/100', 'info')}",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"{pill('Pas encore matché', 'warn')} "
            f"{pill(f'Cache analyses : {already_analysed}/100', 'info')}",
            unsafe_allow_html=True,
        )
    st.caption(
        "Le matching analyse les 100 offres les plus pertinentes via Cerebras. "
        "Compte ~5 min (~2,5 s par offre). Le pipeline est reprenable : "
        "si tu interromps, il reprendra où il s'est arrêté."
    )

with col_action:
    run_label = "Reprendre le matching" if 0 < already_analysed < 100 else "Lancer le matching"
    run = st.button(run_label, type="primary", use_container_width=True)


if run:
    progress_bar = st.progress(0.0)
    status_box = st.empty()

    def on_progress(i: int, total: int, msg: str):
        progress_bar.progress(i / total)
        status_box.markdown(f"`{i}/{total}` · {msg}")

    try:
        with st.spinner("Pipeline en cours…"):
            top10 = core_matching.run_full_matching(profil, progress_cb=on_progress)
        progress_bar.progress(1.0)
        status_box.success(f"Terminé — {len(top10)} offres dans le Top final.")
        st.rerun()
    except Exception as e:
        status_box.error(f"Erreur : {e}")


# ─── Affichage du Top 10 ───────────────────────────────────────────
top10 = core_matching.load_top10()
if top10:
    st.markdown("---")
    st.markdown(f"### Top {len(top10)} offres")

    for i, offre in enumerate(top10):
        score = offre.get("score_final", 0)
        klass = score_class(score)

        # Toutes les valeurs dynamiques passent par safe_html pour éviter que
        # leurs sauts de ligne ou caractères spéciaux cassent le rendu Streamlit.
        fit_level   = safe_html(offre.get("fit_level", "—"))
        intitule    = safe_html(offre.get("intitule", "—"), max_len=140)
        entreprise  = safe_html(offre.get("entreprise", "—"))
        ville       = safe_html(offre.get("ville", "—"))
        contrat     = safe_html(offre.get("contrat", "—"))
        salaire     = safe_html(offre.get("salaire", ""))
        raisonnement = safe_html(offre.get("raisonnement", ""))
        url = offre.get("url", "")

        # Bloc salaire optionnel
        salaire_html = f" · 💰 {salaire}" if salaire else ""

        # Lien "Voir l'offre" — on échappe l'URL aussi par sécurité
        url_html = ""
        if url:
            safe_url = safe_html(url)
            url_html = (
                f'<a href="{safe_url}" target="_blank" '
                f'style="color:var(--mia-text-dim);text-decoration:underline;">'
                f"Voir l'offre</a>"
            )

        # Points forts / faibles — construits sans sauts de ligne entre les divs
        pf_html = "".join(
            f'<div class="offre-pf">+ {safe_html(pf)}</div>'
            for pf in offre.get("points_forts", [])[:3]
        )
        pw_html = "".join(
            f'<div class="offre-pw">− {safe_html(pw)}</div>'
            for pw in offre.get("points_faibles", [])[:2]
        )

        # IMPORTANT : on construit le HTML sur UNE SEULE LIGNE logique pour éviter
        # que markdown ne se perde dans l'indentation et casse le rendu.
        # On colle tout avec des concaténations sans saut de ligne interne.
        card_html = (
            f'<div class="offre-card">'
            f'<div class="offre-rank">#{i+1} · {fit_level}</div>'
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:1rem;">'
            f'<div style="flex:1;">'
            f'<h3 class="offre-title">{intitule}</h3>'
            f'<div class="offre-meta">🏢 {entreprise} · 📍 {ville} · 📄 {contrat}{salaire_html}</div>'
            f'</div>'
            f'<div><span class="offre-score {klass}">{score}/100</span></div>'
            f'</div>'
            f'<p class="offre-reasoning">{raisonnement}</p>'
            f'{pf_html}'
            f'{pw_html}'
            f'<div style="margin-top:0.5rem;font-size:0.8rem;">{url_html}</div>'
            f'</div>'
        )

        st.markdown(card_html, unsafe_allow_html=True)

        # Boutons d'action sous chaque carte
        bcol1, bcol2, bcol3 = st.columns([1, 1, 4])
        with bcol1:
            if st.button("Générer CV", key=f"cv_{i}", use_container_width=True):
                st.session_state.selected_offre_idx = i
                st.switch_page("pages/cv_page.py")
        with bcol2:
            if st.button("Lettre", key=f"lm_{i}", use_container_width=True):
                st.session_state.selected_offre_idx = i
                st.switch_page("pages/lm_page.py")
else:
    st.info("Lance le matching pour voir tes Top 10 offres ici.")
