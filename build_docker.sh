#!/bin/bash

# Configuration
PROJECT_NAME="replay-analyzer"
VERSION_FILE=".version"
DOCKERFILE="Dockerfile"

# Vérifier si Docker est installé
if ! command -v docker &> /dev/null; then
    echo "Docker n'est pas installé. Veuillez l'installer et réessayer."
    exit 1
fi

# Fonction pour incrémenter la version
increment_version() {
    local version=$1
    IFS='.' read -r -a version_parts <<< "$version"
    
    # Incrémenter la partie patch (troisième nombre)
    version_parts[2]=$((version_parts[2] + 1))
    
    echo "${version_parts[0]}.${version_parts[1]}.${version_parts[2]}"
}

# Créer le fichier de version s'il n'existe pas
if [ ! -f "$VERSION_FILE" ]; then
    echo "1.0.0" > "$VERSION_FILE"
    echo "Fichier de version créé avec la version initiale 1.0.0"
fi

# Lire la version actuelle
CURRENT_VERSION=$(cat "$VERSION_FILE")
echo "Version actuelle: $CURRENT_VERSION"

# Incrémenter la version
NEW_VERSION=$(increment_version "$CURRENT_VERSION")
echo "Nouvelle version: $NEW_VERSION"

# Vérifier si le Dockerfile existe
if [ ! -f "$DOCKERFILE" ]; then
    echo "Erreur: Dockerfile introuvable."
    exit 1
fi

# Construire l'image Docker
echo "Construction de l'image Docker $PROJECT_NAME:$NEW_VERSION..."
docker build -t "$PROJECT_NAME:$NEW_VERSION" -t "$PROJECT_NAME:latest" .

# Vérifier si la construction a réussi
if [ $? -eq 0 ]; then
    # Sauvegarder la nouvelle version
    echo "$NEW_VERSION" > "$VERSION_FILE"
    echo "Image Docker $PROJECT_NAME:$NEW_VERSION construite avec succès!"
    echo "L'image a également été taguée comme 'latest'."
    
    # Afficher les images
    docker images | grep "$PROJECT_NAME"
else
    echo "Erreur lors de la construction de l'image Docker."
    exit 1
fi 