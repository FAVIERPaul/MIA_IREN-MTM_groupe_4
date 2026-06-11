"""JoBFlow — Matching d'offres + génération CV/LM.

Modules :
- config            : paths, env vars, constantes
- assets            : téléchargement des fichiers lourds depuis Hugging Face
- cerebras_client   : wrapper LLM avec retry
- profile           : Phase 3b (CV → profil enrichi)
- matching          : Phase 3c (matching sémantique + LLM)
- cv_generator      : Phase 4 (CV adapté ATS-friendly)
- lm_generator      : Phase 5 (lettre de motivation auto via Cerebras)
"""

__version__ = "0.1.0"
