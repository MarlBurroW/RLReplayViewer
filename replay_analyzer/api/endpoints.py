import os
import json
import time
import shutil
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Response
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel, Field

from replay_analyzer.utils.helpers import (
    create_directory_if_not_exists,
    run_command,
    get_background_task_status,
    set_background_task_status,
    BinaryFramesWriter,
    BinaryFramesReader
)


# Modèles de données
class PlayerStats(BaseModel):
    id: str
    name: str
    score: int = 0
    goals: int = 0
    assists: int = 0
    saves: int = 0
    shots: int = 0
    team: int = 0


class TimelineEvent(BaseModel):
    type: str
    time: float
    player_id: Optional[str] = None
    description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class CarState(BaseModel):
    id: str
    position: List[float]
    rotation: List[float]
    velocity: List[float]
    angular_velocity: List[float]
    boost: int = 0


class BallState(BaseModel):
    position: List[float]
    rotation: List[float]
    velocity: List[float]
    angular_velocity: List[float]


class Frame(BaseModel):
    time: float
    delta: float = 0.008
    ball: BallState
    cars: List[CarState]


class ReplayData(BaseModel):
    id: str
    filename: str
    name: Optional[str] = None
    map_name: Optional[str] = None
    match_type: Optional[str] = None
    team_size: Optional[int] = None
    duration: float = 0.0
    date: Optional[str] = None
    version: Optional[str] = None
    frames: Optional[List[Frame]] = None
    players: Optional[List[PlayerStats]] = None
    teams: Optional[Dict[str, List[str]]] = None
    car_player_map: Optional[Dict[str, str]] = None
    timeline: Optional[List[TimelineEvent]] = None


class ReplayStatus(BaseModel):
    id: str
    processing_status: str
    processing_progress: float = 0.0
    error: Optional[str] = None


class ReplayDataProcessed(BaseModel):
    id: str
    filename: str
    name: Optional[str] = None
    map_name: Optional[str] = None
    match_type: Optional[str] = None
    team_size: Optional[int] = None
    duration: float = 0.0
    date: Optional[str] = None
    version: Optional[str] = None
    players: Optional[List[PlayerStats]] = None
    teams: Optional[Dict[str, List[str]]] = None
    timeline: Optional[List[TimelineEvent]] = None
    team0_score: Optional[int] = 0
    team1_score: Optional[int] = 0
    score: Optional[Dict[str, Any]] = None


# Constantes
UPLOAD_DIR = "uploads"
DATA_DIR = "data"
RRROCKET_PATH = "rrrocket"  # Chemin vers l'exécutable rrrocket


# Fonctions d'analyse et de traitement
async def analyze_replay_metadata(replay_file: str, replay_id: str) -> Dict:
    """Analyse les métadonnées d'un fichier replay en utilisant rrrocket"""
    try:
        print(f"[DEBUG] analyze_replay_metadata: début pour {replay_id}")
        
        # Créer le répertoire DATA_DIR s'il n'existe pas temporairement
        create_directory_if_not_exists(DATA_DIR)
        
        # Générer un nom de fichier temporaire unique pour éviter les conflits entre requêtes
        request_uuid = str(uuid.uuid4())
        temp_output_json = f"{DATA_DIR}/{replay_id}_{request_uuid}_temp_output.json"
        
        print(f"[DEBUG] Utilisation du fichier temporaire: {temp_output_json}")
        
        # Exécuter rrrocket pour analyser le replay
        print(f"[DEBUG] Exécution de rrrocket pour {replay_id}: {RRROCKET_PATH} --pretty {replay_file}")
        result = await run_command([
            RRROCKET_PATH, "--pretty", replay_file
        ], output_file=temp_output_json)
        
        print(f"[DEBUG] rrrocket terminé avec code: {result[0]}")
        
        # Vérifier si la commande a réussi
        if result[0] != 0:
            error_msg = result[2]
            print(f"[ERROR] rrrocket a échoué: {error_msg}")
            raise HTTPException(status_code=500, 
                                detail=f"Erreur d'analyse du replay: {error_msg}")
        
        # Charger les données JSON
        print(f"[DEBUG] Chargement du JSON depuis {temp_output_json}")
        try:
            with open(temp_output_json, "r") as f:
                data = json.load(f)
            print(f"[DEBUG] JSON chargé: {len(str(data))} caractères")
        except Exception as json_err:
            print(f"[ERROR] Erreur lors du chargement JSON: {str(json_err)}")
            raise HTTPException(status_code=500, detail=f"Erreur de lecture du JSON de sortie: {str(json_err)}")
        
        # Traiter les métadonnées
        print(f"[DEBUG] Traitement des métadonnées pour {replay_id}")
        
        # Extraire les propriétés du replay
        properties = data.get("properties", {})
        
        # Préparer les métadonnées
        metadata = {
            "id": replay_id,
            "filename": os.path.basename(replay_file),
            "name": data.get("game_type", ""),
            "map_name": properties.get("MapName", ""),
            "match_type": properties.get("MatchType", ""),
            "team_size": properties.get("TeamSize", 0),
            "duration": properties.get("TotalSecondsPlayed", 0.0),
            "date": properties.get("Date", ""),
            "version": properties.get("BuildVersion", ""),
            "team0_score": properties.get("Team0Score", 0),
            "team1_score": properties.get("Team1Score", 0),
            "players": [],
            "teams": {"0": [], "1": []},
            "timeline": [],
            "score": {
                "blue": properties.get("Team0Score", 0),
                "orange": properties.get("Team1Score", 0),
                "winner": "blue" if properties.get("Team0Score", 0) > properties.get("Team1Score", 0) else "orange"
            }
        }
        
        # Traiter les joueurs
        player_stats = properties.get("PlayerStats", [])
        for player_data in player_stats:
            if not isinstance(player_data, dict):
                continue
                
            # Extraire les identifiants du joueur
            player_id_data = player_data.get("PlayerID", {}).get("fields", {})
            epic_id = player_id_data.get("EpicAccountId", "")
            
            # Récupérer l'ID Steam
            steam_id = None
            
            # 1. Vérifier le OnlineID (plus courant pour Steam)
            online_id = player_data.get("OnlineID", "")
            if online_id and online_id != "0" and online_id != "":
                # Vérifier si c'est une plateforme Steam
                platform_type = ""
                if isinstance(player_data.get("Platform"), dict):
                    platform_type = player_data["Platform"].get("value", "").lower()
                
                if "steam" in platform_type or not platform_type:
                    steam_id = online_id
                    print(f"[DEBUG] Steam ID trouvé dans OnlineID: {steam_id}")
            
            # 2. Vérifier dans les ID de plateforme si OnlineID n'a pas donné de résultat
            if not steam_id:
                platform_obj = player_id_data.get("Platform", {})
                platform_value = platform_obj.get("value", "") if isinstance(platform_obj, dict) else ""
                
                # 3. Vérifier dans les ID distants (remote_id)
                if "NpId" in player_id_data and isinstance(player_id_data["NpId"], dict):
                    np_fields = player_id_data["NpId"].get("fields", {})
                    if "Handle" in np_fields and isinstance(np_fields["Handle"], dict):
                        handle_fields = np_fields["Handle"].get("fields", {})
                        steam_handle = handle_fields.get("Data", "")
                        if steam_handle and steam_handle != "0":
                            steam_id = steam_handle
                
                # 4. Vérifier s'il existe des propriétés UniqueId ou remote_id avec Steam
                for prop_name, prop_value in player_id_data.items():
                    if isinstance(prop_value, dict) and "remote_id" in prop_value:
                        remote_id = prop_value.get("remote_id", {})
                        if isinstance(remote_id, dict) and "Steam" in remote_id:
                            steam_value = remote_id.get("Steam")
                            if steam_value and steam_value != "0":
                                steam_id = steam_value
            
            # Détermine l'ID du joueur en utilisant la hiérarchie de priorité
            player_id = None
            if epic_id and epic_id != "":
                player_id = f"epic_{epic_id}"
            elif steam_id and steam_id != "":
                player_id = f"steam_{steam_id}"
            else:
                player_id = f"name_{player_data.get('Name', 'Unknown')}"
            
            # S'assurer que platform_value est définie
            platform_value = ""
            if isinstance(player_id_data.get("Platform"), dict):
                platform_value = player_id_data["Platform"].get("value", "")
            
            # Afficher les informations de debug pour ce joueur
            print(f"[DEBUG] Joueur: {player_data.get('Name')} - ID généré: {player_id}")
            print(f"[DEBUG] Epic ID: {epic_id}, Steam ID: {steam_id}, Platform: {platform_value}")
            
            player = {
                "id": player_id,
                "name": player_data.get("Name", "Unknown"),
                "score": player_data.get("Score", 0),
                "goals": player_data.get("Goals", 0),
                "assists": player_data.get("Assists", 0),
                "saves": player_data.get("Saves", 0),
                "shots": player_data.get("Shots", 0),
                "team": player_data.get("Team", 0)
            }
            
            metadata["players"].append(player)
            
            # Ajouter le joueur à son équipe
            team_key = str(player["team"])
            if team_key not in metadata["teams"]:
                metadata["teams"][team_key] = []
            metadata["teams"][team_key].append(player["id"])
        
        # Créer la timeline des événements
        goals = properties.get("Goals", [])
        max_goal_time = 0.0
        
        for goal in goals:
            if not isinstance(goal, dict):
                continue
                
            time_fraction = goal.get("frame", 0) / (properties.get("RecordFPS", 30) * properties.get("TotalSecondsPlayed", 300))
            time = time_fraction * properties.get("TotalSecondsPlayed", 300)
            
            # Garder une trace du temps du dernier but
            if time > max_goal_time:
                max_goal_time = time
            
            event = {
                "type": "goal",
                "time": time,
                "player_id": None,  # Sera rempli ci-dessous
                "description": f"But de {goal.get('PlayerName', 'Unknown')}",
                "details": {
                    "player_name": goal.get("PlayerName", "Unknown"),
                    "team": goal.get("PlayerTeam", 0)
                }
            }
            
            # Trouver l'ID du joueur à partir de son nom
            for player in metadata["players"]:
                if player["name"] == goal.get("PlayerName"):
                    event["player_id"] = player["id"]
                    break
            
            metadata["timeline"].append(event)
        
        # Ajouter des événements par défaut si la timeline est vide
        if not metadata["timeline"]:
            metadata["timeline"] = [
                {"type": "match_start", "time": 0.0},
                {"type": "match_end", "time": properties.get("TotalSecondsPlayed", 300.0)}
            ]
        else:
            # Calculer le temps de fin réel (soit la durée officielle, soit le dernier but + 25 secondes, selon ce qui est le plus grand)
            match_end_time = max(properties.get("TotalSecondsPlayed", 300.0), max_goal_time + 25.0)
            
            # Ajouter le début et la fin du match
            metadata["timeline"].insert(0, {"type": "match_start", "time": 0.0})
            metadata["timeline"].append({"type": "match_end", "time": match_end_time})
            
            # Trier la timeline par temps croissant pour garantir l'ordre chronologique
            metadata["timeline"] = sorted(metadata["timeline"], key=lambda x: x["time"])
        
        # Supprimer le fichier temporaire après utilisation
        if os.path.exists(temp_output_json):
            try:
                os.remove(temp_output_json)
                print(f"[DEBUG] Fichier temporaire supprimé: {temp_output_json}")
            except Exception as e:
                print(f"[WARNING] Impossible de supprimer le fichier temporaire: {str(e)}")
        
        print(f"[DEBUG] analyze_replay_metadata: terminé pour {replay_id}")
        return metadata
        
    except Exception as e:
        # En cas d'erreur, mettre à jour le statut et lever une exception
        print(f"[ERROR] Exception dans analyze_replay_metadata: {str(e)}")
        import traceback
        traceback.print_exc()
        set_background_task_status(replay_id, {"status": "error", "error": str(e), "progress": 0})
        
        # Nettoyer les fichiers temporaires en cas d'erreur
        if os.path.exists(temp_output_json):
            try:
                os.remove(temp_output_json)
            except:
                pass
                
        raise HTTPException(status_code=500, detail=f"Erreur d'analyse des métadonnées: {str(e)}")


async def generate_replay_raw_json(replay_file: str, replay_id: str, network_parse: bool = False) -> str:
    """Génère le fichier JSON à partir du replay et retourne le chemin du fichier temporaire"""
    try:
        print(f"[DEBUG] generate_replay_raw_json: début pour {replay_id}")
        
        # Créer le répertoire DATA_DIR s'il n'existe pas
        create_directory_if_not_exists(DATA_DIR)
        
        # Générer un nom de fichier temporaire unique pour éviter les conflits entre requêtes
        request_uuid = str(uuid.uuid4())
        temp_output_json = f"{DATA_DIR}/{replay_id}_{request_uuid}_temp_output.json"
        
        print(f"[DEBUG] Utilisation du fichier temporaire: {temp_output_json}")
        
        # Préparer la commande rrrocket
        command = [RRROCKET_PATH, "--pretty"]
        if network_parse:
            command.append("--network-parse")
        command.append(replay_file)
        
        # Exécuter rrrocket
        print(f"[DEBUG] Exécution de rrrocket: {' '.join(command)}")
        result = await run_command(command, output_file=temp_output_json)
        
        print(f"[DEBUG] rrrocket terminé avec code: {result[0]}")
        
        # Vérifier si la commande a réussi
        if result[0] != 0:
            error_msg = result[2]
            print(f"[ERROR] rrrocket a échoué: {error_msg}")
            raise HTTPException(status_code=500, 
                                detail=f"Erreur d'analyse du replay: {error_msg}")
        
        return temp_output_json
        
    except Exception as e:
        print(f"[ERROR] Exception dans generate_replay_raw_json: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur de génération du JSON: {str(e)}")


# Configuration des routes
def setup_routes(app: FastAPI) -> None:
    """Configure les routes pour l'application FastAPI"""
    
    @app.get("/")
    async def root():
        """Redirection vers l'interface React"""
        return RedirectResponse(url="/static/viewer/index.html")
    
    @app.post("/replays")
    async def upload_replay(
        file: UploadFile = File(...)
    ):
        """Upload et analyse d'un fichier replay"""
        try:
            print(f"[DEBUG] Début upload_replay: fichier={file.filename}")
            # Vérifier l'extension du fichier
            if not file.filename.endswith('.replay'):
                print(f"[ERROR] Extension de fichier invalide: {file.filename}")
                raise HTTPException(status_code=400, detail="Le fichier doit être au format .replay")
            
            # Générer un ID unique pour le replay
            replay_id = str(uuid.uuid4())
            print(f"[DEBUG] ID généré: {replay_id}")
            
            # Créer les répertoires s'ils n'existent pas
            print(f"[DEBUG] Création des répertoires: {UPLOAD_DIR}")
            create_directory_if_not_exists(UPLOAD_DIR)
            
            # Sauvegarder le fichier upload
            replay_path = os.path.join(UPLOAD_DIR, f"{replay_id}.replay")
            print(f"[DEBUG] Sauvegarde du fichier vers: {replay_path}")
            with open(replay_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
                print(f"[DEBUG] Fichier sauvegardé")
            
            try:
                # Analyser les métadonnées
                print(f"[DEBUG] Analyse des métadonnées: {replay_path}")
                metadata = await analyze_replay_metadata(replay_path, replay_id)
                print(f"[DEBUG] Métadonnées récupérées, id={replay_id}")
                
                # Retourner les métadonnées immédiates
                print(f"[DEBUG] Retour des métadonnées pour {replay_id}")
                return ReplayDataProcessed(**metadata)
                
            except Exception as e:
                # En cas d'erreur, supprimer le fichier et renvoyer l'erreur
                print(f"[ERROR] Exception pendant le traitement de {replay_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                if os.path.exists(replay_path):
                    os.remove(replay_path)
                    print(f"[DEBUG] Fichier supprimé suite à l'erreur: {replay_path}")
                
                raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
        except Exception as e:
            print(f"[ERROR] Exception non gérée dans upload_replay: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")
    
    @app.get("/replays/{replay_id}")
    async def get_replay_file(replay_id: str):
        """Télécharger le fichier replay original"""
        replay_file = os.path.join(UPLOAD_DIR, f"{replay_id}.replay")
        
        if not os.path.exists(replay_file):
            raise HTTPException(status_code=404, detail="Fichier replay non trouvé")
            
        return FileResponse(
            path=replay_file,
            media_type="application/octet-stream", 
            filename=f"{replay_id}.replay"
        )
    
    @app.get("/replays/{replay_id}/meta")
    async def get_replay_metadata(replay_id: str):
        """Obtenir les métadonnées d'un replay en générant le JSON à la volée"""
        replay_file = os.path.join(UPLOAD_DIR, f"{replay_id}.replay")
        
        if not os.path.exists(replay_file):
            raise HTTPException(status_code=404, detail="Fichier replay non trouvé")
            
        try:
            # Analyser les métadonnées (génération à la volée)
            metadata = await analyze_replay_metadata(replay_file, replay_id)
            
            # S'assurer que chaque joueur a un ID
            for i, player in enumerate(metadata.get("players", [])):
                if "id" not in player:
                    player["id"] = f"player_{i}"
            
            # Filtrer les événements inconnus de la timeline
            if metadata.get("timeline"):
                metadata["timeline"] = [
                    event for event in metadata["timeline"]
                    if event.get("type") != "unknown"
                ]
                
                # Si la timeline est vide, ajouter des événements par défaut
                if not metadata["timeline"]:
                    metadata["timeline"] = [
                        {"type": "match_start", "time": 0.0},
                        {"type": "match_end", "time": metadata.get("duration", 300.0)}
                    ]
            
            # Valider la réponse
            response_data = {
                **metadata,
                "team0_score": metadata.get("team0_score", 0),
                "team1_score": metadata.get("team1_score", 0),
                "score": {
                    "blue": metadata.get("team0_score", 0),
                    "orange": metadata.get("team1_score", 0),
                    "winner": "blue" if metadata.get("team0_score", 0) > metadata.get("team1_score", 0) else "orange"
                }
            }
            return ReplayDataProcessed(**response_data)
            
        except Exception as e:
            print(f"[ERROR] Exception dans get_replay_metadata: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Erreur d'analyse du replay: {str(e)}")
    
    @app.get("/replays/{replay_id}/raw")
    async def get_replay_raw_json(replay_id: str, background_tasks: BackgroundTasks):
        """Obtenir le fichier JSON complet généré par rrrocket (avec --network-parse)"""
        replay_file = os.path.join(UPLOAD_DIR, f"{replay_id}.replay")
        
        if not os.path.exists(replay_file):
            raise HTTPException(status_code=404, detail="Fichier replay non trouvé")
            
        try:
            # Générer le JSON complet avec network_parse
            temp_json_file = await generate_replay_raw_json(replay_file, replay_id, network_parse=True)
            
            # Ajouter une tâche en arrière-plan pour supprimer le fichier temporaire
            async def remove_temp_file():
                # Attendre un petit délai pour s'assurer que le fichier a été envoyé
                await asyncio.sleep(5)
                if os.path.exists(temp_json_file):
                    try:
                        os.remove(temp_json_file)
                        print(f"[DEBUG] Fichier temporaire supprimé après envoi: {temp_json_file}")
                    except Exception as e:
                        print(f"[WARNING] Impossible de supprimer le fichier temporaire: {str(e)}")
            
            background_tasks.add_task(remove_temp_file)
            
            # Retourner le fichier JSON en tant que FileResponse
            return FileResponse(
                path=temp_json_file,
                media_type="application/json",
                filename=f"{replay_id}_full.json"
            )
            
        except Exception as e:
            print(f"[ERROR] Exception dans get_replay_raw_json: {str(e)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Erreur de génération du JSON complet: {str(e)}")
    
    # Route de compatibilité avec l'ancien endpoint (renvoie vers le nouveau /meta)
    @app.get("/replays/{replay_id}/metadata")
    async def get_replay_metadata_compat(replay_id: str):
        """Route de compatibilité avec l'ancien endpoint"""
        return await get_replay_metadata(replay_id)
        
    # Route de compatibilité avec l'ancien endpoint de frames (renvoie vers le nouvel endpoint raw)
    @app.get("/replays/{replay_id}/frames")
    async def get_replay_frames_compat(replay_id: str, background_tasks: BackgroundTasks):
        """Route de compatibilité avec l'ancien endpoint de frames"""
        return await get_replay_raw_json(replay_id, background_tasks) 