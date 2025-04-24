# RL Replay Analyzer

Analyseur et visualiseur 3D de replays Rocket League. Cette application web vous permet d'analyser vos fichiers de replay .replay, d'extraire des statistiques détaillées et de visualiser le match en 3D directement dans votre navigateur.

![RL Replay Analyzer](https://via.placeholder.com/800x400?text=RL+Replay+Analyzer+Screenshot)

## Fonctionnalités

- ✅ Upload et analyse de fichiers .replay Rocket League
- ✅ Extraction des métadonnées et des statistiques
- ✅ Visualisation 3D du match en temps réel dans le navigateur
- ✅ Contrôles de lecture (play/pause, vitesse, timeline)
- ✅ Rendu 3D du terrain et des joueurs
- ✅ Affichage des noms et niveaux de boost des joueurs

## Architecture

### Backend (Python)
- **FastAPI** - Framework API REST
- **rrrocket** - Parseur de fichiers .replay (remplace Carball)
- **Uvicorn** - Serveur ASGI

### Frontend (TypeScript)
- **React** - Bibliothèque UI
- **Three.js / React Three Fiber** - Moteur de rendu 3D
- **Tailwind CSS** - Framework CSS
- **Vite** - Bundler et serveur de développement

## Installation

### Avec Docker Compose (recommandé pour le développement)

La méthode la plus simple pour le développement:

```bash
# Cloner le dépôt
git clone https://github.com/votre-username/rl-replay.git
cd rl-replay

# Lancer avec Docker Compose
docker-compose up
```

Cela lancera:
- Le backend FastAPI sur http://localhost:8000
- Le frontend React sur http://localhost:5173

Toute modification du code sera automatiquement appliquée grâce au hot-reload.

### Installation manuelle

#### Prérequis
- Python 3.10+ (recommandé)
- Node.js 18+ et Yarn
- [rrrocket](https://github.com/nickbabcock/rrrocket)

#### Backend

1. Créer un environnement virtuel (recommandé):
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Installer les dépendances:
```bash
pip install -r requirements.txt
```

3. Lancer le serveur backend:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

1. Installer les dépendances:
```bash
cd viewer
yarn install
```

2. Lancer le serveur de développement:
```bash
yarn dev
```

## Utilisation

1. Accéder à l'application dans votre navigateur: http://localhost:5173
2. Uploader un fichier .replay
3. Visualiser le match en 3D et accéder aux statistiques

## API REST

### POST /replays
Upload d'un fichier .replay
- **Request**: Formulaire multipart avec un champ `file`
- **Response**: JSON avec l'ID du replay et statut

### GET /replays/{id}/meta
Récupération des métadonnées du replay
- **Response**: JSON avec les données des équipes, joueurs et statistiques

### GET /replays/{id}/raw
Récupération des données brutes du replay
- **Response**: JSON avec toutes les frames et mouvements

### GET /replays/{id}
Téléchargement du fichier replay original
- **Response**: Fichier .replay

## Contribution

Les contributions sont les bienvenues! N'hésitez pas à ouvrir une issue ou une pull request.

1. Forkez le projet
2. Créez votre branche de fonctionnalité (`git checkout -b feature/amazing-feature`)
3. Committez vos changements (`git commit -m 'Add some amazing feature'`)
4. Poussez vers la branche (`git push origin feature/amazing-feature`)
5. Ouvrez une Pull Request

## Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Remerciements

- [rrrocket](https://github.com/nickbabcock/rrrocket) pour le parsing des replays
- La communauté Rocket League pour son soutien 