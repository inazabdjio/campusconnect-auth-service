# 🔐 Service d'Authentification (`auth-service`)

Microservice d'authentification, d'autorisation et de gestion des identités conçu selon les principes de la **Clean Architecture** avec **FastAPI**, **PostgreSQL**, **SQLAlchemy** et **JWT**. Il constitue le socle de sécurité de la plateforme universitaire en gérant les rôles **Étudiant (`STUDENT`)**, **Enseignant (`LECTURER`)** et **Administrateur (`ADMIN`)** sur une base de données dédiée (`auth_db`).

---

## 📋 Table des matières

1. [Fonctionnalités principales](#-1-fonctionnalités-principales)
2. [Architecture du projet](#-2-architecture-du-projet)
3. [Prérequis système](#-3-prérequis-système)
4. [Installation et configuration](#-4-installation-et-configuration)
5. [Lancement du service sur PC (Terminal 1 : Serveur)](#5-lancement-du-service-sur-pc-terminal-1--serveur)
6. [Exécution des tests — Unitaires & Intégration (Terminal 2 : Tests)](#6-exécution-des-tests--unitaires--intégration-terminal-2--tests)
7. [Tests complets sur téléphone Android (Terminal 2 : ADB + Chrome mobile)](#7-tests-complets-sur-téléphone-android-terminal-2--adb--chrome-mobile)
8. [Dépannage rapide](#-8-dépannage-rapide)

---

## 🚀 1. Fonctionnalités principales

Le service permet l'inscription, la gestion de profil et la connexion via **trois mécanismes d'authentification indépendants et sécurisés** :

1. **🔑 Authentification par e-mail et mot de passe** :
   * Hachage sécurisé des mots de passe avec `bcrypt`.
   * Émission d'un **Access Token JWT** (`HS256`) et d'un **Refresh Token** avec rotation automatique et révocation immédiate en base (`refresh_tokens`) pour bloquer toute réutilisation (attaque par relecture).
   * Gestion stricte des rôles utilisateurs : `STUDENT`, `LECTURER`, `ADMIN`.
2. **🙂 Reconnaissance faciale biométrique** :
   * Détection de vivacité (*liveness detection*) vérifiant la netteté/texture ou le mouvement entre **2 captures photo**.
   * Extraction d'embeddings faciaux normalisés et **chiffrement symétrique Fernet (`AES-128-CBC` + `HMAC`)** avant stockage dans la table `face_templates`.
   * Exigence explicite du consentement utilisateur (`consent_given: true`).
3. **👆 Empreinte digitale / Passkeys (WebAuthn / FIDO2)** :
   * Génération des défis cryptographiques (*challenges*) et vérification des signatures biométriques matérielles depuis le capteur d'empreinte d'un téléphone Android ou d'un navigateur compatible (`webauthn_credentials`).

---

## 🏗️ 2. Architecture du projet

Le projet respecte une séparation claire entre le domaine métier, les cas d'utilisation, l'infrastructure et l'API :

```text
auth-service/
├── app/
│   ├── api/                  # Routes FastAPI, dépendances HTTP et schémas Pydantic
│   ├── application/          # Cas d'utilisation métier (AuthUseCases)
│   ├── core/                 # Configuration, sécurité JWT, chiffrement Fernet, hachage
│   ├── domain/               # Entités, énumérations (RoleEnum), interfaces et stratégies (Face, WebAuthn)
│   ├── infrastructure/       # Modèles ORM SQLAlchemy, sessions PostgreSQL, repositories, Kafka
│   └── main.py               # Point d'entrée de l'application FastAPI
├── tests/
│   ├── unit/                 # Tests unitaires isolés (42 tests)
│   └── integration/          # Tests d'intégration FastAPI + PostgreSQL réel (7 tests)
├── .env.example              # Modèle des variables d'environnement de l'application
├── .env.test                 # Variables d'environnement isolées pour les tests (ignoré par Git)
├── pytest.ini                # Configuration Pytest et filtres d'avertissements
└── requirements.txt          # Dépendances Python du projet
```

---

## 🧰 3. Prérequis système

Avant de démarrer, vérifiez que les éléments suivants sont installés sur votre ordinateur :

* **Python 3.10 ou plus** (`python3 --version`)
* **PostgreSQL 14 ou plus** (`psql --version`) avec une base de données dédiée nommée **`auth_db`**
* **Git** (`git --version`)
* **ADB (Android Debug Bridge)** *(indispensable pour relier le téléphone Android par câble USB)* :
  ```bash
  sudo apt update && sudo apt install -y adb
  ```

---

## ⚙️ 4. Installation et configuration

> **Où taper ces commandes ?** Ouvrez un terminal sur votre PC (nous l'appellerons **Terminal 1**).

### Étape 1 : Ouvrir le dossier du projet (`Terminal 1`)
```bash
cd ~/Bureau/auth-service
```

### Étape 2 : Créer et activer l'environnement virtuel Python (`Terminal 1`)
L'environnement virtuel isole les bibliothèques du projet sans modifier la configuration Python globale de votre machine :

```bash
# 1. Créer l'environnement virtuel (à faire une seule fois)
python3 -m venv .venv

# 2. Activer l'environnement virtuel (Linux / macOS)
source .venv/bin/activate
```
*(Une fois activé, le préfixe `(.venv)` apparaît au début de la ligne dans le terminal.)*

### Étape 3 : Installer les dépendances Python (`Terminal 1`)
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Étape 4 : Configurer le fichier `.env` (`Terminal 1`)
Copiez le fichier modèle `.env.example` pour créer votre fichier `.env` :

```bash
cp .env.example .env
```

Ouvrez ensuite `.env` et vérifiez les paramètres suivants :
* **`DATABASE_URL`** : remplacez le deuxième `postgres` dans la chaîne de connexion par votre vrai mot de passe PostgreSQL (ex. `postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5432/auth_db` ou le port `5433` selon votre installation).
* **`JWT_SECRET_KEY`** : clé secrète robuste utilisée pour signer les tokens JWT.
* **`FACE_ENCRYPTION_KEY`** : clé Fernet en base64 utilisée pour chiffrer les empreintes faciales en base.

---

## 💻 5. Lancement du service sur PC (Terminal 1 : Serveur)

> **Où taper ces commandes ?** Dans **Terminal 1** (avec `(.venv)` activé). Gardez ce terminal **ouvert et actif** pendant que vous lancez les tests ou que vous testez sur le téléphone : `uvicorn` doit tourner en continu.

1. Assurez-vous que votre serveur **PostgreSQL** est démarré.
2. Dans **Terminal 1**, lancez le serveur FastAPI :
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```
3. Ouvrez votre navigateur sur le PC pour vérifier que le service répond :
   * **Interface de test interactive (Swagger UI)** : http://localhost:8001/docs
   * **Documentation technique (ReDoc)** : http://localhost:8001/redoc

---

## 🧪 6. Exécution des tests — Unitaires & Intégration (Terminal 2 : Tests)

> **Où taper ces commandes ?** Ouvrez un **deuxième terminal** (**Terminal 2**) afin de ne pas couper `uvicorn` qui tourne dans **Terminal 1**. Positionnez-vous dans le dossier du projet et activez l'environnement virtuel dans **Terminal 2** :
> ```bash
> cd ~/Bureau/auth-service
> source .venv/bin/activate
> ```

Le microservice est couvert par **49 tests automatisés** qui valident à la fois la logique interne et les échanges réels avec PostgreSQL :
* **42 tests unitaires** (`tests/unit/`) : validation de la cryptographie, des tokens JWT, du chiffrement Fernet, des rôles et des défis WebAuthn sans dépendance réseau.
* **7 tests d'intégration** (`tests/integration/`) : validation complète des endpoints HTTP FastAPI branchés sur une base **PostgreSQL** réelle, avec nettoyage automatique des tables avant et après chaque test.

### 6.1. Configuration requise pour les tests d'intégration (`.env.test`) — `Terminal 2`

Pour garder vos identifiants PostgreSQL hors du code source et de Git, créez un fichier `.env.test` à la racine du projet depuis **Terminal 2** :

```bash
cat << 'EOF' > .env.test
TEST_DATABASE_URL=postgresql://postgres:VOTRE_MOT_DE_PASSE@localhost:5433/auth_db
FACE_ENCRYPTION_KEY=dGVzdC1mZXJuZXQta2V5LWZvci1pbnRlZ3JhdGlvbi10ZXN0cy0xMjM0NQ==
EOF
```
*(Adaptez le port `5432` ou `5433` et remplacez `VOTRE_MOT_DE_PASSE` par le mot de passe de votre instance PostgreSQL.)*

### 6.2. Lancer chaque fichier de test séparément — `Terminal 2`

#### A. Tests unitaires (fichier par fichier, dans `Terminal 2`)

* **Chiffrement biométrique Fernet (`test_face_encryption.py` — 9 tests)** :
  ```bash
  pytest tests/unit/test_face_encryption.py -v
  ```

* **Hachage des mots de passe, tokens et rôles (`test_password_and_roles.py` — 14 tests)** :
  ```bash
  pytest tests/unit/test_password_and_roles.py -v
  ```

* **Création, signature et expiration des JWT (`test_security_jwt.py` — 9 tests)** :
  ```bash
  pytest tests/unit/test_security_jwt.py -v
  ```

* **Logique et normalisation WebAuthn (`test_webauthn_logic.py` — 10 tests)** :
  ```bash
  pytest tests/unit/test_webauthn_logic.py -v
  ```

#### B. Tests d'intégration PostgreSQL (fichier par fichier, dans `Terminal 2`)

* **Inscription, connexion mot de passe, `/auth/me` et suppression (`test_auth_password_flow.py` — 4 tests)** :
  ```bash
  pytest tests/integration/test_auth_password_flow.py -v
  ```

* **Rotation des Refresh Tokens, reconnaissance faciale chiffrée et WebAuthn (`test_tokens_and_biometrics.py` — 3 tests)** :
  ```bash
  pytest tests/integration/test_tokens_and_biometrics.py -v
  ```

### 6.3. Lancer les suites complètes (par catégorie ou toutes ensemble) — `Terminal 2`

* **Lancer uniquement tous les tests unitaires (42 tests)** :
  ```bash
  pytest tests/unit -v
  ```

* **Lancer uniquement tous les tests d'intégration (7 tests)** :
  ```bash
  pytest tests/integration -v
  ```

* **Lancer TOUS les tests ensemble (49 tests unitaires + intégration)** :
  ```bash
  pytest -v
  ```

---

## 📱 7. Tests complets sur téléphone Android (Terminal 2 : ADB + Chrome mobile)

Les navigateurs mobiles exigent un contexte sécurisé (`localhost` ou HTTPS) pour autoriser l'accès à la **caméra frontale** et au **capteur d'empreinte digitale (WebAuthn)**. En reliant le téléphone Android au PC par **câble USB de transfert de données**, on expose directement le port `8001` du PC sur `http://localhost:8001` côté téléphone.

> **Organisation des écrans :**
> * **Terminal 1** : reste actif avec `uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload`.
> * **Terminal 2** : sert à taper les commandes `adb`.
> * **Navigateur Google Chrome sur le téléphone Android** : sert à ouvrir l'application et tester la caméra et l'empreinte.

### Étape 1 : Activer le débogage USB sur le téléphone Android *(sur le téléphone)*
1. Sur votre téléphone, ouvrez **Paramètres** → **À propos du téléphone**.
2. Appuyez **7 fois** de suite sur **Numéro de build** jusqu'à voir le message indiquant que le mode développeur est activé.
3. Revenez dans **Paramètres** → **Système** → **Options pour les développeurs**.
4. Activez l'option **Débogage USB**.

### Étape 2 : Connecter le téléphone au PC et initialiser ADB (`Terminal 2`)
1. Branchez le téléphone au PC à l'aide d'un **câble USB permettant le transfert de données** (et pas uniquement la charge).
2. Déverrouillez l'écran du téléphone et sélectionnez le mode USB **Transfert de fichiers** (MTP).
3. Dans **Terminal 2**, exécutez :
   ```bash
   adb kill-server
   adb start-server
   adb devices
   ```
4. Sur l'écran du téléphone, une fenêtre **« Autoriser le débogage USB »** apparaît : cochez *Toujours autoriser* et appuyez sur **Autoriser**.
5. Vérifiez dans **Terminal 2** que `adb devices` affiche l'identifiant du téléphone suivi du statut **`device`**.

### Étape 3 : Relier le port `8001` du téléphone au serveur du PC (`Terminal 2`)
Dans **Terminal 2**, exécutez la redirection de port inverse via ADB :

```bash
adb reverse tcp:8001 tcp:8001
```

### Étape 4 : Ouvrir l'interface de test mobile sur le téléphone *(dans Google Chrome sur Android)*
1. Vérifiez dans **Terminal 1** que le serveur `uvicorn` tourne bien sur le port `8001`.
2. Ouvrez **Google Chrome** sur le téléphone Android et rendez-vous à l'adresse :
   ```text
   http://localhost:8001/mobile-test
   ```

### Étape 5 : Tester les 3 modes d'authentification sur le téléphone *(dans Google Chrome sur Android)*
* **🔑 1. Connexion par Mot de passe** :
  * Saisissez votre adresse e-mail et votre mot de passe, puis appuyez sur **Se connecter**.
* **🙂 2. Reconnaissance faciale (Caméra frontale + vivacité)** :
  * Connectez-vous d'abord par mot de passe pour ouvrir une session active.
  * Allez dans l'onglet/section **Visage** → **Enregistrer mon visage**.
  * Autorisez l'accès à la caméra dans Chrome, prenez les **2 photos** demandées (pour valider la vivacité) et enregistrez votre profil facial.
  * Déconnectez-vous puis testez **Se connecter** via reconnaissance faciale.
* **👆 3. Empreinte digitale (Capteur biométrique WebAuthn)** :
  * Connectez-vous d'abord par mot de passe.
  * Allez dans l'onglet/section **Empreinte** → **1. Enregistrer empreinte**, puis posez votre doigt sur le capteur d'empreinte du téléphone lorsque Chrome le demande.
  * Déconnectez-vous puis testez **2. Se connecter** avec votre empreinte digitale.

---

## 🆘 8. Dépannage rapide

| Problème rencontré | Solution et terminal concerné |
| :--- | :--- |
| **`RuntimeError: TEST_DATABASE_URL est manquant`** | Créez le fichier `.env.test` à la racine du projet dans **Terminal 2** comme indiqué à la section [6.1](#61-configuration-requise-pour-les-tests-dintégration-envtest--terminal-2). |
| **Erreur d'authentification PostgreSQL (`password authentication failed`)** | Vérifiez que le mot de passe et le port (`5432` ou `5433`) dans `.env` et `.env.test` correspondent bien à votre base PostgreSQL locale. |
| **La fenêtre « Autoriser le débogage USB » n'apparaît pas** | Vérifiez que le câble transporte bien les données, passez en **Transfert de fichiers**, révoquez les autorisations USB dans *Options pour les développeurs* puis relancez dans **Terminal 2** : `adb kill-server && adb start-server && adb devices`. |
| **`adb devices` affiche `unauthorized`** | Déverrouillez l'écran du téléphone et validez la demande d'autorisation USB affichée à l'écran. |
| **La page `http://localhost:8001/mobile-test` ne s'ouvre pas sur le téléphone** | Dans **Terminal 2**, relancez `adb reverse tcp:8001 tcp:8001`, et vérifiez dans **Terminal 1** qu'`uvicorn` est bien lancé sur le port `8001`. |
| **Le port `8001` est déjà occupé** | Arrêtez l'ancien processus avec `pkill -f uvicorn` puis relancez `uvicorn` dans **Terminal 1**. |