"""CSS custom injecté dans Streamlit pour un look propre, sobre, moderne.

Note : les classes CSS conservent le préfixe 'mia-' pour éviter de casser
les sélecteurs existants (le préfixe est purement interne, invisible à l'utilisateur).
"""
from __future__ import annotations

import html as _html

import streamlit as st


CUSTOM_CSS = """
<style>
  /* ─── Variables ─────────────────────────────────────────────────── */
  :root {
    --mia-bg:        #0F1117;
    --mia-surface:   #181B25;
    --mia-surface-2: #232733;
    --mia-border:    #2A2F3D;
    --mia-text:      #E8EAF0;
    --mia-text-dim:  #9097A8;
    --mia-accent:    #7C5CFF;
    --mia-accent-2:  #5EE6B8;
    --mia-warn:      #FFB547;
    --mia-error:     #FF6B6B;
  }

  /* ─── Reset général ─────────────────────────────────────────────── */
  .stApp { background: var(--mia-bg) !important; }
  section[data-testid="stMain"] { background: var(--mia-bg); }
  .block-container { padding-top: 2rem !important; max-width: 1180px !important; }

  /* Sidebar */
  section[data-testid="stSidebar"] {
    background: #0A0B11 !important;
    border-right: 1px solid var(--mia-border);
    min-width: 250px !important;
  }
  section[data-testid="stSidebar"] .stMarkdown,
  section[data-testid="stSidebar"] label { color: var(--mia-text); }

  /* Garantit que le bouton "rouvrir la sidebar" reste visible en haut à gauche
     si jamais Streamlit la replie. Sans ça, on peut se retrouver coincé. */
  button[data-testid="collapsedControl"],
  button[data-testid="stSidebarCollapseButton"],
  button[kind="header"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    color: var(--mia-text) !important;
    z-index: 999 !important;
  }

  /* ─── Typo ──────────────────────────────────────────────────────── */
  h1, h2, h3, h4 {
    color: var(--mia-text) !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
  }
  h1 { font-size: 2rem !important; margin-bottom: 0.4rem !important; }
  h2 { font-size: 1.35rem !important; margin-top: 1.8rem !important; }
  h3 { font-size: 1.1rem !important; }
  p, li, span, label { color: var(--mia-text); }

  /* ─── Header JoBFlow ────────────────────────────────────────────────── */
  .mia-header {
    display: flex; align-items: center; gap: 0.85rem;
    padding-bottom: 1.2rem; margin-bottom: 1.5rem;
    border-bottom: 1px solid var(--mia-border);
  }
  .mia-logo {
    width: 42px; height: 42px; border-radius: 11px;
    background: linear-gradient(135deg, var(--mia-accent), var(--mia-accent-2));
    display: flex; align-items: center; justify-content: center;
    font-weight: 900; font-size: 1.3rem; color: #0A0B11;
    box-shadow: 0 4px 18px rgba(124, 92, 255, 0.35);
  }
  .mia-title { font-size: 1.5rem; font-weight: 800; color: var(--mia-text); margin: 0; }
  .mia-subtitle { font-size: 0.82rem; color: var(--mia-text-dim); margin: 0; }

  /* ─── Cartes ───────────────────────────────────────────────────── */
  .mia-card {
    background: var(--mia-surface);
    border: 1px solid var(--mia-border);
    border-radius: 14px;
    padding: 1.25rem 1.4rem;
    margin-bottom: 1rem;
  }
  .mia-card-h { background: var(--mia-surface-2); }

  /* ─── Cartes d'offre (Top 10) ──────────────────────────────────── */
  .offre-card {
    background: var(--mia-surface);
    border: 1px solid var(--mia-border);
    border-radius: 14px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.9rem;
    transition: border-color 0.15s, transform 0.15s;
  }
  .offre-card:hover {
    border-color: var(--mia-accent);
    transform: translateY(-1px);
  }
  .offre-rank {
    display: inline-block;
    font-size: 0.72rem;
    color: var(--mia-text-dim);
    margin-bottom: 0.35rem;
    letter-spacing: 0.08em;
  }
  .offre-title {
    font-size: 1.05rem; font-weight: 700;
    color: var(--mia-text); margin: 0 0 0.25rem 0;
  }
  .offre-meta {
    font-size: 0.85rem; color: var(--mia-text-dim);
    margin-bottom: 0.6rem;
  }
  .offre-score {
    display: inline-block;
    padding: 0.18rem 0.65rem;
    border-radius: 999px;
    font-size: 0.78rem; font-weight: 700;
    color: #0A0B11;
    background: var(--mia-accent-2);
  }
  .offre-score-bad   { background: var(--mia-warn); }
  .offre-score-poor  { background: var(--mia-error); color: #fff; }
  .offre-reasoning {
    color: var(--mia-text); font-size: 0.9rem;
    line-height: 1.55; margin: 0.5rem 0;
  }
  .offre-pf { color: var(--mia-accent-2); font-size: 0.85rem; }
  .offre-pw { color: var(--mia-warn); font-size: 0.85rem; }

  /* ─── Boutons ──────────────────────────────────────────────────── */
  .stButton > button,
  .stDownloadButton > button {
    background: var(--mia-accent) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 9px !important;
    padding: 0.55rem 1.1rem !important;
    font-weight: 600 !important;
    transition: transform 0.1s, box-shadow 0.1s;
  }
  .stButton > button:hover,
  .stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 14px rgba(124, 92, 255, 0.35);
  }
  .stButton > button:disabled {
    background: var(--mia-surface-2) !important;
    color: var(--mia-text-dim) !important;
    cursor: not-allowed;
  }
  /* Bouton secondaire */
  .stButton.secondary > button {
    background: transparent !important;
    border: 1px solid var(--mia-border) !important;
    color: var(--mia-text) !important;
  }

  /* ─── Inputs ───────────────────────────────────────────────────── */
  .stTextInput input,
  .stTextArea textarea,
  .stNumberInput input,
  .stSelectbox > div > div {
    background: var(--mia-surface-2) !important;
    color: var(--mia-text) !important;
    border: 1px solid var(--mia-border) !important;
    border-radius: 8px !important;
  }
  .stTextInput input:focus,
  .stTextArea textarea:focus {
    border-color: var(--mia-accent) !important;
  }

  /* ─── File uploader ────────────────────────────────────────────── */
  [data-testid="stFileUploader"] {
    background: var(--mia-surface);
    border: 1px dashed var(--mia-border);
    border-radius: 12px;
    padding: 0.7rem;
  }

  /* ─── Tabs ─────────────────────────────────────────────────────── */
  .stTabs [data-baseweb="tab-list"] {
    background: transparent;
    border-bottom: 1px solid var(--mia-border);
    gap: 0.4rem;
  }
  .stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--mia-text-dim);
    border-radius: 7px 7px 0 0;
    padding: 0.55rem 1rem;
  }
  .stTabs [aria-selected="true"] {
    background: var(--mia-surface);
    color: var(--mia-text) !important;
    border-bottom: 2px solid var(--mia-accent);
  }

  /* ─── Status pills ─────────────────────────────────────────────── */
  .pill {
    display: inline-block;
    padding: 0.18rem 0.6rem;
    border-radius: 999px;
    font-size: 0.75rem; font-weight: 600;
    margin-right: 0.4rem;
  }
  .pill-ok    { background: rgba(94, 230, 184, 0.15); color: var(--mia-accent-2); }
  .pill-warn  { background: rgba(255, 181, 71, 0.15); color: var(--mia-warn); }
  .pill-error { background: rgba(255, 107, 107, 0.15); color: var(--mia-error); }
  .pill-info  { background: rgba(124, 92, 255, 0.15); color: var(--mia-accent); }

  /* ─── Métriques sobres ─────────────────────────────────────────── */
  [data-testid="stMetric"] {
    background: var(--mia-surface);
    border: 1px solid var(--mia-border);
    border-radius: 12px; padding: 0.9rem 1.1rem;
  }
  [data-testid="stMetricLabel"] { color: var(--mia-text-dim) !important; }
  [data-testid="stMetricValue"] { color: var(--mia-text) !important; font-size: 1.6rem !important; }

  /* ─── Expander ─────────────────────────────────────────────────── */
  .streamlit-expanderHeader {
    background: var(--mia-surface) !important;
    border: 1px solid var(--mia-border) !important;
    border-radius: 10px !important;
    color: var(--mia-text) !important;
  }

  /* ─── Hide Streamlit branding ──────────────────────────────────── */
  #MainMenu      { visibility: hidden; }
  footer         { visibility: hidden; }
  .stDeployButton { display: none; }
  /* On garde le header pour que le bouton "déplier la sidebar" reste accessible */
  header[data-testid="stHeader"] { background: transparent !important; height: 0 !important; }
</style>
"""


def inject():
    """À appeler une fois en haut de l'app."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def header():
    """Affiche le header JoBFlow stylisé."""
    st.markdown(
        """
        <div class="mia-header">
          <div class="mia-logo">J</div>
          <div>
            <p class="mia-title">JoBFlow</p>
            <p class="mia-subtitle">Matching d'offres + génération CV/LM</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def pill(text: str, variant: str = "info") -> str:
    """Retourne le HTML d'une pill colorée. À utiliser dans un st.markdown(... unsafe_allow_html=True)."""
    return f'<span class="pill pill-{variant}">{_html.escape(str(text))}</span>'


def score_class(score: int) -> str:
    """Classe CSS à utiliser pour la pill de score d'une offre."""
    if score >= 75:
        return ""
    if score >= 55:
        return "offre-score-bad"
    return "offre-score-poor"


def safe_html(value, max_len: int | None = None) -> str:
    """Nettoie une valeur dynamique avant injection dans un bloc HTML rendu par st.markdown.

    Streamlit utilise un parser markdown qui rend le HTML inline, mais si une chaîne
    interpolée contient un double saut de ligne (\\n\\n), markdown considère que le bloc
    HTML est terminé et tout le HTML qui suit s'affiche comme du texte brut.

    Cette fonction :
    - Convertit None / valeurs falsy en ""
    - Échappe les caractères HTML dangereux (<, >, &, ", ')
    - Remplace tous les sauts de ligne par des espaces
    - Tronque optionnellement
    """
    if value is None:
        return ""
    s = str(value)
    if not s.strip():
        return ""
    # Aplati les sauts de ligne (cause #1 du bug "HTML brut dans Streamlit")
    s = s.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # Évite les sauts horizontaux multiples
    while "  " in s:
        s = s.replace("  ", " ")
    s = s.strip()
    if max_len and len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    # Échappe les caractères HTML (sécurise + évite que < > cassent le rendu)
    return _html.escape(s, quote=True)
