import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from replay_analyzer.api.endpoints import setup_routes
from replay_analyzer.utils.helpers import create_directory_if_not_exists


# Créer l'application FastAPI
app = FastAPI(
    title="Rocket League Replay Analyzer API",
    description="API pour analyser les fichiers replay de Rocket League",
    version="1.0.0"
)

# Configurer CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Pour le développement, à restreindre en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# S'assurer que les dossiers nécessaires existent
create_directory_if_not_exists("static")
create_directory_if_not_exists("static/viewer")

# Monter les fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

# Configurer les routes
setup_routes(app)


# Pour l'exécution avec uvicorn directement
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 