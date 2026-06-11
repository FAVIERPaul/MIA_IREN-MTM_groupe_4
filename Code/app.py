"""JoBFlow — point d'entrée Streamlit.

Lance avec :
    streamlit run app.py
"""
import streamlit as st

from jobflow_core import config
from pages import _styles


st.set_page_config(
    page_title=f"{config.APP_NAME} — recherche d'emploi assistée",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

_styles.inject()


# ─── Sidebar : statut global de la config ────────────────────────────
def render_sidebar_status():
    with st.sidebar:
        _styles.header()

        st.markdown("### État")
        # Clé Cerebras
        if config.has_cerebras_key():
            st.markdown(_styles.pill("Cerebras OK", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_styles.pill("Clé Cerebras manquante", "error"), unsafe_allow_html=True)

        # Assets
        if config.assets_present():
            st.markdown(_styles.pill("Base offres OK", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_styles.pill("Assets à télécharger", "warn"), unsafe_allow_html=True)

        # Profil
        if config.PROFIL_PATH.exists():
            st.markdown(_styles.pill("Profil chargé", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_styles.pill("Pas de profil", "warn"), unsafe_allow_html=True)

        # Top 10
        if config.TOP10_PATH.exists():
            st.markdown(_styles.pill("Top 10 prêt", "ok"), unsafe_allow_html=True)
        else:
            st.markdown(_styles.pill("Pas de matching", "warn"), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(
            f"<p style='font-size:0.75rem;color:var(--mia-text-dim);margin:0;'>"
            f"v{__import__('jobflow_core').__version__} · data : <code>{config.DATA_DIR}</code></p>",
            unsafe_allow_html=True,
        )


# ─── Pages (st.navigation) ───────────────────────────────────────────
profile_page  = st.Page("pages/profile_page.py",   title="Profil",     icon="👤", default=True)
matching_page = st.Page("pages/matching_page.py",  title="Matching",   icon="🎯")
cv_page       = st.Page("pages/cv_page.py",        title="CV",         icon="📄")
lm_page       = st.Page("pages/lm_page.py",        title="Lettre",     icon="✉️")
settings_page = st.Page("pages/settings_page.py",  title="Réglages",   icon="⚙️")

nav = st.navigation([profile_page, matching_page, cv_page, lm_page, settings_page])

render_sidebar_status()
nav.run()
