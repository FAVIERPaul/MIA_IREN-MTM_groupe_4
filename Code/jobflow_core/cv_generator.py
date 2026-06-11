"""Phase 4 — Génération de CV LaTeX adapté à une offre, avec interdiction d'inventer.

v5 (8 juin 2026) — Ajout d'une section Projets :
- Extraction des projets depuis le CV original (Étape 3)
- Sélection + priorisation par pertinence pour l'offre (Étape 4)
- Section LaTeX dédiée affichée uniquement si ≥1 projet présent
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable

import pypdf

from . import config
from .cerebras_client import call_llm


# ─── Corrections OCR connues (les CV InDesign/Canva extraient mal) ───
CORRECTIONS_OCR = {
    "Haasmann":            "Haussmann",
    "Haussman":            "Haussmann",
    "Hausmann":            "Haussmann",
    "Galerie Lafayette":   "Galeries Lafayette",
    "Galleries Lafayette": "Galeries Lafayette",
    "SNFC":                "SNCF",
    "SCNF":                "SNCF",
}


def parse_cv_pdf(pdf_path: Path) -> str:
    """Extrait + nettoie le texte d'un CV PDF."""
    reader = pypdf.PdfReader(str(pdf_path))
    txt = "\n".join((p.extract_text() or "") for p in reader.pages).strip()

    # Fix : entreprise+mois collés (ARTEMars → ARTE Mars)
    mois = r"(Janvier|Février|Fevrier|Mars|Avril|Mai|Juin|Juillet|Août|Aout|Septembre|Octobre|Novembre|Décembre|Decembre)"
    txt = re.sub(rf"([A-Za-zéèêàùôîç]){mois}\b", r"\1 \2", txt)
    txt = re.sub(r"[ \t]+", " ", txt)

    for wrong, right in CORRECTIONS_OCR.items():
        txt = txt.replace(wrong, right)
    return txt


def latex_escape(text: str | None) -> str:
    if not isinstance(text, str):
        return ""
    unicode_map = {
        "\u2011": "-", "\u2012": "-", "\u2013": "--", "\u2014": "---",
        "\u2015": "--", "\u00ad": "", "\u2019": "'", "\u2018": "'",
        "\u201c": "``", "\u201d": "''", "\u00ab": "<<", "\u00bb": ">>",
        "\u00a0": " ", "\u202f": " ", "\u2026": "...", "\u2022": "-",
        "\n": " ", "\r": " ", "\t": " ",
    }
    for k, v in unicode_map.items():
        text = text.replace(k, v)
    escapes = [
        ("\\",  r"\textbackslash{}"),
        ("&",   r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_",   r"\_"), ("{", r"\{"), ("}", r"\}"),
        ("~",   r"\textasciitilde{}"), ("^", r"\textasciicircum{}"),
    ]
    for k, v in escapes:
        text = text.replace(k, v)
    return text


def slugify(text: str, maxlen: int = 40) -> str:
    text = re.sub(r"[^\w\s-]", "", text or "").strip().lower()
    text = re.sub(r"[\s_-]+", "_", text)
    return text[:maxlen] or "unknown"


# ─── Étape 1 : extraction des mots-clés ATS ──────────────────────────
_SYSTEM_KEYWORDS = """Tu es expert en recrutement et optimisation ATS.

Extrait les MOTS-CLES exacts qu'un ATS recherchera dans le CV pour cette offre.

Règles :
- Hard skills : technos, outils, méthodologies (Python, SQL, Tableau, Agile...)
- Soft skills : qualités humaines explicitement demandées
- Vocabulaire métier : termes du secteur
- Diplômes/certifs mentionnés
- Langues exigées avec niveau

Reprends les mots-clés EXACTS de l'offre (orthographe et casse exactes).

Réponds UNIQUEMENT en JSON :
{
  "hard_skills": [],
  "soft_skills": [],
  "vocabulaire_metier": [],
  "diplomes_certifs": [],
  "langues": [{"langue": "", "niveau": ""}],
  "mots_cles_critiques_top5": []
}"""


def extract_keywords(offre: dict) -> dict:
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_KEYWORDS},
            {"role": "user", "content":
                f"OFFRE :\n\nIntitulé : {offre.get('intitule', '')}\n\n{offre.get('description', '')}"},
        ],
        max_tokens=2500,
    )


# ─── Étape 2 : audit profil vs mots-clés ────────────────────────────
_SYSTEM_AUDIT = """Tu compares un profil candidat à des mots-clés cibles d'une offre.

Pour CHAQUE mot-clé, indique son statut :
- "present_explicit" : terme exact présent dans le profil
- "present_implicit" : compétence présente mais formulée différemment
- "absent_but_inferrable" : pas explicite mais probablement maîtrisé vu le parcours
- "absent" : vraiment pas dans le profil

N'invente JAMAIS de compétence.

Réponds UNIQUEMENT en JSON :
{
  "recommandations": {
    "a_mettre_en_avant": [],
    "a_integrer_naturellement": [],
    "gaps_honnetes": []
  }
}"""


def audit_profile_vs_keywords(profil: dict, keywords: dict) -> dict:
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_AUDIT},
            {"role": "user", "content":
                f"PROFIL :\n{json.dumps(profil, ensure_ascii=False, indent=2)}\n\n"
                f"MOTS-CLES CIBLES :\n{json.dumps(keywords, ensure_ascii=False, indent=2)}\n\n"
                "Audit chaque mot-clé."},
        ],
        max_tokens=4000,
    )


# ─── Étape 3 : extraction EXACTE des expériences du CV ──────────────
_SYSTEM_PARSE = """Tu extrais EXACTEMENT les expériences d'un CV - texte brut, aucune invention.

REGLES CRITIQUES :

1. INTITULES DE POSTE : extrait l'intitulé COMPLET, jamais tronqué.
   MAUVAIS : poste = 'Stagiaire'
   BON     : poste = 'Stagiaire au sein de la Direction People & Culture France (Ressources Humaines)'

1bis. EXPERIENCES ASSOCIATIVES : président(e) d'asso, membre de bureau (BDE, BDS, BDA),
   coordination de projet associatif, bénévolat structuré → à extraire dans le MÊME array
   'experiences' que les expériences pro. Une 'Présidente de Belle Rive Paris' est une expérience
   à part entière (compétences en management, événementiel...).

2. ENTREPRISES : nom EXACT, jamais fusionné avec un mois ou une date.
   MAUVAIS : 'ARTEMars'    BON : entreprise = 'ARTE', date_debut = '03/2026'

3. FORMATIONS : sépare STRICTEMENT établissement et detail_exact.
   - etablissement = nom de l'école/lycée uniquement
   - detail_exact = mention, spécialités, options uniquement
   Extrait TOUTES les formations (Master, Licence, Bac).

4. CERTIFICATIONS : si TOEIC/TOEFL/Cambridge/IELTS avec un score, recopie EXACT
   (ex: 'TOEIC 975/990', 'TOEFL 667/677', 'Cambridge C1+').

5. LANGUES : extrait le niveau et toute info de contexte (semestre à l'étranger, etc.).

6. ORTHOGRAPHE : corrige les fautes évidentes d'extraction PDF sur noms propres connus.

7. MISSIONS : recopie EXACTEMENT comme dans le CV, aucun résumé.

8. PROJETS PERSONNELS : si le CV contient une section "Projets", "Projects",
   "Side projects" ou équivalent (typiquement dans CV tech/data), extrais-les dans
   un array 'projets'. Un projet = un livrable concret réalisé par le candidat hors
   contexte pro/scolaire formel (Kaggle, GitHub, build perso, hackathon...).
   IMPORTANT : si le CV n'a PAS de section projets, retourne 'projets': [].
   Ne fabrique JAMAIS un projet à partir d'une expérience pro.
   Recopie le titre, le stack et les descriptions EXACTEMENT.

Réponds UNIQUEMENT en JSON :
{
  "experiences": [
    {"poste": "intitulé COMPLET", "entreprise": "nom exact SANS date",
     "contexte": "sous-direction si présente", "lieu": "Ville",
     "date_debut": "MM/YYYY", "date_fin": "MM/YYYY ou Present",
     "missions_exactes": ["Mission 1 EXACTE", "Mission 2 EXACTE"]}
  ],
  "projets": [
    {"titre": "Titre exact du projet",
     "stack": "Techs/outils mentionnés (ex: Python, TensorFlow, Pandas)",
     "lien": "URL si présente sinon vide",
     "descriptions_exactes": ["Description 1 EXACTE", "Description 2 EXACTE"]}
  ],
  "formations": [
    {"diplome": "...", "etablissement": "...", "detail_exact": "...",
     "date_debut": "YYYY", "date_fin": "YYYY"}
  ],
  "certifications": [{"nom": "TOEIC", "score_ou_niveau": "975/990", "annee": "YYYY"}],
  "langues": [{"langue": "Anglais", "niveau": "C1", "contexte": "semestre Londres"}],
  "centres_interet_bruts": ["..."]
}"""


def parse_cv_exact(cv_text: str) -> dict:
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PARSE},
            {"role": "user", "content": f"CV à analyser :\n\n{cv_text}"},
        ],
        max_tokens=6000,
        temperature=0.1,
    )


# ─── Étape 4 : génération du CV adapté (sélection + compression) ─────
_SYSTEM_CV = """Tu es expert en rédaction de CV adapté à une offre.

PARADIGME : tu SÉLECTIONNES et COMPRIMES depuis cv_structure, tu n'inventes RIEN.

========== INTERDICTION ABSOLUE D'INVENTER ==========
Tu DOIS te baser EXCLUSIVEMENT sur cv_structure['experiences'][i]['missions_exactes']
et cv_structure['projets'][i]['descriptions_exactes'].
TU NE PEUX PAS AJOUTER :
- Des CHIFFRES non présents dans missions_exactes/descriptions_exactes
- Des RESPONSABILITES non présentes
- Des LIVRABLES non présents
- Des compétences adjacentes non listées
- Des PROJETS non présents dans cv_structure['projets']
Si cv_structure['projets'] est vide, le champ 'projets' de ta sortie DOIT être [].
Si tu sens le besoin d'inventer pour remplir, AJOUTE UNE EXPERIENCE EN PLUS, ne stretche pas une bullet.

========== STYLE DES BULLETS ==========
Bullets COURTS (15-25 mots), commençant par NOM COMMUN (Gestion, Animation, Coordination,
Pilotage, Conception, Analyse, Rédaction, Organisation, Suivi, Structuration...).
Pour les projets : même style (Conception, Implémentation, Entraînement, Construction...).

========== STRATEGIE 1 PAGE BIEN REMPLIE ==========
- 4 à 6 expériences (pro + associatives), TRIEES PAR PERTINENCE POUR L'OFFRE
- 2 à 3 bullets/expérience, 15-25 mots chacun, FIDÈLES aux missions_exactes
- 0 à 3 projets, TRIES PAR PERTINENCE pour l'offre (les + techniques d'abord pour postes tech/data,
  zappe les projets si l'offre est éloignée de leur thématique)
- 1-2 bullets/projet, 15-25 mots chacun, FIDELES aux descriptions_exactes
- 3 FORMATIONS si disponibles, avec détails conservés
- Accroche 2 lignes OBLIGATOIRE, orientée match avec l'offre
- Centres d'intérêt : 3-5 éléments détaillés

========== REGLE PROJETS ==========
- Si cv_structure['projets'] est NON VIDE → tu DOIS inclure 1 à 3 projets pertinents
- Si cv_structure['projets'] est VIDE → 'projets': [] dans ta sortie (PAS d'invention)
- Critère de priorisation : pertinence du stack/thématique pour l'offre, puis pour la trajectoire

Réponds UNIQUEMENT en JSON :
{
  "contact": {"nom_complet": "", "email": "", "telephone": "", "ville": "", "linkedin": "", "github": ""},
  "titre_cv": "Titre du CV adapté à l'offre",
  "accroche": "2 lignes d'accroche",
  "experiences": [
    {"poste": "", "entreprise": "", "lieu": "", "contexte": "",
     "date_debut": "MM/YYYY", "date_fin": "MM/YYYY ou Présent",
     "bullets": ["...", "...", "..."]}
  ],
  "projets": [
    {"titre": "", "stack": "", "lien": "",
     "bullets": ["...", "..."]}
  ],
  "formations": [{"diplome": "", "etablissement": "", "detail": "", "dates": "YYYY-YYYY"}],
  "competences": {"techniques": [], "outils": [], "langues_avec_niveau": []},
  "langues": [{"langue": "", "niveau": ""}],
  "centres_interet": ["..."]
}"""


def generate_cv_structured(
    cv_structure: dict, profil: dict, offre: dict, audit: dict, keywords: dict
) -> dict:
    user_prompt = (
        f"CV STRUCTURE (source de vérité, ne pas dévier) :\n{json.dumps(cv_structure, ensure_ascii=False, indent=2)}\n\n"
        f"PROFIL ENRICHI :\n{json.dumps(profil, ensure_ascii=False, indent=2)}\n\n"
        f"OFFRE CIBLE :\nIntitulé : {offre.get('intitule', '')}\nEntreprise : {offre.get('entreprise', '')}\n"
        f"Description :\n{offre.get('description', '')[:2000]}\n\n"
        f"AUDIT :\n{json.dumps(audit, ensure_ascii=False, indent=2)}\n\n"
        f"MOTS-CLES :\n{json.dumps(keywords, ensure_ascii=False, indent=2)}\n\n"
        "Génère le CV adapté en respectant l'interdiction absolue d'inventer.\n"
        "RAPPEL : si cv_structure['projets'] est vide, retourne 'projets': [] (PAS d'invention)."
    )
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_CV},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=6000,
        temperature=0.3,
    )


# ─── Étape 5 : injection LaTeX ──────────────────────────────────────
# NB : la section Projets est insérée via placeholder __PROJETS_BLOCK__ qui sera
# soit vide (pas de projets), soit "\section{Projets} ..." complet.
_LATEX_TEMPLATE = r"""\documentclass[10pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage[margin=1.3cm]{geometry}
\usepackage{enumitem}
\usepackage{titlesec}
\usepackage{xcolor}
\usepackage[hidelinks]{hyperref}
\usepackage{parskip}
\pagestyle{empty}
\definecolor{sectioncolor}{HTML}{2C3E50}
\titleformat{\section}{\large\bfseries\color{sectioncolor}}{}{0pt}{}[\titlerule]
\titlespacing*{\section}{0pt}{10pt}{5pt}
\titleformat{\subsection}{\normalsize\bfseries}{}{0pt}{}
\titlespacing*{\subsection}{0pt}{6pt}{2pt}
\setlist[itemize]{leftmargin=*,topsep=1pt,itemsep=1pt,parsep=0pt}
\setlength{\parskip}{2pt}
\begin{document}
\begin{center}
{\LARGE\bfseries __NOM_COMPLET__}\\[2pt]
{\normalsize __TITRE_CV__}\\[3pt]
{\small __CONTACT_LINE__}
\end{center}
__ACCROCHE_BLOCK__
\section{Exp\'erience professionnelle}
__EXPERIENCES_BLOCK__
__PROJETS_BLOCK__
\section{Formation}
__FORMATIONS_BLOCK__
\section{Comp\'etences}
__COMPETENCES_BLOCK__
\section{Langues}
__LANGUES_BLOCK__
__INTERETS_BLOCK__
\end{document}
"""


def _build_contact_line(c: dict) -> str:
    parts = [latex_escape(c.get(k, ""))
             for k in ("email", "telephone", "ville", "linkedin", "github")
             if c.get(k)]
    return " \\textbar{} ".join(parts)


def _build_experiences_block(experiences: list[dict]) -> str:
    blocks = []
    for exp in experiences[:6]:
        poste    = latex_escape(exp.get("poste", ""))
        ent      = latex_escape(exp.get("entreprise", ""))
        lieu     = latex_escape(exp.get("lieu", ""))
        contexte = latex_escape(exp.get("contexte", ""))
        dates    = f"{exp.get('date_debut', '')} -- {exp.get('date_fin', '')}"
        bullets  = exp.get("bullets", [])[:4]

        header = f"\\subsection*{{{poste} \\hfill {dates}}}"
        sub = f"\\textit{{{ent}"
        if lieu:
            sub += f", {lieu}"
        sub += "}"
        if contexte:
            sub += f" \\textemdash\\ \\small {contexte}\\normalsize"

        if bullets:
            items = "\n".join(f"  \\item {latex_escape(b)}" for b in bullets)
            blocks.append(f"{header}\n{sub}\n\\begin{{itemize}}\n{items}\n\\end{{itemize}}")
        else:
            blocks.append(f"{header}\n{sub}")
    return "\n".join(blocks)


def _build_projets_block(projets: list[dict]) -> str:
    """Construit la section Projets en LaTeX. Renvoie "" si aucun projet."""
    if not projets:
        return ""

    blocks = []
    for proj in projets[:3]:
        titre   = latex_escape(proj.get("titre", ""))
        stack   = latex_escape(proj.get("stack", ""))
        lien    = (proj.get("lien", "") or "").strip()
        bullets = proj.get("bullets", [])[:2]

        # Titre + lien aligné à droite si présent (cliquable dans le PDF)
        if lien:
            # Pas de latex_escape sur l'URL (sinon les & seraient cassés),
            # mais on protège quand même les caractères dangereux essentiels
            safe_lien = lien.replace("%", "\\%").replace("#", "\\#")
            header = f"\\subsection*{{{titre} \\hfill \\href{{{safe_lien}}}{{\\small Lien}}}}"
        else:
            header = f"\\subsection*{{{titre}}}"

        sub = f"\\textit{{{stack}}}" if stack else ""

        if bullets:
            items = "\n".join(f"  \\item {latex_escape(b)}" for b in bullets)
            body = f"\\begin{{itemize}}\n{items}\n\\end{{itemize}}"
        else:
            body = ""

        parts = [header]
        if sub:
            parts.append(sub)
        if body:
            parts.append(body)
        blocks.append("\n".join(parts))

    return "\\section{Projets}\n" + "\n".join(blocks)


def _build_formations_block(formations: list[dict]) -> str:
    blocks = []
    for f in formations[:3]:
        diplome      = latex_escape(f.get("diplome", ""))
        etab         = latex_escape(f.get("etablissement", ""))
        detail       = latex_escape(f.get("detail", ""))
        dates        = latex_escape(f.get("dates", ""))
        line = f"\\textbf{{{diplome}}} \\hfill {dates}\\\\\n\\textit{{{etab}}}"
        if detail:
            line += f"\\\\\n\\small {detail}\\normalsize"
        blocks.append(line + "\\par")
    return "\n\\vspace{4pt}\n".join(blocks)


def _build_competences_block(c: dict) -> str:
    parts = []
    if c.get("techniques"):
        parts.append("\\textbf{Techniques :} " + latex_escape(", ".join(c["techniques"])))
    if c.get("outils"):
        parts.append("\\textbf{Outils :} " + latex_escape(", ".join(c["outils"])))
    return "\\\\\n".join(parts)


def _build_langues_block(langues: list[dict]) -> str:
    items = [f"{latex_escape(l.get('langue', ''))} ({latex_escape(l.get('niveau', ''))})" for l in langues]
    return ", ".join(items)


def _build_interets_block(interets: list[str]) -> str:
    if not interets:
        return ""
    return ("\\section{Centres d'int\\'er\\^et}\n"
            + ", ".join(latex_escape(i) for i in interets))


def build_latex(cv: dict) -> str:
    contact = cv.get("contact", {})
    accroche = cv.get("accroche", "")
    accroche_block = ""
    if accroche:
        accroche_block = (
            "\\begin{center}\n\\small\\itshape "
            + latex_escape(accroche) + "\n\\end{center}"
        )
    return (_LATEX_TEMPLATE
            .replace("__NOM_COMPLET__",     latex_escape(contact.get("nom_complet", "")))
            .replace("__TITRE_CV__",        latex_escape(cv.get("titre_cv", "")))
            .replace("__CONTACT_LINE__",    _build_contact_line(contact))
            .replace("__ACCROCHE_BLOCK__",  accroche_block)
            .replace("__EXPERIENCES_BLOCK__", _build_experiences_block(cv.get("experiences", [])))
            .replace("__PROJETS_BLOCK__",    _build_projets_block(cv.get("projets", [])))
            .replace("__FORMATIONS_BLOCK__",  _build_formations_block(cv.get("formations", [])))
            .replace("__COMPETENCES_BLOCK__", _build_competences_block(cv.get("competences", {})))
            .replace("__LANGUES_BLOCK__",     _build_langues_block(cv.get("langues", [])))
            .replace("__INTERETS_BLOCK__",    _build_interets_block(cv.get("centres_interet", []))))


def has_pdflatex() -> bool:
    # On ajoute le chemin Mac TeX par défaut s'il n'est pas déjà dans le PATH
    import os
    if shutil.which("pdflatex"):
        return True
    extra = "/Library/TeX/texbin"
    if extra not in os.environ.get("PATH", ""):
        os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + extra
    return shutil.which("pdflatex") is not None


def compile_pdf(tex_path: Path) -> tuple[Path | None, int | None]:
    """Compile un .tex en .pdf (2 passes). Retourne (pdf_path | None, nb_pages | None)."""
    if not has_pdflatex():
        return None, None
    output_dir = tex_path.parent
    for _ in range(2):
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode",
             "-output-directory", str(output_dir), str(tex_path)],
            capture_output=True, text=True,
        )
    pdf_path = output_dir / (tex_path.stem + ".pdf")
    if not pdf_path.exists():
        return None, None
    try:
        n_pages = len(pypdf.PdfReader(str(pdf_path)).pages)
    except Exception:
        n_pages = None
    # Cleanup des fichiers auxiliaires
    for ext in (".aux", ".log", ".out"):
        aux = output_dir / (tex_path.stem + ext)
        if aux.exists():
            aux.unlink()
    return pdf_path, n_pages


# ─── Pipeline complet ───────────────────────────────────────────────
def generate_cv_for_offre(
    offre: dict,
    profil: dict,
    cv_pdf_path: Path = config.CV_PDF_PATH,
    progress_cb: Callable[[str], None] | None = None,
) -> dict:
    """Pipeline complet : génère un CV adapté à une offre.

    Retourne un dict {tex_path, pdf_path|None, nb_pages|None, keywords, audit, cv_data}.
    """
    def progress(msg):
        if progress_cb:
            progress_cb(msg)

    progress("Lecture du CV PDF…")
    cv_text = parse_cv_pdf(cv_pdf_path)

    progress("Extraction des mots-clés ATS de l'offre…")
    keywords = extract_keywords(offre)

    progress("Audit profil vs mots-clés…")
    audit = audit_profile_vs_keywords(profil, keywords)

    progress("Extraction structurée des expériences et projets du CV…")
    cv_structure = parse_cv_exact(cv_text)

    progress("Génération du CV adapté…")
    cv = generate_cv_structured(cv_structure, profil, offre, audit, keywords)

    progress("Construction du .tex…")
    tex = build_latex(cv)

    # Nom de dossier basé sur entreprise + intitulé
    folder_name = (
        datetime.now().strftime("%Y%m%d_%H%M%S") + "_"
        + slugify(offre.get("entreprise", "")) + "_"
        + slugify(offre.get("intitule", ""))
    )
    out_dir = config.OUTPUTS_CV_DIR / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    tex_path = out_dir / "cv.tex"
    tex_path.write_text(tex, encoding="utf-8")

    progress("Compilation PDF…")
    pdf_path, nb_pages = compile_pdf(tex_path)

    return {
        "tex_path":  tex_path,
        "pdf_path":  pdf_path,
        "nb_pages":  nb_pages,
        "keywords":  keywords,
        "audit":     audit,
        "cv_data":   cv,
        "out_dir":   out_dir,
    }
