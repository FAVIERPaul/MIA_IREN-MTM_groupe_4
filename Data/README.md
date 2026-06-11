# Données

Les données utilisées par JoBFlow sont trop volumineuses pour être versionnées sur GitHub (~1.7 Go). Elles sont hébergées sur Hugging Face Hub et téléchargées automatiquement par l'application.

## Accès aux données

**Lien direct** : [https://huggingface.co/datasets/gabinsrg/mia-france-travail](https://huggingface.co/datasets/gabinsrg/mia-france-travail)

Le dataset est **public** et accessible sans authentification.

## Contenu du dataset

| Fichier | Description | Taille |
|---|---|---|
| `offres.db` | Base SQLite de ~563 000 offres France Travail (collectées via API OAuth2) | ~200 Mo |
| `offres_embeddings.npy` | Embeddings sémantiques (modèle `intfloat/multilingual-e5-small`, 384 dim) | ~1.5 Go |
| `offres_ids.npy` | Identifiants des offres (même ordre que les embeddings) | ~15 Mo |

## Source des données

Les offres proviennent de l'API publique de [France Travail](https://francetravail.io/data/api/offres-emploi) (anciennement Pôle Emploi). La collecte a été réalisée via un script OAuth2 paginé itérant département par département pour contourner le cap de résultats par requête (voir `Code/scripts/collect_offres.py`).

## Téléchargement

Le téléchargement se fait automatiquement depuis l'application (page **Réglages** → **Télécharger les assets**). Il est aussi possible de le faire manuellement :

```python
from huggingface_hub import hf_hub_download

for filename in ["offres.db", "offres_embeddings.npy", "offres_ids.npy"]:
    hf_hub_download(repo_id="gabinsrg/mia-france-travail", filename=filename, repo_type="dataset")
```
