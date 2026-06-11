# JoBFlow

> Pipeline de candidature automatisé qui scrape les offres France Travail, les matche sémantiquement à votre profil et génère des CV et lettres de motivation sur mesure.

Projet réalisé dans le cadre du M1 SIREN, Paris Dauphine-PSL.

---

## Sommaire

1. [Vue d'ensemble](#vue-densemble)
2. [Pipeline](#pipeline)
3. [Installation](#installation)
4. [Lancement](#lancement)
5. [Structure du projet](#structure-du-projet)
6. [Stack technique](#stack-technique)
7. [Décisions architecturales](#décisions-architecturales)
8. [Auteur](#auteur)

---

## Vue d'ensemble

JoBFlow part d'un constat simple : postuler en masse à des offres est mécanique, mais le faire intelligemment demande un travail de matching, de personnalisation et de rédaction qu'aucun outil grand public ne fait correctement. Les ATS classent par mots-clés sans comprendre le profil. Les CV builders génèrent des contenus inventés. Les lettres de motivation produites par les LLM génériques sont reconnaissables au premier coup d'œil.

JoBFlow propose une approche différente, fondée sur trois principes :

- **Matching fuzzy plutôt que binaire** : un poste à 50 km ou un salaire 10 % en dessous de la cible n'est pas éliminé d'emblée, il est noté.
- **Inférence profonde des compétences** : le LLM ne fait pas qu'extraire les mots-clés du CV, il déduit les compétences implicites à partir des expériences décrites.
- **Select and compress, never invent** : la génération de CV sélectionne et compresse depuis des missions extraites verbatim du profil, elle n'invente jamais.

Le résultat est une app Streamlit locale qui, à partir d'un CV PDF et de quelques préférences, produit un top 10 d'offres scorées avec analyse détaillée, puis pour chaque offre un CV LaTeX optimisé ATS et une lettre de motivation `.docx` calquée sur le style du candidat.

---

## Pipeline

```
Phase 1    Collecte France Travail (~563k offres, OAuth2)
Phase 3a   Embeddings sémantiques (multilingual-e5-small, Apple Silicon MPS)
Phase 3b   Enrichissement profil candidat (Cerebras gpt-oss-120b)
Phase 3c   Matching sémantique + filtre contrat + analyse LLM
Phase 4    Génération CV LaTeX ATS-optimisé
Phase 5    Génération lettre de motivation .docx
```

### Phase 1 — Collecte
API France Travail OAuth2 paginée, itération département par département pour contourner le cap par requête. Sortie : base SQLite de 563 000 offres, hébergée sur [Hugging Face Hub](https://huggingface.co/datasets/gabinsrg/mia-france-travail).

### Phase 3a — Embeddings
Modèle `intfloat/multilingual-e5-small` (384 dimensions), exécution sur Apple Silicon MPS, checkpointing par chunks de 1 000 offres. Vitesse atteinte : 58 offres/seconde.

### Phase 3b — Profil enrichi
Parsing du CV PDF, inférence des compétences déduites par le LLM, génération de 3 à 5 questions ciblées sur les préférences (zone géo, salaire, contrats), intégration des réponses dans un profil JSON structuré avec un champ dense `synthese_pour_matching` utilisé pour l'embedding du candidat.

### Phase 3c — Matching
Single-pass : embedding du candidat → top 100 sémantique → filtrage strict par type de contrat → analyse LLM profonde de chaque offre filtrée. Sortie : un top 10 avec score 0-100, fit level, points forts/faibles, raisonnement détaillé.

### Phase 4 — Génération CV
Extraction des mots-clés ATS de l'offre, audit profil vs mots-clés, parsing structuré du CV en verbatim, génération du CV adapté, construction LaTeX, compilation PDF. Template ATS-classic unique, une page, six expériences max avec trois bullets chacune.

### Phase 5 — Génération LM
Fiche entreprise (fetch optionnel du site corporate), angles stratégiques, rédaction avec few-shot des lettres exemples du candidat, auto-critique sur cinq axes, export `.docx` dans le style cloné (Times New Roman, marges 1.27 cm, interligne 1.15).

---

## Installation

### Prérequis

- Python 3.10+
- macOS Apple Silicon recommandé pour MPS (CUDA et CPU fonctionnent aussi)
- BasicTeX pour la compilation LaTeX des CV : `brew install --cask basictex`
- Un compte Cerebras gratuit : [cloud.cerebras.ai](https://cloud.cerebras.ai)

### Setup

```bash
git clone <url-de-ce-repo>
cd <nom-du-repo>

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Configuration

Copier `.env.example` en `.env` et renseigner la clé Cerebras :

```bash
cp .env.example .env
```

| Variable | Obligatoire | Description |
|---|---|---|
| `CEREBRAS_API_KEY` | Oui | Clé Cerebras (1M tokens/jour gratuits) |
| `HF_REPO_ID` | Non | Repo HF des assets (défaut : `gabinsrg/mia-france-travail`) |
| `MIA_DATA_DIR` | Non | Dossier de stockage local (défaut : `~/.jobflow/`) |

C'est tout. La base de 563 000 offres et les embeddings sont téléchargés automatiquement depuis Hugging Face Hub au premier lancement, sans authentification requise.

---

## Lancement

```bash
streamlit run app.py
```

L'application s'ouvre sur `http://localhost:8501`.

### Premier lancement

1. Aller dans **Réglages**, saisir la clé Cerebras, télécharger les assets
2. Aller dans **Profil**, uploader son CV, répondre aux questions ciblées
3. Aller dans **Matching**, lancer le pipeline (~5 min)
4. Générer CV et LM pour les offres du Top 10

### Few-shot pour les lettres de motivation

Pour que JoBFlow reproduise fidèlement votre style de lettre, placer 2-3 LM `.docx` dans `~/.jobflow/lm_exemples/` (le dossier est créé automatiquement au premier lancement).

### Commandes utiles

```bash
# Reset du matching (pour relancer avec un profil modifié)
rm -rf ~/.jobflow/matching_state

# Forcer le re-téléchargement des assets
rm ~/.jobflow/assets/offres*.{db,npy}

# Fix PATH BasicTeX si nécessaire
export PATH="$PATH:/Library/TeX/texbin"
```

---

## Structure du projet

```
├── app.py                        # Entrée Streamlit
├── requirements.txt
├── .env.example
├── .gitignore
├── .streamlit/
│   └── config.toml               # Thème dark Streamlit
│
├── jobflow_core/                  # Logique métier
│   ├── config.py                  # Chemins, clés API, constantes
│   ├── cerebras_client.py         # Wrapper SDK + retry adaptatif
│   ├── assets.py                  # Téléchargement depuis Hugging Face Hub
│   ├── profile.py                 # Phase 3b
│   ├── matching.py                # Phase 3c
│   ├── cv_generator.py            # Phase 4
│   └── lm_generator.py            # Phase 5
│
├── pages/                         # UI Streamlit multipage
│   ├── _styles.py                 # CSS dark theme
│   ├── profile_page.py
│   ├── matching_page.py
│   ├── cv_page.py
│   ├── lm_page.py
│   └── settings_page.py
│
└── scripts/                       # One-shots opérationnels
    ├── collect_offres.py           # Collecte France Travail (Phase 1)
    ├── compute_embeddings.py       # Calcul des embeddings (Phase 3a)
    ├── build_db.py                 # Construction SQLite
    └── publish_to_hf.py            # Publication sur HF Hub
```

---

## Stack technique

| Couche | Choix | Justification |
|---|---|---|
| Embeddings | `intfloat/multilingual-e5-small` (384 dim) | Compromis qualité/vitesse sur Apple Silicon |
| LLM | Cerebras `gpt-oss-120b` | 1M TPD gratuit, latence faible |
| Backend ML | sentence-transformers, torch MPS | Apple Silicon natif |
| Frontend | Streamlit multipage | Itération rapide, zéro stack web |
| Base de données | SQLite | Embarquable, pas de serveur |
| Hébergement assets | Hugging Face Hub | Gratuit, versionné, accès public |
| Compilation CV | BasicTeX | Léger, fallback Overleaf possible |
| Export LM | python-docx | Clonage du style depuis template existant |

### Paramètres critiques

```python
TOP_K_SEMANTIC = 100          # Pré-filtre sémantique (ne pas baisser)
TOP_K_FINAL = 10              # Taille du top final
SLEEP_BETWEEN_LLM_CALLS = 2.5 # Safe pour Cerebras free tier

EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384
CEREBRAS_MODEL = "gpt-oss-120b"
```

---

## Décisions architecturales

**Single-pass plutôt que funnel.** Une première version utilisait Groq en pré-filtre puis Cerebras en analyse profonde. L'architecture a été simplifiée à un seul passage Cerebras `gpt-oss-120b`, le funnel à deux étages ne servant qu'à contourner les quotas Groq.

**Embedding via `synthese_pour_matching`.** Le matching ne se fait pas sur le JSON complet du profil, mais sur un champ dense de 5-7 phrases généré en Phase 3b. Plus pertinent sémantiquement, et plus compact.

**Filtre contrat avant analyse LLM.** Le filtre par type de contrat intervient après le top 100 sémantique mais avant l'analyse LLM. Économie de tokens et suppression des analyses inutiles sur des offres exclues par préférence dure.

**State JSON par hash de profil.** Le state du matching est dérivé d'un hash MD5 du profil. Permet de tester plusieurs candidats sans collision et de reprendre une analyse interrompue.

**App locale d'abord.** Les 1,7 Go d'embeddings coûteraient 5-15 €/mois en hébergement cloud, sans bénéfice pour un usage personnel.

**Select and compress, never invent.** La génération de CV extrait les missions verbatim du CV original et les compresse pour l'offre cible. Aucun chiffre, livrable ou responsabilité n'est inventé. Si le CV source ne contient pas assez de matière, le modèle ajoute une expérience plutôt que d'étirer une bullet.

---

## Auteur

**Gabin Sirgant**
M1 SIREN, Paris Dauphine-PSL

---

*JoBFlow est un projet personnel et académique. Le code est livré tel quel, sans garantie.*
