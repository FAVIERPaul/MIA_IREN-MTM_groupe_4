"""Phase 3b — Construction du profil enrichi à partir du CV + dialogue Q/R."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pypdf

from . import config
from .cerebras_client import call_llm


def extract_cv_text(pdf_path: Path) -> str:
    """Extrait le texte brut d'un CV PDF."""
    reader = pypdf.PdfReader(str(pdf_path))
    text = "\n".join(
        f"--- Page {i+1} ---\n{(p.extract_text() or '')}"
        for i, p in enumerate(reader.pages)
    )
    return text.strip()


_SYSTEM_PASS1 = """Tu es un expert en analyse de profils candidats.

Tu reçois le texte brut d'un CV. Tu produis un PROFIL ENRICHI en INFÉRANT activement
les compétences déduites du parcours.

Principes d'inférence :
- Cabinet de conseil → analyse stratégique, synthèse, présentation client
- Data analyst → SQL, statistiques, ETL, BI, même si non listés
- Grande école → méthodologie rigoureuse, capacité analytique
- Radio/audio/média → production, animation, storytelling, créativité
N'invente PAS d'expériences. Déduis les compétences que les expériences réelles impliquent.

Réponds UNIQUEMENT en JSON valide, schéma exact :
{
  "informations": {
    "nom": "", "email": "", "telephone": "", "localisation": "",
    "linkedin": "", "github_portfolio": ""
  },
  "formation_resume": "Texte concis listant les diplômes principaux",
  "experiences_resume": "Texte concis listant les expériences clés et leur contexte",
  "competences_techniques_explicites": [],
  "competences_techniques_deduites": [],
  "soft_skills_probables": [],
  "langues": [{"langue": "", "niveau": ""}],
  "secteurs_naturels": [],
  "trajectoire_logique": "1-2 phrases",
  "postes_pertinents": [],
  "questions_pour_le_candidat": [
    {"id": "1", "question": "", "pourquoi": ""}
  ]
}

Pour les questions : 3-5 questions ciblées sur ce que tu ne peux PAS déduire
(préférences géo précises, salaire min, contrats acceptés, secteurs voulus/rejetés,
ambitions long terme, contraintes personnelles).
Sois CONCIS dans chaque champ."""


_SYSTEM_PASS2 = """Tu reçois un profil candidat V1 et ses réponses à tes questions.
Produis le PROFIL FINAL ENRICHI en intégrant les réponses, en ajoutant la section
"preferences", et en générant une synthèse pour matching.

Réponds UNIQUEMENT en JSON valide :
{
  "informations": {},
  "formation_resume": "",
  "experiences_resume": "",
  "competences_techniques_explicites": [],
  "competences_techniques_deduites": [],
  "soft_skills_probables": [],
  "langues": [],
  "secteurs_naturels": [],
  "trajectoire_logique": "",
  "postes_pertinents": [],
  "preferences": {
    "zones_geographiques": [],
    "salaire_minimum_annuel_brut_euros": 0,
    "types_de_contrats_acceptes": [],
    "secteurs_recherches": [],
    "secteurs_rejetes": [],
    "ambitions_court_moyen_terme": "",
    "contraintes_personnelles": "",
    "modalites_travail": ""
  },
  "synthese_pour_matching": "Paragraphe de 5-7 phrases qui décrit ce candidat de manière dense pour orienter le matching."
}
Sois CONCIS."""


def pass1_analyze_cv(cv_text: str) -> dict:
    """Premier passage : extrait le profil V1 + génère 3-5 questions ciblées."""
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PASS1},
            {"role": "user", "content": f"CV à analyser :\n\n{cv_text}"},
        ],
        max_tokens=8000,
        temperature=0.3,
    )


def pass2_enrich_with_answers(profil_v1: dict, answers: dict[str, str]) -> dict:
    """Deuxième passage : intègre les réponses du candidat dans le profil final."""
    qa_pairs = []
    for q in profil_v1.get("questions_pour_le_candidat", []):
        qid = q.get("id", "?")
        qtxt = q.get("question", "")
        rep = answers.get(qid, "(pas de réponse)")
        qa_pairs.append(f"Q{qid}: {qtxt}\nR{qid}: {rep}")
    qa_block = "\n\n".join(qa_pairs)

    user_prompt = (
        f"PROFIL V1 :\n{json.dumps(profil_v1, ensure_ascii=False, indent=2)}\n\n"
        f"RÉPONSES DU CANDIDAT À TES QUESTIONS :\n{qa_block}\n\n"
        "Produis le profil final enrichi."
    )
    return call_llm(
        messages=[
            {"role": "system", "content": _SYSTEM_PASS2},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=8000,
        temperature=0.3,
    )


def save_profile(profil: dict, path: Path = config.PROFIL_PATH) -> None:
    path.write_text(json.dumps(profil, ensure_ascii=False, indent=2), encoding="utf-8")


def load_profile(path: Path = config.PROFIL_PATH) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
