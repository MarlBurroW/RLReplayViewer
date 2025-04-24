# Configuration
$PROJECT_NAME = "replay-analyzer"
$DOCKER_HUB_REPO = "marlburrow/rl-replay"
$VERSION_FILE = ".version"
$DOCKERFILE = "Dockerfile"

# Vérifier si Docker est installé
try {
    docker --version | Out-Null
} catch {
    Write-Host "Docker n'est pas installé ou n'est pas dans le PATH. Veuillez l'installer et réessayer."
    exit 1
}

# Fonction pour incrémenter la version
function Increment-Version {
    param (
        [string]$Version
    )
    
    $versionParts = $Version.Split('.')
    
    # Incrémenter la partie patch (troisième nombre)
    $versionParts[2] = [int]$versionParts[2] + 1
    
    return "$($versionParts[0]).$($versionParts[1]).$($versionParts[2])"
}

# Créer le fichier de version s'il n'existe pas
if (-not (Test-Path $VERSION_FILE)) {
    "1.0.0" | Out-File -FilePath $VERSION_FILE -Encoding utf8
    Write-Host "Fichier de version créé avec la version initiale 1.0.0"
}

# Lire la version actuelle
$CURRENT_VERSION = Get-Content $VERSION_FILE -Raw
$CURRENT_VERSION = $CURRENT_VERSION.Trim()
Write-Host "Version actuelle: $CURRENT_VERSION"

# Incrémenter la version
$NEW_VERSION = Increment-Version -Version $CURRENT_VERSION
Write-Host "Nouvelle version: $NEW_VERSION"

# Vérifier si le Dockerfile existe
if (-not (Test-Path $DOCKERFILE)) {
    Write-Host "Erreur: Dockerfile introuvable."
    exit 1
}

# Construire l'image Docker
Write-Host "Construction de l'image Docker $PROJECT_NAME`:$NEW_VERSION..."
docker build -t "$PROJECT_NAME`:$NEW_VERSION" -t "$PROJECT_NAME`:latest" .

# Vérifier si la construction a réussi
if ($LASTEXITCODE -eq 0) {
    # Sauvegarder la nouvelle version
    $NEW_VERSION | Out-File -FilePath $VERSION_FILE -Encoding utf8
    Write-Host "Image Docker $PROJECT_NAME`:$NEW_VERSION construite avec succès!"
    Write-Host "L'image a également été taguée comme 'latest'."
    
    # Tagger l'image pour Docker Hub
    Write-Host "Tagging pour Docker Hub: $DOCKER_HUB_REPO`:$NEW_VERSION"
    docker tag "$PROJECT_NAME`:$NEW_VERSION" "$DOCKER_HUB_REPO`:$NEW_VERSION"
    docker tag "$PROJECT_NAME`:latest" "$DOCKER_HUB_REPO`:latest"
    
    # Pousser l'image sur Docker Hub
    Write-Host "Pushing vers Docker Hub..."
    
    # Vérifier si l'utilisateur est connecté à Docker Hub
    $dockerLoginStatus = docker info 2>&1 | Select-String "Username"
    if (-not $dockerLoginStatus) {
        Write-Host "Vous n'êtes pas connecté à Docker Hub. Veuillez vous connecter avec la commande: docker login"
        $loginChoice = Read-Host "Voulez-vous vous connecter maintenant? (O/N)"
        if ($loginChoice -eq "O" -or $loginChoice -eq "o") {
            docker login
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Échec de la connexion à Docker Hub. L'image ne sera pas poussée."
                exit 1
            }
        } else {
            Write-Host "L'image ne sera pas poussée sur Docker Hub."
            exit 0
        }
    }
    
    # Pousser les tags
    docker push "$DOCKER_HUB_REPO`:$NEW_VERSION"
    docker push "$DOCKER_HUB_REPO`:latest"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Image poussée avec succès vers $DOCKER_HUB_REPO`:$NEW_VERSION et $DOCKER_HUB_REPO`:latest" -ForegroundColor Green
    } else {
        Write-Host "Erreur lors du push vers Docker Hub." -ForegroundColor Red
    }
    
    # Afficher les images
    docker images | Select-String -Pattern "$PROJECT_NAME|$DOCKER_HUB_REPO"
} else {
    Write-Host "Erreur lors de la construction de l'image Docker."
    exit 1
} 