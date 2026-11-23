# 🔐 Service d'Authentification (`auth-service`)

Ce guide explique pas à pas, de façon très simple, comment installer, configurer et lancer le service **`auth-service`** sur votre ordinateur et le tester sur un téléphone Android.

---

## 📖 1. À quoi sert ce service ?

Le service **`auth-service`** gère la connexion et la sécurité des utilisateurs. Il permet de se connecter de **3 manières différentes et indépendantes** :

1. **🔑 Mot de passe** : Avec une adresse e-mail et un mot de passe.
2. **🙂 Reconnaissance faciale** : Avec la caméra frontale (le système prend 2 photos pour vérifier que la personne est bien réelle).
3. **👆 Empreinte digitale (WebAuthn)** : Avec le capteur d'empreinte du téléphone Android.

---

## 🧰 2. Ce qu'il faut installer sur l'ordinateur (Prérequis)

Avant de commencer, vérifiez que vous avez :

* **Python 3.10 ou plus** (`python3 --version`)
* **PostgreSQL** (`psql --version`)
* **Git** (`git --version`)
* **ADB** *(pour relier le téléphone Android par câble USB)*

Pour installer **ADB** sur Ubuntu / Linux :
```bash
sudo apt update && sudo apt install -y adb
```

---

## ⚙️ 3. Installation et configuration du projet

### Étape 1 : Ouvrir le dossier du projet
```bash
cd ~/Bureau/auth-service
```

### Étape 2 : Créer et activer l'environnement virtuel Python
L'environnement virtuel permet d'installer les bibliothèques du projet proprement sans toucher au reste de l'ordinateur.

```bash
# 1. Créer l'environnement virtuel (à faire une seule fois)
python3 -m venv .venv

# 2. Activer l'environnement virtuel (Linux / macOS)
source .venv/bin/activate
```
*(Quand il est activé, `(.venv)` apparaît au début de la ligne dans le terminal.)*

### Étape 3 : Installer les dépendances
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Étape 4 : Configurer le fichier `.env`
Copiez le fichier modèle `.env.example` pour créer votre fichier `.env` :
```bash
cp .env.example .env
```

Ouvrez ensuite le fichier `.env` et vérifiez les informations (port de l'application, accès à votre base de données PostgreSQL, clés secrètes et n'oublier pas de remplacer le deuxieme postgres ecrit dans la ligne de DATABASE_URL par votre mot de passe de postgresql).

---

## 💻 4. Comment lancer le service sur la machine (PC)

1. Assurez-vous que votre base de données **PostgreSQL** est démarrée.
2. Dans le terminal (avec `(.venv)` activé), lancez le serveur :
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
   ```
3. Ouvrez votre navigateur sur le PC pour vérifier que tout fonctionne :
   * **Interface de test API (Swagger)** : http://localhost:8001/docs

---

## 📱 5. Comment lancer et tester sur un téléphone Android

Pour que la caméra et l'empreinte digitale fonctionnent sur le téléphone, il faut relier le téléphone au PC par **câble USB** (câble permettant le transfert de données).

### Étape 1 : Activer le débogage USB sur le téléphone
1. Allez dans **Paramètres** → **À propos du téléphone**.
2. Appuyez **7 fois** sur **Numéro de build** pour activer le mode développeur.
3. Allez dans **Paramètres** → **Système** → **Options pour les développeurs**.
4. Activez **Débogage USB**.

### Étape 2 : Connecter le téléphone et relancer ADB
Branchez le téléphone au PC avec le câble USB, déverrouillez l'écran du téléphone, mettez le mode USB sur **Transfert de fichiers**, puis tapez ces commandes dans le terminal :

```bash
adb kill-server
adb start-server
adb devices
```

* Sur l'écran de votre téléphone, une fenêtre **« Autoriser le débogage USB »** apparaît : appuyez sur **Autoriser**.
* Dans le terminal, `adb devices` doit afficher l'identifiant du téléphone suivi du mot **`device`**.

### Étape 3 : Relier le port `8001` du téléphone au PC
```bash
adb reverse tcp:8001 tcp:8001
```

### Étape 4 : Ouvrir l'application sur le téléphone
1. Vérifiez que `uvicorn` tourne bien sur votre PC.
2. Ouvrez **Google Chrome** sur le téléphone Android et allez à l'adresse :
   ```text
   http://localhost:8001/mobile-test
   ```

### Comment tester les 3 modes sur le téléphone :
* **🔑 Mot de passe** : Saisissez l'e-mail et le mot de passe, puis cliquez sur **Se connecter**.
* **🙂 Visage** : Connectez-vous d'abord par mot de passe, allez dans **Visage** → **Enregistrer mon visage**, activez la caméra, prenez les **2 photos**, enregistrez, puis testez **Se connecter**.
* **👆 Empreinte** : Connectez-vous d'abord par mot de passe, allez dans **Empreinte** → **1. Enregistrer empreinte**, posez votre doigt sur le capteur, puis testez **2. Se connecter**.

---

## 🆘 6. Dépannage rapide

| Problème | Solution |
| :--- | :--- |
| **La fenêtre « Autoriser le débogage USB » n'apparaît pas** | Vérifiez que le câble transporte bien les données (pas uniquement la charge), passez en **Transfert de fichiers**, révoquez les autorisations USB dans les options développeur puis relancez `adb kill-server`, `adb start-server` et `adb devices`. |
| **`adb devices` affiche `unauthorized`** | Déverrouillez l'écran du téléphone et validez la demande d'autorisation USB. |
| **La page `http://localhost:8001/mobile-test` ne s'ouvre pas** | Relancez `adb reverse tcp:8001 tcp:8001` et vérifiez que `uvicorn` est bien lancé sur le PC. |
| **Le port 8001 est déjà occupé** | Arrêtez l'ancien serveur avec `pkill -f uvicorn` puis relancez `uvicorn`. |