# Projet Final — Méthodologies de l'IA Générative (2025-2026)

**Université Paris Dauphine - PSL**
**Master SIREN — Parcours MTM**

---

## Sujet

**JoBFlow** — Pipeline de candidature automatisé, de bout en bout, utilisant l'IA générative pour matcher sémantiquement un profil candidat aux offres d'emploi France Travail et générer des CV et lettres de motivation personnalisés.

## Problème traité

Postuler à des offres d'emploi demande un travail de matching, de personnalisation et de rédaction qu'aucun outil grand public ne fait correctement. Les ATS classent par mots-clés sans comprendre le profil. Les CV builders génèrent des contenus inventés. Les lettres de motivation produites par les LLM génériques sont reconnaissables au premier coup d'œil.

## Approche choisie

JoBFlow est un pipeline en six phases qui combine embeddings sémantiques et LLM (Cerebras `gpt-oss-120b`) pour :

1. **Collecter** ~563 000 offres France Travail via l'API OAuth2
2. **Calculer** un embedding sémantique pour chaque offre (`intfloat/multilingual-e5-small`, 384 dim)
3. **Enrichir** le profil candidat à partir d'un CV PDF, en inférant les compétences implicites
4. **Matcher** sémantiquement le profil aux offres, avec filtrage par type de contrat et analyse LLM profonde
5. **Générer** un CV LaTeX optimisé ATS par offre (paradigme "select and compress, never invent")
6. **Générer** une lettre de motivation `.docx` calquée sur le style du candidat (few-shot learning)

L'ensemble est packagé dans une application Streamlit locale avec un dark theme custom.

## Principaux résultats

- Pipeline fonctionnel testé avec deux profils distincts (validation multi-candidats)
- Top 10 d'offres scorées 0-100 avec raisonnement détaillé, points forts/faibles
- CV générés fidèles au profil original (aucune hallucination de chiffres ou de responsabilités)
- Lettres de motivation clonant le style du candidat grâce au few-shot sur ses propres LM existantes
- Architecture reprenable : le matching sauvegarde son état après chaque appel LLM

## Comment lancer le projet

```bash
# 1. Cloner le repo
git clone <url-de-ce-repo>
cd <nom-du-repo>

# 2. Installer les dépendances
cd Code
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configurer la clé API (seule clé obligatoire)
cp .env.example .env
# → Renseigner CEREBRAS_API_KEY (gratuit sur https://cloud.cerebras.ai)

# 4. Lancer l'application
streamlit run app.py
```

Au premier lancement, aller dans **Réglages** pour télécharger la base d'offres (~1.7 Go) depuis Hugging Face Hub. Le téléchargement est automatique et ne nécessite aucune authentification.

Voir `Code/README_TECHNIQUE.md` pour la documentation technique complète (architecture, stack, paramètres, décisions).

---

## Arborescence du dépôt

```text
/ (Racine du dépôt)
│
├── README.md                   ← Ce fichier
├── .gitignore
│
├── Rapport/
│   └── README.md               ← Rapport final + journal de bord IA (à déposer)
│
├── Code/
│   ├── README_TECHNIQUE.md     ← Documentation technique détaillée
│   ├── .env.example            ← Template de configuration
│   ├── requirements.txt        ← Dépendances Python
│   ├── app.py                  ← Point d'entrée Streamlit
│   ├── jobflow_core/           ← Logique métier (config, LLM, matching, génération)
│   ├── pages/                  ← UI Streamlit multipage
│   └── scripts/                ← Scripts one-shot (collecte, embeddings, publication)
│
├── Data/
│   └── README.md               ← Lien vers les données sur Hugging Face Hub
│
└── Presentation/
    └── README.md               ← Support de soutenance (à déposer)
```

---

## Checklist avant rendu

- [x] Le dépôt contient toutes les pièces demandées
- [x] L'arborescence est claire et cohérente
- [x] Les étapes de reproduction sont décrites
- [x] Les liens externes (données, modèles, ressources) fonctionnent
- [ ] Le rapport final est inclus dans `Rapport/`
- [ ] Le support de présentation est inclus dans `Presentation/`

---

**Auteur** : Gabin Sirgant — M1 SIREN, M2 MTM, Paris Dauphine-PSL
