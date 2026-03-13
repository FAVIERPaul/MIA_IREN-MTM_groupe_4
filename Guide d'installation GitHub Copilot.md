# Guide d'installation et d'utilisation de GitHub Copilot (Pack Éducation)

Ce guide est conçu pour les étudiants souhaitant utiliser **GitHub Copilot** gratuitement via le **GitHub Education Pack** dans **Visual Studio Code (VS Code)**.

---

## Table des matières
1. [Inscription au GitHub Education Pack](#1-inscription-au-github-education-pack)
2. [Installation de GitHub Copilot dans VS Code](#2-installation-de-github-copilot-dans-vs-code)
3. [Guide d'utilisation de GitHub Copilot](#3-guide-dutilisation-de-github-copilot)
4. [Bonnes pratiques pour les étudiants](#4-bonnes-pratiques-pour-les-étudiants)
5. [Résoudre les problèmes courants](#5-résoudre-les-problèmes-courants)

---

## 1. Inscription au GitHub Education Pack

### Étape 1 : Créer un compte GitHub
- Rendez-vous sur [github.com](https://github.com/) et cliquez sur **"Sign up"**.
- Suivez les instructions pour créer un compte avec une **adresse email académique** (ex: `prenom.nom@univ-paris.fr`).

### Étape 2 : Demander le GitHub Education Pack
- Allez sur [education.github.com/pack](https://education.github.com/pack).
- Cliquez sur **"Get benefits"**, puis sur **"Request a discount"**.
- Remplissez le formulaire avec :
  - Votre adresse email académique.
  - Une preuve de statut étudiant (carte étudiante, certificat de scolarité, etc.).
- Validez la demande. **La validation peut prendre quelques heures à 2 jours.**

### Étape 3 : Activer GitHub Copilot
- Une fois le pack validé, retournez sur [education.github.com/pack](https://education.github.com/pack).
- Faites défiler jusqu’à la section **"GitHub Copilot"** et cliquez sur **"Get GitHub Copilot"**.
- Suivez les instructions pour activer votre accès gratuit.

---

## 2. Installation de GitHub Copilot dans VS Code

### Étape 1 : Installer VS Code
- Téléchargez et installez [Visual Studio Code](https://code.visualstudio.com/).

### Étape 2 : Installer l’extension GitHub Copilot
- Ouvrez VS Code.
- Allez dans l’onglet **"Extensions"** (icône en forme de carré en bas de la barre latérale).
- Recherchez **"GitHub Copilot"** et cliquez sur **"Install"**.
- Une fois installée, cliquez sur **"Sign in"** et connectez-vous avec votre compte GitHub.

### Étape 3 : Vérifier l’activation
- Après la connexion, un message devrait apparaître en bas à droite : **"GitHub Copilot is ready!"**.
- Si ce n’est pas le cas, redémarrez VS Code.

---

## 3. Guide d'utilisation de GitHub Copilot

### Fonctionnalités de base
- **Suggestions de code** : Copilot propose des lignes ou des blocs de code en temps réel pendant que vous tapez.
- **Génération de fonctions** : Décrivez ce que vous voulez faire en commentaire, et Copilot générera le code.
- **Explications de code** : Sélectionnez un bloc de code et demandez une explication.

### Exemple 1 : Générer une fonction
1. Ouvrez un fichier Python (ex: `script.py`).
2. Tapez un commentaire décrivant ce que vous voulez :
   ```python
   # Écrire une fonction qui calcule la factorielle d'un nombre
