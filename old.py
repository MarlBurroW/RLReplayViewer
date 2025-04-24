import os
import uuid
import json
import math
import struct
import subprocess
from typing import List, Optional, Dict, Any, Tuple
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import aiofiles
# import pandas as pd # Not used anymore?
# import numpy as np # Not used anymore?
from pydantic import BaseModel
import traceback
import asyncio
import copy
import time

# Création des dossiers nécessaires
os.makedirs("uploads", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Stockage des tâches en arrière-plan
background_tasks = {}

app = FastAPI(title="Rocket League Replay Analyzer")

# --- Classes utilitaires pour la sérialisation binaire ---
class BinaryFramesWriter:
    """Classe pour sérialiser les frames en format binaire."""
    
    @staticmethod
    async def write_frames_to_binary(frames: List[Dict[str, Any]], output_path: str):
        """Écrit les frames au format binaire dans un fichier.
        
        Format:
        - Header: "RLFRAME\0" (8 bytes)
        - Version: 1 (2 bytes, little endian)
        - Frame count: N (4 bytes, little endian)
        - Pour chaque frame:
            - Time: float (4 bytes)
            - Delta: float (4 bytes)
            - Ball position: [x, y, z] (3 x 4 bytes)
            - Ball rotation: [x, y, z, w] (4 x 4 bytes)
            - Ball velocity: [x, y, z] (3 x 4 bytes)
            - Car count: n (2 bytes)
            - Pour chaque voiture:
                - ID length: len(car_id) (1 byte)
                - ID: car_id (variable)
                - Position: [x, y, z] (3 x 4 bytes)
                - Rotation: [x, y, z, w] (4 x 4 bytes)
                - Boost: (1 byte, 0-255)
        """
        if not frames:
            print("[WARNING] Aucune frame à sérialiser")
            return
        
        try:
            # Ouvrir le fichier en écriture binaire
            async with aiofiles.open(output_path, 'wb') as f:
                # Écrire l'en-tête
                await f.write(b"RLFRAME\0")  # 8 bytes magic number
                await f.write(struct.pack("<H", 1))  # Version 1, 2 bytes
                await f.write(struct.pack("<I", len(frames)))  # Nombre de frames, 4 bytes
                
                # Écrire chaque frame
                for frame in frames:
                    # Time et delta
                    await f.write(struct.pack("<f", frame.get("time", 0.0)))
                    await f.write(struct.pack("<f", frame.get("delta", 0.0)))
                    
                    # Ball data
                    ball = frame.get("ball", {})
                    # Position
                    ball_pos = ball.get("position", [0.0, 0.0, 93.0])
                    for coord in ball_pos[:3]:  # Assurer 3 valeurs
                        await f.write(struct.pack("<f", float(coord)))
                    
                    # Rotation
                    ball_rot = ball.get("rotation", [0.0, 0.0, 0.0, 1.0])
                    for coord in ball_rot[:4]:  # Assurer 4 valeurs
                        await f.write(struct.pack("<f", float(coord)))
                    
                    # Velocity
                    ball_vel = ball.get("velocity", [0.0, 0.0, 0.0])
                    for coord in ball_vel[:3]:  # Assurer 3 valeurs
                        await f.write(struct.pack("<f", float(coord)))
                    
                    # Cars data
                    cars = frame.get("cars", {})
                    await f.write(struct.pack("<H", len(cars)))  # Nombre de voitures
                    
                    for car_id, car_data in cars.items():
                        # ID de la voiture (variable)
                        car_id_bytes = str(car_id).encode('utf-8')
                        await f.write(struct.pack("<B", len(car_id_bytes)))  # Longueur de l'ID
                        await f.write(car_id_bytes)  # ID
                        
                        # Position
                        car_pos = car_data.get("position", [0.0, 0.0, 17.0])
                        for coord in car_pos[:3]:
                            await f.write(struct.pack("<f", float(coord)))
                        
                        # Rotation
                        car_rot = car_data.get("rotation", [0.0, 0.0, 0.0, 1.0])
                        for coord in car_rot[:4]:
                            await f.write(struct.pack("<f", float(coord)))
                        
                        # Boost (0-255)
                        boost = car_data.get("boost", 33)
                        await f.write(struct.pack("<B", min(255, max(0, int(boost)))))
                
                print(f"[INFO] Fichier binaire écrit avec succès: {output_path}")
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'écriture du fichier binaire: {e}")
            traceback.print_exc()


class BinaryFramesReader:
    """Classe pour désérialiser les frames depuis un format binaire."""
    
    @staticmethod
    async def read_frames_from_binary(input_path: str) -> List[Dict[str, Any]]:
        """Lit les frames depuis un fichier binaire."""
        frames = []
        
        try:
            # Lire tout le fichier en mémoire
            async with aiofiles.open(input_path, 'rb') as f:
                data = await f.read()
            
            # Vérifier l'en-tête
            if not data.startswith(b"RLFRAME\0"):
                print("[ERROR] Format de fichier binaire invalide")
                return frames
            
            # Lire la version et le nombre de frames
            offset = 8  # Après le magic number
            version = struct.unpack("<H", data[offset:offset+2])[0]
            offset += 2
            
            frame_count = struct.unpack("<I", data[offset:offset+4])[0]
            offset += 4
            
            print(f"[INFO] Lecture de {frame_count} frames, version {version}")
            
            # Lire chaque frame
            for _ in range(frame_count):
                # Time et delta
                time = struct.unpack("<f", data[offset:offset+4])[0]
                offset += 4
                delta = struct.unpack("<f", data[offset:offset+4])[0]
                offset += 4
                
                # Ball data
                ball_pos = []
                for _ in range(3):
                    ball_pos.append(struct.unpack("<f", data[offset:offset+4])[0])
                    offset += 4
                
                ball_rot = []
                for _ in range(4):
                    ball_rot.append(struct.unpack("<f", data[offset:offset+4])[0])
                    offset += 4
                
                ball_vel = []
                for _ in range(3):
                    ball_vel.append(struct.unpack("<f", data[offset:offset+4])[0])
                    offset += 4
                
                # Cars data
                car_count = struct.unpack("<H", data[offset:offset+2])[0]
                offset += 2
                
                cars = {}
                for _ in range(car_count):
                    # ID de la voiture
                    id_length = struct.unpack("<B", data[offset:offset+1])[0]
                    offset += 1
                    car_id = data[offset:offset+id_length].decode('utf-8')
                    offset += id_length
                    
                    # Position
                    car_pos = []
                    for _ in range(3):
                        car_pos.append(struct.unpack("<f", data[offset:offset+4])[0])
                        offset += 4
                    
                    # Rotation
                    car_rot = []
                    for _ in range(4):
                        car_rot.append(struct.unpack("<f", data[offset:offset+4])[0])
                        offset += 4
                    
                    # Boost
                    boost = struct.unpack("<B", data[offset:offset+1])[0]
                    offset += 1
                    
                    cars[car_id] = {
                        "position": car_pos,
                        "rotation": car_rot,
                        "boost": boost
                    }
                
                # Ajouter la frame
                frames.append({
                    "time": time,
                    "delta": delta,
                    "ball": {
                        "position": ball_pos,
                        "rotation": ball_rot,
                        "velocity": ball_vel
                    },
                    "cars": cars
                })
            
            print(f"[INFO] {len(frames)} frames lues avec succès depuis {input_path}")
        except Exception as e:
            print(f"[ERROR] Erreur lors de la lecture du fichier binaire: {e}")
            traceback.print_exc()
        
        return frames

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Autorise toutes les origines
    allow_credentials=True,
    allow_methods=["*"],  # Autorise toutes les méthodes
    allow_headers=["*"],  # Autorise tous les headers
)

# Montage des fichiers statiques
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Modèles Pydantic pour structurer les données ---
class ReplayInfo(BaseModel):
    id: str
    filename: str
    duration: Optional[float] = None

class TeamStats(BaseModel):
    id: str
    score: int = 0
    name: str

class PlayerStatsDetails(BaseModel):
    score: int = 0
    goals: int = 0
    assists: int = 0
    saves: int = 0
    shots: int = 0

class PlayerInfo(BaseModel):
    id: str                          # Identifiant unique et cohérent
    name: str
    team: int
    platform: Optional[str] = None
    is_bot: bool = False
    actor_id: Optional[int] = None
    platform_id: Optional[str] = None  # ID spécifique à la plateforme
    epic_id: Optional[str] = None      # ID Epic Games
    steam_id: Optional[str] = None     # ID Steam
    psn_id: Optional[str] = None       # ID PlayStation
    xbox_id: Optional[str] = None      # ID Xbox
    stats: PlayerStatsDetails = PlayerStatsDetails()

class TimelineEvent(BaseModel):
    type: str
    time: float
    player: Optional[str] = None
    team: Optional[int] = None

class BallState(BaseModel):
    position: List[float] = [0.0, 0.0, 93.0]
    rotation: List[float] = [0.0, 0.0, 0.0, 1.0]
    velocity: List[float] = [0.0, 0.0, 0.0]

class CarState(BaseModel):
    position: List[float] = [0.0, 0.0, 17.0]
    rotation: List[float] = [0.0, 0.0, 0.0, 1.0]
    velocity: Optional[List[float]] = None
    boost: int = 33

class FrameData(BaseModel):
    time: float
    delta: float
    ball: Optional[BallState] = None
    cars: Dict[str, CarState] = {}

class ReplayDataProcessed(BaseModel):
    id: str
    teams: Dict[str, TeamStats] = {}
    players: Dict[str, PlayerInfo] = {}
    timeline: List[TimelineEvent] = []
    frames: List[FrameData] = []
    duration: float = 300.0
    map_name: Optional[str] = None
    match_type: Optional[str] = None
    game_type: Optional[str] = None
    date: Optional[str] = None
    # Table de correspondance entre acteurs et joueurs
    car_player_map: Dict[str, str] = {}  # {car_id: player_id}

# --- Utility function to get nested property values ---
def get_prop_value(prop_dict):
    """Extracts the actual value from a Rattletrap property structure."""
    if not isinstance(prop_dict, dict) or 'value' not in prop_dict:
        return None
    val_container = prop_dict['value']
    # The actual value is often nested (e.g., {"int": 5}, {"array": [...]})
    if isinstance(val_container, dict) and len(val_container) == 1:
        return list(val_container.values())[0]
    return val_container

# --- Schema-based data extraction functions ---

def find_players_and_teams_from_schema(header_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, int]]:
    """Extracts players and teams directly from header properties based on schema."""
    players: Dict[str, Any] = {}
    teams: Dict[str, Any] = {}
    player_actor_map: Dict[str, int] = {} # Map OnlineID/PlayerKey (str) to ActorID (int)

    if not isinstance(header_data, dict) or 'properties' not in header_data or 'elements' not in header_data['properties']:
        print("[WARNING] Header properties not found or invalid structure for schema parsing.")
        return players, teams, player_actor_map

    print("[INFO] Parsing header properties for players and teams...")
    header_props = header_data['properties']['elements']

    actor_id_prop_map: Dict[str, int] = {}
    player_name_to_id_map: Dict[str, str] = {}  # Pour faire correspondre les noms aux IDs

    # --- Premier passage : Explorer toutes les propriétés pour repérer les IDs d'acteurs et les correspondances ---
    print("[DEBUG] Scanning all properties for actor IDs and player data...")
    for key, prop_data in header_props:
        # PlayerStats contient à la fois les noms et les IDs d'acteurs
        if key == 'PlayerStats' and prop_data.get('kind') == 'ArrayProperty':
            player_stats_array = get_prop_value(prop_data)
            if isinstance(player_stats_array, list):
                for player_prop_list in player_stats_array:
                    if isinstance(player_prop_list, dict) and 'elements' in player_prop_list:
                        online_id: Optional[str] = None
                        player_name: Optional[str] = None
                        actor_id: Optional[int] = None
                        platform: Optional[str] = None
                        player_stats = {}
                        is_bot = False

                        for sub_key, sub_prop in player_prop_list['elements']:
                            sub_value = get_prop_value(sub_prop)
                            kind = sub_prop.get('kind')
                            
                            if sub_key == 'OnlineID' and kind == 'QWordProperty':
                                online_id = str(sub_value)
                            elif sub_key == 'Name' and kind == 'StrProperty':
                                player_name = sub_value
                            elif sub_key == 'PlayerID' and kind == 'IntProperty':  # C'est l'ID d'acteur
                                actor_id = sub_value
                            elif sub_key == 'bBot' and kind == 'BoolProperty':
                                is_bot = sub_value
                            elif sub_key == 'Platform' and kind == 'StrProperty':
                                platform = sub_value
                            # Collecter les statistiques du joueur
                            elif kind == 'IntProperty' and sub_key in ['Score', 'Goals', 'Assists', 'Saves', 'Shots']:
                                player_stats[sub_key.lower()] = sub_value
                            # Collecter les données d'identification supplémentaires
                            elif sub_key == 'UniqueId' and kind == 'StructProperty':
                                # Récupérer les données spécifiques à la plateforme
                                if isinstance(sub_value, dict) and 'fields' in sub_value:
                                    unique_fields = sub_value.get('fields', {})
                                    if 'Platform' in unique_fields:
                                        platform = unique_fields.get('Platform')
                                    
                                    # Récupérer les IDs spécifiques à la plateforme
                                    if platform and 'Uid' in unique_fields:
                                        uid = unique_fields.get('Uid')
                                        if uid and str(uid) != "0":
                                            if 'Steam' in platform:
                                                player_stats['steam_id'] = str(uid)
                                            elif 'PS4' in platform or 'PSN' in platform:
                                                player_stats['psn_id'] = str(uid)
                                            elif 'Xbox' in platform:
                                                player_stats['xbox_id'] = str(uid)
                                    
                                    # Récupérer spécifiquement l'EpicID
                                    if 'EpicAccountId' in unique_fields:
                                        epic_id = unique_fields.get('EpicAccountId')
                                        if epic_id:
                                            player_stats['epic_id'] = str(epic_id)

                        # Générer une clé unique pour ce joueur
                        player_key = online_id if online_id and online_id != "0" else player_name
                        
                        if player_key:
                            # Enregistrer la correspondance nom -> player_key pour une utilisation ultérieure
                            if player_name:
                                player_name_to_id_map[player_name] = player_key
                            
                            # Créer ou mettre à jour les données du joueur
                            if player_key not in players:
                                players[player_key] = {
                                    'name': player_name,
                                    'team': None,  # Sera rempli dans la deuxième passe
                                    'is_bot': is_bot,
                                    'platform': platform,
                                    'stats': player_stats
                                }
                            else:
                                # Mettre à jour les données existantes
                                players[player_key].update({
                                    'name': player_name,
                                    'is_bot': is_bot,
                                    'platform': platform
                                })
                                # Mettre à jour les stats
                                if 'stats' not in players[player_key]:
                                    players[player_key]['stats'] = {}
                                players[player_key]['stats'].update(player_stats)
                            
                            # Si nous avons trouvé un actor_id, l'enregistrer
                            if actor_id is not None:
                                player_actor_map[player_key] = actor_id
                                if 'actor_id' not in players[player_key]:
                                    players[player_key]['actor_id'] = actor_id
                                print(f"[DEBUG] Mapped player '{player_key}' to actor ID {actor_id}")

        # Teams contient les données d'équipe
        elif key == 'Teams' and prop_data.get('kind') == 'ArrayProperty':
            teams_array = get_prop_value(prop_data)
            if isinstance(teams_array, list):
                for team_idx, team_prop_list in enumerate(teams_array):
                    if isinstance(team_prop_list, dict) and 'elements' in team_prop_list:
                        team_id = str(team_idx)
                        team_name = None
                        team_score = 0
                        
                        for sub_key, sub_prop in team_prop_list['elements']:
                            sub_value = get_prop_value(sub_prop)
                            kind = sub_prop.get('kind')
                            
                            if sub_key == 'Score' and kind == 'IntProperty':
                                team_score = sub_value
                            elif sub_key == 'TeamName' and kind == 'NameProperty':
                                team_name = sub_value
                        
                        # Ajouter l'équipe
                        teams[team_id] = {
                            'id': team_id,
                            'name': team_name if team_name else f"Team {team_idx}",
                            'score': team_score
                        }
                        print(f"[DEBUG] Added team {team_id}: {team_name}, score: {team_score}")
        
        # PRI_TA (Archetype PlayerReplicationInfo) contient souvent la correspondance joueur/équipe
        elif key.startswith('PRI_TA') and prop_data.get('kind') == 'ObjectProperty':
            pri_data = get_prop_value(prop_data)
            if isinstance(pri_data, dict) and 'properties' in pri_data and 'elements' in pri_data['properties']:
                player_name = None
                team_num = None
                actor_id = None
                
                # Essayer d'extraire l'actorId de l'objet lui-même
                if 'actor_id' in pri_data:
                    actor_id = pri_data['actor_id']
                
                for sub_key, sub_prop in pri_data['properties']['elements']:
                    sub_value = get_prop_value(sub_prop)
                    kind = sub_prop.get('kind')
                    
                    if sub_key == 'PlayerName' and kind in ['StrProperty', 'NameProperty']:
                        player_name = sub_value
                    elif sub_key == 'Team' and kind == 'ObjectProperty':
                        # Essayer d'extraire l'équipe du joueur
                        if isinstance(sub_value, dict) and 'actor_id' in sub_value:
                            # Format possible: TeamID = actor_id % 2
                            team_actor_id = sub_value['actor_id']
                            team_num = team_actor_id % 2  # 0 = Bleu, 1 = Orange
                    elif sub_key == 'TeamNum' and kind == 'IntProperty':
                        team_num = sub_value
                
                # Si nous avons un nom de joueur et une équipe, mettre à jour les données du joueur
                if player_name and team_num is not None:
                    # Trouver le joueur par son nom
                    if player_name in player_name_to_id_map:
                        player_key = player_name_to_id_map[player_name]
                        if player_key in players:
                            players[player_key]['team'] = team_num
                        player_key = online_id if online_id is not None and online_id != "0" else player_name # Use OnlineID if valid, else name
                        if player_key is not None and actor_id is not None:
                            print(f"[DEBUG]   Mapped Player Key '{player_key}' to Actor ID {actor_id}")
                            actor_id_prop_map[player_key] = actor_id
                        # else:
                            # print(f"[DEBUG]   Could not map: key={player_key}, actor_id={actor_id}")

    # --- Second Pass: Extract Teams and PlayerStats, using the ActorID map ---
    print("[DEBUG] Second Pass: Extracting Team and Player Data...")
    for key, prop_data in header_props:
        prop_value = get_prop_value(prop_data)

        # Extract Teams
        if key == 'Teams' and prop_data.get('kind') == 'ArrayProperty' and isinstance(prop_value, list):
            print(f"[DEBUG] Processing Teams Property (found {len(prop_value)} entries)")
            for team_index, team_prop_list in enumerate(prop_value):
                if isinstance(team_prop_list, dict) and 'elements' in team_prop_list:
                    team_data: Dict[str, Any] = {'id': str(team_index)}
                    print(f"[DEBUG]  Processing Team Index {team_index}: {team_prop_list['elements']}")
                    for sub_key, sub_prop in team_prop_list['elements']:
                        sub_value = get_prop_value(sub_prop)
                        kind = sub_prop.get('kind')
                        # print(f"[DEBUG]   Team SubProp: key={sub_key}, kind={kind}, value={sub_value}") # Verbose
                        if sub_key == 'Score' and kind == 'IntProperty':
                            team_data['score'] = sub_value
                            print(f"[DEBUG]    Found Score: {sub_value}")
                        elif sub_key == 'TeamName' and kind == 'NameProperty':
                            team_data['name'] = sub_value
                    if 'score' in team_data: # Only add if score was found
                        teams[str(team_index)] = team_data
                    else:
                        print(f"[WARNING] Team index {team_index} processed, but no 'Score' found.")


        # Extract Player Stats
        elif key == 'PlayerStats' and prop_data.get('kind') == 'ArrayProperty' and isinstance(prop_value, list):
            print(f"[DEBUG] Processing PlayerStats Property (found {len(prop_value)} entries)")
            for player_prop_list in prop_value:
                 if isinstance(player_prop_list, dict) and 'elements' in player_prop_list:
                    player_data: Dict[str, Any] = {'stats': {}}
                    online_id: Optional[str] = None
                    player_name: Optional[str] = None
                    actor_id: Optional[int] = None # Actor ID found in *this* specific PlayerStats entry

                    for sub_key, sub_prop in player_prop_list['elements']:
                        sub_value = get_prop_value(sub_prop)
                        kind = sub_prop.get('kind')

                        if sub_key == 'OnlineID' and kind == 'QWordProperty':
                            online_id = str(sub_value)
                            # Handle potential '0' OnlineID for bots/splitscreen?
                            if online_id == "0":
                                print("[DEBUG]   Found OnlineID '0', likely a bot or splitscreen.")
                                online_id = None # Treat as if no OnlineID for key generation
                        elif sub_key == 'Name' and kind == 'StrProperty':
                            player_data['name'] = sub_value
                            player_name = sub_value # Keep name for potential key
                        elif sub_key == 'Team' and kind == 'IntProperty':
                            player_data['team'] = sub_value
                        elif sub_key == 'PlayerID' and kind == 'IntProperty': # Actor ID
                            actor_id = sub_value
                            player_data['actor_id'] = actor_id # Store it in player data too
                        elif kind == 'IntProperty' and sub_key not in ['Team', 'PlayerID']:
                             player_data['stats'][sub_key.lower()] = sub_value

                    # Determine the primary key for this player (OnlineID > Name)
                    player_key = online_id if online_id else player_name
                    if player_key and 'name' in player_data: # Need at least a key and a name
                        players[player_key] = player_data
                        print(f"[DEBUG]  Stored player data for key '{player_key}': {player_data}")

                        # --- Populate player_actor_map ---
                        # Priority: Actor ID found in this specific PlayerStats entry
                        final_actor_id: Optional[int] = None
                        if actor_id is not None:
                            final_actor_id = actor_id
                            print(f"[DEBUG]   Using ActorID {final_actor_id} from current PlayerStats for '{player_key}'")
                        # Fallback: Actor ID found in the first pass map
                        elif player_key in actor_id_prop_map:
                            final_actor_id = actor_id_prop_map[player_key]
                            print(f"[DEBUG]   Using ActorID {final_actor_id} from first pass map for '{player_key}'")
                        else:
                             print(f"[WARNING] Could not determine ActorID for player '{player_key}'. Frame data might be missing.")

                        if final_actor_id is not None:
                            player_actor_map[player_key] = final_actor_id
                    else:
                         print(f"[WARNING] Could not store player data - missing key or name. OnlineID={online_id}, Name={player_name}")


    # Add default team names if missing and teams exist
    if '0' in teams and teams['0'].get('name') is None: teams['0']['name'] = "Équipe Bleue"
    if '1' in teams and teams['1'].get('name') is None: teams['1']['name'] = "Équipe Orange"

    print(f"[INFO] Found {len(players)} players and {len(teams)} teams from header.")
    print(f"[DEBUG] Final Player Actor Map: {player_actor_map}")
    return players, teams, player_actor_map


def extract_frames_from_schema(content_data: Dict[str, Any], player_actor_map: Dict[str, int], fps: float, player_ids: List[str], players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait les frames à partir des structures de données connues, sans générer de frames synthétiques.
    
    Tente d'extraire les frames depuis différentes structures connues du fichier JSON.
    Si aucune frame n'est trouvée, une erreur est levée au lieu de générer des frames synthétiques.
    """
    frames = []
    car_player_map = {}
    
    # Vérification des données
    if not isinstance(players_data, dict):
        print("[WARNING] Les données des joueurs ne sont pas un dictionnaire")
        raise ValueError("Les données des joueurs ne sont pas correctement formatées")
    
    try:
        # Essayer d'abord la structure network_frames (moderne)
        if "network_frames" in content_data:
            print("[INFO] Extraction des frames depuis network_frames")
            frames, car_player_map = extract_frames_from_network_frames(content_data, player_actor_map, fps)
        
        # Si pas de frames depuis network_frames, essayer la structure ticks (ancienne)
        if not frames and "ticks" in content_data:
            print("[INFO] Extraction des frames depuis ticks")
            frames, car_player_map = extract_frames_from_ticks(content_data, player_actor_map, fps)
        
        # Si toujours pas de frames, essayer la structure frames (alternative)
        if not frames and "frames" in content_data:
            print("[INFO] Extraction des frames depuis frames")
            frames, car_player_map = extract_frames_from_old_frames(content_data, player_actor_map, fps)
        
        # Vérifier si des frames ont été extraites
        if not frames:
            print("[ERROR] Aucune frame trouvée dans les structures connues")
            raise ValueError("Aucune frame trouvée dans les structures connues du fichier de replay")
        
        print(f"[INFO] {len(frames)} frames extraites avec succès, {len(car_player_map)} voitures mappées")
        return frames, car_player_map
    
    except Exception as e:
        print(f"[ERROR] Exception lors de l'extraction des frames: {e}")
        traceback.print_exc()
        # Au lieu de générer des frames synthétiques, propager l'erreur
        raise ValueError(f"Erreur lors de l'extraction des frames: {str(e)}")

def extract_frames_from_actors(actors_list: List[Dict[str, Any]], fps: float, player_ids: List[str], players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait des données de frames à partir de la liste d'acteurs."""
    frames = []
    car_player_map = {}
    
    print("[INFO] Tentative d'extraction des frames à partir des acteurs...")
    
    try:
        # Trier les acteurs par type (balle, voiture) et par timestamp
        ball_actors = []
        car_actors = {}  # {acteur_id: [updates]}
        
        # Créer une table de correspondance nom -> player_id
        name_to_player_id = {}
        for player_id, player_data in players_data.items():
            if isinstance(player_data, dict) and "name" in player_data:
                name_to_player_id[player_data["name"]] = player_id
            elif hasattr(player_data, "name"):
                name_to_player_id[player_data.name] = player_id
        
        # Identifier les types d'acteurs et organiser les données
        for actor in actors_list:
            actor_id = actor.get("actor_id")
            object_name = actor.get("object_name", "")
            actor_class = actor.get("class_name", "")
            
            # Déterminer le type (balle, voiture, etc.)
            if any(ball_term in object_name.lower() or ball_term in actor_class.lower() 
                  for ball_term in ["ball", "sphere", "basketball"]):
                ball_actors.append(actor)
                print(f"[DEBUG] Acteur de type balle trouvé: {actor_id} ({object_name})")
            elif any(car_term in object_name.lower() or car_term in actor_class.lower() 
                    for car_term in ["car", "vehicle", "octane", "dominus", "battle"]):
                if actor_id not in car_actors:
                    car_actors[actor_id] = []
                car_actors[actor_id].append(actor)
                print(f"[DEBUG] Acteur de type voiture trouvé: {actor_id} ({object_name})")
        
        print(f"[DEBUG] Trouvé: {len(ball_actors)} acteurs de type balle, {len(car_actors)} acteurs de type voiture")
        
        # Associer les voitures aux joueurs en utilisant diverses méthodes
        
        # 1. Essayer via les propriétés des acteurs
        for actor_id, actor_list in car_actors.items():
            for actor in actor_list:
                # Chercher le nom du joueur dans les propriétés
                if "properties" in actor:
                    props = actor.get("properties", {})
                    player_name = None
                    
                    # Chercher différentes clés qui pourraient contenir le nom
                    for prop_key in ["PlayerName", "Player", "OwnerName", "Owner", "name"]:
                        if prop_key in props:
                            player_name = props[prop_key]
                            if isinstance(player_name, str) and player_name in name_to_player_id:
                                player_id = name_to_player_id[player_name]
                                car_id = f"car_{actor_id}"
                                car_player_map[car_id] = player_id
                                print(f"[DEBUG] Association via propriété: {car_id} -> {player_id} ({player_name})")
                                break
        
        # 2. Essayer via l'ID d'acteur lui-même
        if len(car_player_map) < len(player_ids):
            for player_id, player_data in players_data.items():
                actor_id = None
                if isinstance(player_data, dict):
                    actor_id = player_data.get("actor_id")
                elif hasattr(player_data, "actor_id"):
                    actor_id = player_data.actor_id
                
                if actor_id is not None and actor_id in car_actors:
                    car_id = f"car_{actor_id}"
                    car_player_map[car_id] = player_id
                    print(f"[DEBUG] Association via ID d'acteur: {car_id} -> {player_id}")
        
        # 3. Si aucune association n'est trouvée, associer arbitrairement
        if not car_player_map:
            print("[WARNING] Aucune association naturelle trouvée, assignation arbitraire")
            unassigned_players = [p for p in player_ids if not any(v == p for v in car_player_map.values())]
            unassigned_cars = [aid for aid in car_actors.keys() if f"car_{aid}" not in car_player_map]
            
            # Associer les voitures non assignées aux joueurs non assignés
            for i, actor_id in enumerate(unassigned_cars):
                if i < len(unassigned_players):
                    car_id = f"car_{actor_id}"
                    player_id = unassigned_players[i]
                    car_player_map[car_id] = player_id
                    print(f"[DEBUG] Association arbitraire: {car_id} -> {player_id}")
                else:
                    break
            
            # S'il reste des joueurs non assignés mais plus de voitures, créer des correspondances virtuelles
            if len(unassigned_players) > len(unassigned_cars):
                for i, player_id in enumerate(unassigned_players[len(unassigned_cars):]):
                    virtual_car_id = f"virtual_car_{i+1000}"
                    car_player_map[virtual_car_id] = player_id
                    print(f"[DEBUG] Association virtuelle: {virtual_car_id} -> {player_id}")
        
        # Récupérer les timestamps uniques pour créer les frames
        timestamps = set()
        
        # Explorer les acteurs pour trouver tous les timestamps disponibles
        for actor_list in [ball_actors] + list(car_actors.values()):
            for actor in actor_list:
                # Chercher les timestamps dans différentes structures
                
                # 1. Dans les "updates"
                if "updates" in actor and isinstance(actor["updates"], list):
                    for update in actor["updates"]:
                        if "time" in update:
                            timestamps.add(update["time"])
                
                # 2. Dans les "frames"
                if "frames" in actor and isinstance(actor["frames"], list):
                    for frame in actor["frames"]:
                        if isinstance(frame, dict) and "time" in frame:
                            timestamps.add(frame["time"])
                
                # 3. Dans les "states"
                if "states" in actor and isinstance(actor["states"], list):
                    for state in actor["states"]:
                        if isinstance(state, dict) and "time" in state:
                            timestamps.add(state["time"])
        
        # Trier les timestamps
        sorted_timestamps = sorted(timestamps)
        print(f"[DEBUG] {len(sorted_timestamps)} timestamps uniques trouvés")
        
        if not sorted_timestamps:
            print("[WARNING] Aucun timestamp trouvé, création de frames synthétiques")
            return create_synthetic_frames(player_ids, players_data)
        
        # Si trop de timestamps, faire un échantillonnage
        if len(sorted_timestamps) > 600:
            sample_rate = len(sorted_timestamps) // 600
            sorted_timestamps = sorted_timestamps[::sample_rate]
            print(f"[DEBUG] Échantillonnage: {len(sorted_timestamps)} timestamps après échantillonnage")
        
        # Pour chaque timestamp, créer une frame
        prev_time = 0
        for i, timestamp in enumerate(sorted_timestamps):
            delta = timestamp - prev_time if i > 0 else 0
            prev_time = timestamp
            
            # Créer une frame vide
            frame = {
                "time": timestamp,
                "delta": delta,
                "ball": {
                    "position": [0, 0, 93],
                    "rotation": [0, 0, 0, 1],
                    "velocity": [0, 0, 0]
                },
                "cars": {}
            }
            
            # Fonction pour mettre à jour les données de la balle ou d'une voiture
            def update_actor_data(frame_data, update_data, is_ball=False):
                # Position
                if "position" in update_data and isinstance(update_data["position"], list):
                    frame_data["position"] = update_data["position"][:3]
                elif "loc" in update_data and isinstance(update_data["loc"], list):
                    frame_data["position"] = update_data["loc"][:3]
                elif "location" in update_data and isinstance(update_data["location"], list):
                    frame_data["position"] = update_data["location"][:3]
                
                # Rotation
                if "rotation" in update_data and isinstance(update_data["rotation"], list):
                    frame_data["rotation"] = update_data["rotation"][:4]
                elif "rot" in update_data and isinstance(update_data["rot"], list):
                    frame_data["rotation"] = update_data["rot"][:4]
                
                # Velocity (seulement pour la balle)
                if is_ball:
                    if "velocity" in update_data and isinstance(update_data["velocity"], list):
                        frame_data["velocity"] = update_data["velocity"][:3]
                    elif "vel" in update_data and isinstance(update_data["vel"], list):
                        frame_data["velocity"] = update_data["vel"][:3]
                
                # Boost (seulement pour les voitures)
                if not is_ball:
                    if "boost" in update_data:
                        try:
                            frame_data["boost"] = int(update_data["boost"])
                        except (ValueError, TypeError):
                            pass
                    elif "boost_amount" in update_data:
                        try:
                            frame_data["boost"] = int(update_data["boost_amount"])
                        except (ValueError, TypeError):
                            pass
            
            # Trouver les données de la balle à ce timestamp
            for actor in ball_actors:
                # Chercher dans différentes structures
                # 1. Dans "updates"
                if "updates" in actor and isinstance(actor["updates"], list):
                    for update in actor["updates"]:
                        if update.get("time") == timestamp:
                            update_actor_data(frame["ball"], update, is_ball=True)
                
                # 2. Dans "frames"
                if "frames" in actor and isinstance(actor["frames"], list):
                    for act_frame in actor["frames"]:
                        if isinstance(act_frame, dict) and act_frame.get("time") == timestamp:
                            update_actor_data(frame["ball"], act_frame, is_ball=True)
                
                # 3. Dans "states"
                if "states" in actor and isinstance(actor["states"], list):
                    for state in actor["states"]:
                        if isinstance(state, dict) and state.get("time") == timestamp:
                            update_actor_data(frame["ball"], state, is_ball=True)
            
            # Trouver les positions des voitures à ce timestamp
            for actor_id, actor_list in car_actors.items():
                car_id = f"car_{actor_id}"
                player_id = car_player_map.get(car_id)
                
                if not player_id:
                    continue  # Ignorer les voitures sans joueur associé
                
                # État par défaut de la voiture
                car_state = {
                    "position": [0, 0, 17],
                    "rotation": [0, 0, 0, 1],
                    "boost": 33
                }
                
                # Mise à jour des données depuis les différentes structures
                for actor in actor_list:
                    # 1. Dans "updates"
                    if "updates" in actor and isinstance(actor["updates"], list):
                        for update in actor["updates"]:
                            if isinstance(update, dict) and update.get("time") == timestamp:
                                update_actor_data(car_state, update)
                    
                    # 2. Dans "frames"
                    if "frames" in actor and isinstance(actor["frames"], list):
                        for act_frame in actor["frames"]:
                            if isinstance(act_frame, dict) and act_frame.get("time") == timestamp:
                                update_actor_data(car_state, act_frame)
                    
                    # 3. Dans "states"
                    if "states" in actor and isinstance(actor["states"], list):
                        for state in actor["states"]:
                            if isinstance(state, dict) and state.get("time") == timestamp:
                                update_actor_data(car_state, state)
                
                # Ajouter l'état de la voiture à la frame
                frame["cars"][player_id] = car_state
            
            # Ajouter les voitures virtuelles si elles existent
            for car_id, player_id in car_player_map.items():
                if car_id.startswith("virtual_car_") and player_id not in frame["cars"]:
                    # Créer une position virtuelle en fonction de l'équipe
                    team = get_player_team(player_id, players_data)
                    x_pos = 0
                    y_pos = 3000 if team == 0 else -3000
                    
                    # Faire un petit mouvement sinusoïdal pour l'animation
                    x_pos += 500 * math.sin(timestamp * 0.3)
                    
                    car_state = {
                        "position": [x_pos, y_pos, 17],
                        "rotation": [0, 0, math.sin(timestamp * 0.1), math.cos(timestamp * 0.1)],
                        "boost": 33
                    }
                    frame["cars"][player_id] = car_state
            
            # Ajouter la frame à la liste
            frames.append(frame)
        
        print(f"[INFO] {len(frames)} frames extraites à partir des acteurs avec {len(car_player_map)} voitures")
    
    except Exception as e:
        print(f"[ERROR] Erreur lors de l'extraction des frames à partir des acteurs: {e}")
        traceback.print_exc()
        
        # En cas d'erreur, retourner des frames synthétiques
        if not frames:
            print("[WARNING] Création de frames synthétiques suite à une erreur")
            return create_synthetic_frames(player_ids, players_data)
    
    return frames, car_player_map


def extract_frames_from_direct(direct_frames: List[Dict[str, Any]], fps: float, player_ids: List[str], players_data: Dict[str, Any], actor_player_map: Dict[int, str]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait des données de frames à partir du format direct de frames.
    
    Args:
        direct_frames: Liste de frames au format direct
        fps: Frames par seconde
        player_ids: Liste des IDs de joueurs normalisés
        players_data: Données des joueurs pour accéder à l'équipe et autres infos
        actor_player_map: Correspondance {actor_id: player_id}
        
    Returns:
        Tuple contenant les frames et la table de correspondance car_player_map
    """
    frames = []
    car_player_map = {}
    
    try:
        print(f"[INFO] Traitement de {len(direct_frames)} frames au format direct...")
        
        # Examiner la structure de la première frame pour comprendre le format
        if direct_frames and isinstance(direct_frames[0], dict):
            sample_frame = direct_frames[0]
            print(f"[DEBUG] Structure d'une frame directe: {list(sample_frame.keys())}")
        
        for frame_idx, raw_frame in enumerate(direct_frames):
            if not isinstance(raw_frame, dict):
                continue
            
            # Extraire le temps et delta
            time = raw_frame.get("time", frame_idx / fps)
            delta = raw_frame.get("delta", 1.0 / fps)
            
            # Structure de base pour la frame
            frame = {
                "time": time,
                "delta": delta,
                "ball": {
                    "position": [0, 0, 93],
                    "rotation": [0, 0, 0, 1],
                    "velocity": [0, 0, 0]
                },
                "cars": {}
            }
            
            # Traiter la balle - différentes structures possibles
            if "ball" in raw_frame and isinstance(raw_frame["ball"], dict):
                ball_data = raw_frame["ball"]
                
                # Position
                if "position" in ball_data and isinstance(ball_data["position"], list):
                    frame["ball"]["position"] = ball_data["position"][:3]
                elif "loc" in ball_data and isinstance(ball_data["loc"], list):
                    frame["ball"]["position"] = ball_data["loc"][:3]
                
                # Rotation
                if "rotation" in ball_data and isinstance(ball_data["rotation"], list):
                    frame["ball"]["rotation"] = ball_data["rotation"][:4]
                elif "rot" in ball_data and isinstance(ball_data["rot"], list):
                    frame["ball"]["rotation"] = ball_data["rot"][:4]
                
                # Vitesse
                if "velocity" in ball_data and isinstance(ball_data["velocity"], list):
                    frame["ball"]["velocity"] = ball_data["velocity"][:3]
                elif "vel" in ball_data and isinstance(ball_data["vel"], list):
                    frame["ball"]["velocity"] = ball_data["vel"][:3]
            
            # Traiter les voitures - différentes structures possibles
            if "cars" in raw_frame and isinstance(raw_frame["cars"], dict):
                for car_id_str, car_data in raw_frame["cars"].items():
                    process_car_data(car_id_str, car_data, frame, car_player_map, actor_player_map, players_data)
            elif "players" in raw_frame and isinstance(raw_frame["players"], dict):
                for player_id_str, player_data in raw_frame["players"].items():
                    if isinstance(player_data, dict) and "car" in player_data:
                        car_data = player_data["car"]
                        process_car_data(f"car_{player_id_str}", car_data, frame, car_player_map, 
                                        actor_player_map, players_data, direct_player_id=player_id_str)
            elif "actors" in raw_frame and isinstance(raw_frame["actors"], dict):
                for actor_id_str, actor_data in raw_frame["actors"].items():
                    if isinstance(actor_data, dict):
                        # Déterminer si c'est une voiture
                        is_car = False
                        if "type" in actor_data:
                            is_car = actor_data["type"].lower() in ["car", "vehicle", "archetypes.car", "archetypes.vehicle"]
                        elif "class" in actor_data:
                            is_car = "car" in actor_data["class"].lower() or "vehicle" in actor_data["class"].lower()
                        
                        if is_car:
                            process_car_data(f"car_{actor_id_str}", actor_data, frame, car_player_map, actor_player_map, players_data)
            
            # Ajouter la frame
            frames.append(frame)
        
        print(f"[INFO] Extrait {len(frames)} frames au format direct avec {len(car_player_map)} voitures")
        return frames, car_player_map
    
    except Exception as e:
        print(f"[ERROR] Exception dans extract_frames_from_direct: {e}")
        traceback.print_exc()
        return frames, car_player_map


def process_car_data(car_id_str: str, car_data: Dict[str, Any], frame: Dict[str, Any], 
                    car_player_map: Dict[str, str], actor_player_map: Dict[int, str], 
                    players_data: Dict[str, Any], direct_player_id: str = None):
    """Traite les données d'une voiture et les ajoute à la frame si possible.
    
    Args:
        car_id_str: Identifiant de la voiture
        car_data: Données de la voiture
        frame: Frame à laquelle ajouter les données
        car_player_map: Map de correspondance voiture-joueur à mettre à jour
        actor_player_map: Map de correspondance acteur-joueur
        players_data: Données des joueurs
        direct_player_id: ID de joueur direct si disponible
    """
    if not isinstance(car_data, dict):
        return
    
    # Déterminer le joueur associé à cette voiture
    player_id = None
    
    # 1. Utiliser l'ID direct si fourni
    if direct_player_id is not None:
        # Vérifier si cet ID est dans players_data
        if direct_player_id in players_data:
            player_id = direct_player_id
            car_player_map[car_id_str] = player_id
            print(f"[DEBUG] Association directe: {car_id_str} -> {player_id}")
    
    # 2. Essayer de trouver l'ID d'acteur dans la clé de voiture
    if player_id is None:
        car_actor_id = None
        if car_id_str.startswith("car_"):
            try:
                car_actor_id = int(car_id_str.split("_")[1])
            except (ValueError, IndexError):
                pass
        else:
            try:
                car_actor_id = int(car_id_str)
            except ValueError:
                pass
        
        if car_actor_id is not None and car_actor_id in actor_player_map:
            player_id = actor_player_map[car_actor_id]
            car_player_map[car_id_str] = player_id
            print(f"[DEBUG] Association par clé de voiture: {car_id_str} -> {player_id}")
    
    # 3. Essayer de trouver l'ID d'acteur dans les données de voiture
    if player_id is None and "actor_id" in car_data:
        try:
            actor_id = int(car_data["actor_id"])
            if actor_id in actor_player_map:
                player_id = actor_player_map[actor_id]
                car_player_map[car_id_str] = player_id
                print(f"[DEBUG] Association par actor_id: {car_id_str} -> {player_id}")
        except (ValueError, TypeError):
            pass
    
    # 4. Essayer par nom de joueur
    if player_id is None and "player_name" in car_data:
        player_name = car_data["player_name"]
        for pid, pdata in players_data.items():
            name = None
            if isinstance(pdata, dict):
                name = pdata.get("name")
            else:
                name = getattr(pdata, "name", None)
            
            if name == player_name:
                player_id = pid
                car_player_map[car_id_str] = player_id
                print(f"[DEBUG] Association par nom: {car_id_str} -> {player_id} ({player_name})")
                break
    
    # 5. Si on a une équipe, essayer de faire correspondre par équipe
    if player_id is None and "team" in car_data:
        car_team = car_data["team"]
        team_players = []
        
        # Trouver tous les joueurs de cette équipe
        for pid, pdata in players_data.items():
            team = None
            if isinstance(pdata, dict):
                team = pdata.get("team")
            else:
                team = getattr(pdata, "team", None)
            
            if team == car_team:
                team_players.append(pid)
        
        # S'il y a un seul joueur dans cette équipe, l'associer
        if len(team_players) == 1:
            player_id = team_players[0]
            car_player_map[car_id_str] = player_id
            print(f"[DEBUG] Association par équipe: {car_id_str} -> {player_id} (équipe {car_team})")
    
    # Si on a trouvé un joueur, ajouter les données de la voiture à la frame
    if player_id:
        car_state = {
            "position": [0, 0, 17],  # Position par défaut
            "rotation": [0, 0, 0, 1],  # Quaternion par défaut
            "boost": 33  # Boost par défaut
        }
        
        # Position - différents formats possibles
        if "position" in car_data and isinstance(car_data["position"], list):
            car_state["position"] = car_data["position"][:3]
        elif "loc" in car_data and isinstance(car_data["loc"], list):
            car_state["position"] = car_data["loc"][:3]
        
        # Rotation - différents formats possibles
        if "rotation" in car_data and isinstance(car_data["rotation"], list):
            car_state["rotation"] = car_data["rotation"][:4]
        elif "rot" in car_data and isinstance(car_data["rot"], list):
            car_state["rotation"] = car_data["rot"][:4]
        
        # Boost - différents formats possibles
        if "boost" in car_data:
            try:
                car_state["boost"] = int(car_data["boost"])
            except (ValueError, TypeError):
                pass
        elif "boost_amount" in car_data:
            try:
                car_state["boost"] = int(car_data["boost_amount"])
            except (ValueError, TypeError):
                pass
        
        # Ajouter la voiture à la frame
        frame["cars"][player_id] = car_state


def calculate_duration(header_data: Dict[str, Any], frames: List[Dict[str, Any]]) -> float:
    """Calculates replay duration from header properties or frame times."""
    duration: float = 300.0 # Default

    # Try header properties first
    num_frames_prop: Optional[int] = None
    fps_prop: Optional[float] = None
    if isinstance(header_data, dict) and 'properties' in header_data and 'elements' in header_data['properties']:
         for key, prop_data in header_data['properties']['elements']:
             prop_value = get_prop_value(prop_data)
             if key == 'NumFrames': num_frames_prop = prop_value
             if key == 'RecordFPS': fps_prop = prop_value

    if isinstance(num_frames_prop, int) and isinstance(fps_prop, (int, float)) and fps_prop > 0:
         duration = num_frames_prop / fps_prop
         print(f"[INFO] Duration calculated from header: {duration:.2f}s (Frames: {num_frames_prop}, FPS: {fps_prop})")
         return duration

    # Fallback to last frame time
    if frames:
        duration = frames[-1].get('time', duration)
        print(f"[INFO] Duration calculated from last frame time: {duration:.2f}s")
        return duration

    print("[WARNING] Could not determine duration accurately, using default 300s.")
    return duration


def generate_timeline_events(processed_data: Dict[str, Any], content_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Generates timeline events (e.g., goals based on score or messages)."""
    timeline: List[Dict[str, Any]] = []
    duration = processed_data.get("duration", 300.0)
    teams = processed_data.get("teams", {})
    players = processed_data.get("players", {}) # Keyed by player_key (OnlineID or Name)
    player_actor_map = processed_data.get("_player_actor_map", {}) # Need this map passed internally
    
    print("[INFO] Generating timeline events...")
    print(f"[DEBUG] Type de 'teams': {type(teams)}")
    
    # Vérifier si nous avons des données de buts dans les propriétés
    if isinstance(content_data, dict):
        # Rechercher directement les buts dans le JSON brut
        goals_found = False
        
        # Essayer de trouver les buts dans les propriétés de l'en-tête
        header_props = {}
        if "header_size" in content_data and "properties" in content_data:
            header_props = content_data.get("properties", {})
            
            # Extraire les buts depuis les propriétés Goals
            goals = header_props.get("Goals", [])
            if isinstance(goals, list) and goals:
                goals_found = True
                print(f"[DEBUG] Found {len(goals)} goals in header properties")
                
                for goal in goals:
                    if isinstance(goal, dict):
                        frame = goal.get("frame", 0)
                        player_name = goal.get("PlayerName", "Unknown")
                        team = goal.get("PlayerTeam", 0)
                        
                        # Convertir le frame en temps approximatif
                        fps = header_props.get("RecordFPS", 30.0)
                        goal_time = frame / fps if fps > 0 else 0
                        
                        timeline.append({
                            "type": "goal",
                            "time": round(goal_time, 2),
                            "player": player_name,  # Utiliser le nom du joueur directement
                            "team": team
                        })
                        print(f"[DEBUG] Added goal at time {goal_time}s by {player_name} for team {team}")
        
        # Si aucun but n'a été trouvé, essayer d'inférer à partir des scores d'équipe
        if not goals_found and teams:
            print("[INFO] No goals found in properties, inferring from team scores...")
            
            # Parcourir les équipes et leurs scores
            for team_id, team_data in teams.items():
                # Extraire le score - attention au type de team_data
                if isinstance(team_data, dict):
                    score = team_data.get("score", 0)
                else:
                    # Si team_data est un objet Pydantic, accéder à l'attribut score
                    score = getattr(team_data, "score", 0)
                
                if score > 0:
                    # Trouver les joueurs de cette équipe
                    team_players = []
                    for pid, pdata in players.items():
                        player_team = None
                        if isinstance(pdata, dict):
                            player_team = pdata.get("team")
                        else:
                            # Si pdata est un objet Pydantic
                            player_team = getattr(pdata, "team", None)
                        
                        if str(player_team) == team_id:
                            team_players.append(pid)
                    
                    # Si nous avons des joueurs, distribuer les buts
                    if team_players:
                        goal_interval = duration / (score + 1)
                        print(f"[DEBUG] Inferring {score} goals for team {team_id}, interval: {goal_interval}s")
                        
                        for i in range(score):
                            goal_time = (i + 1) * goal_interval
                            player_key = team_players[i % len(team_players)]
                            
                            timeline.append({
                                "type": "goal_inferred",
                                "time": round(goal_time, 2),
                                "player": player_key,
                                "team": int(team_id)
                            })
    
    # Trier les événements par temps
    timeline.sort(key=lambda x: x["time"])
    print(f"[INFO] Generated {len(timeline)} timeline events.")
    return timeline


def get_actor_id_from_player_stats(player_stat_entry: Dict[str, Any]) -> Optional[int]:
    """Extrait l'ID de l'acteur à partir d'une entrée de statistiques de joueur"""
    if not isinstance(player_stat_entry, dict):
        return None
    
    # Logique spécifique à extraire une fois qu'on comprend mieux la structure
    return None

def process_replay_metadata(replay_id: str, raw_data: Dict[str, Any]) -> ReplayDataProcessed:
    """
    Traite les données JSON brutes pour extraire métadonnées et frames.
    """
    print(f"[DEBUG] Traitement des données pour {replay_id}")
    
    # Initialiser l'objet de données traitées
    processed = ReplayDataProcessed(
        id=replay_id,
        teams={},
        players={},
        timeline=[],
        frames=[],
        duration=300.0  # Valeur par défaut
    )
    
    # Vérifier si nous avons un dictionnaire valide
    if not isinstance(raw_data, dict):
        print(f"[ERROR] Les données brutes ne sont pas un dictionnaire valide: {type(raw_data)}")
        return processed
    
    # --- Extraire les métadonnées de base ---
    header = raw_data.get("header", {})
    print(f"[DEBUG] Header keys: {list(header.keys() if isinstance(header, dict) else [])}")
    
    # Extraire les propriétés du header si disponibles
    header_props = {}
    if isinstance(header, dict) and "properties" in header and "elements" in header["properties"]:
        # Convertir la liste d'éléments en dictionnaire pour un accès plus facile
        for prop_pair in header["properties"]["elements"]:
            if isinstance(prop_pair, list) and len(prop_pair) == 2:
                key, value_obj = prop_pair
                if isinstance(value_obj, dict) and "value" in value_obj:
                    val_container = value_obj["value"]
                    # Extraire la valeur du conteneur
                    if isinstance(val_container, dict) and len(val_container) == 1:
                        header_props[key] = list(val_container.values())[0]
                    else:
                        header_props[key] = val_container
    
    print(f"[DEBUG] Propriétés extraites du header: {header_props}")
    
    # Attributs de base du replay
    if "header_size" in raw_data and "properties" in raw_data:
        props = raw_data.get("properties", {})
        # Extraire directement les métadonnées des propriétés
        processed.map_name = props.get("MapName")
        processed.game_type = raw_data.get("game_type")  # Déjà au niveau racine
        processed.match_type = props.get("MatchType")
        processed.date = props.get("Date")
        
        # Durée explicite si disponible
        if "TotalSecondsPlayed" in props:
            processed.duration = float(props.get("TotalSecondsPlayed", 300.0))
    else:
        # Tenter d'extraire du header_props si disponible
        processed.map_name = header_props.get("MapName")
        processed.game_type = header_props.get("GameMode") or raw_data.get("game_type")
        processed.match_type = header_props.get("MatchType")
        processed.date = header_props.get("Date")
    
    print(f"[DEBUG] Métadonnées extraites: Map={processed.map_name}, Type={processed.game_type}, Match={processed.match_type}, Date={processed.date}")
    
    # --- Extraire les joueurs et les équipes ---
    # Explorons la structure complète pour comprendre où sont les données
    players_and_teams = find_players_and_teams(raw_data, 0)
    
    # Si nous avons trouvé des équipes
    if players_and_teams.get("teams"):
        for team_id, team_data in players_and_teams["teams"].items():
            team_id_str = str(team_id)
            # Créer une instance TeamStats
            team_name = team_data.get("name")
            if not team_name:
                team_name = "Équipe Bleue" if team_id_str == "0" else "Équipe Orange"
            
            processed.teams[team_id_str] = TeamStats(
                id=team_id_str,
                name=team_name,
                score=team_data.get("score", 0)
            )
        print(f"[DEBUG] Équipes extraites: {processed.teams}")
    else:
        # Créer des équipes par défaut si aucune n'est trouvée
        # Chercher les scores d'équipe dans les propriétés
        team0_score = 0
        team1_score = 0
        if "header_size" in raw_data and "properties" in raw_data:
            props = raw_data.get("properties", {})
            team0_score = props.get("Team0Score", 0)
            team1_score = props.get("Team1Score", 0)
            # Si Team0Score n'existe pas, essayer avec 'BlueScore'
            if "Team0Score" not in props and "BlueScore" in props:
                team0_score = props.get("BlueScore", 0)
            # Si Team1Score n'existe pas, essayer avec 'OrangeScore'  
            if "Team1Score" not in props and "OrangeScore" in props:
                team1_score = props.get("OrangeScore", 0)
            
            # Si on a toujours pas de score, chercher qui est l'équipe gagnante
            winning_team = props.get("WinningTeam")
            if winning_team is not None:
                if str(winning_team) == "0":
                    team0_score = 1
                elif str(winning_team) == "1":
                    team1_score = 1
        
        processed.teams["0"] = TeamStats(id="0", name="Équipe Bleue", score=team0_score)
        processed.teams["1"] = TeamStats(id="1", name="Équipe Orange", score=team1_score)
        print(f"[DEBUG] Équipes par défaut créées: Bleue (score: {team0_score}), Orange (score: {team1_score})")
    
    # Si nous avons trouvé des joueurs
    if players_and_teams.get("players"):
        for player_id, player_data in players_and_teams["players"].items():
            # Créer les statistiques du joueur
            stats_data = player_data.get("stats", {})
            player_stats = PlayerStatsDetails(
                score=stats_data.get("score", 0),
                goals=stats_data.get("goals", 0),
                assists=stats_data.get("assists", 0),
                saves=stats_data.get("saves", 0),
                shots=stats_data.get("shots", 0)
            )
            
            # Extraire les données principales du joueur
            player_name = player_data.get("name", f"Joueur {player_id}")
            player_team = player_data.get("team", 0)
            
            # Créer une instance PlayerInfo avec un ID normalisé
            normalized_id = player_data.get("id", normalize_player_id(player_data))
            
            processed.players[normalized_id] = PlayerInfo(
                id=normalized_id,
                name=player_name,
                team=player_team,
                platform=player_data.get("platform"),
                is_bot=player_data.get("is_bot", False),
                actor_id=player_data.get("actor_id"),
                platform_id=player_data.get("platform_id"),
                epic_id=player_data.get("epic_id"),
                steam_id=player_data.get("steam_id"),
                psn_id=player_data.get("psn_id"),
                xbox_id=player_data.get("xbox_id"),
                stats=player_stats
            )
        
        print(f"[DEBUG] Joueurs extraits: {list(processed.players.keys())}")
    else:
        # Si aucun joueur n'a été trouvé, essayons d'extraire des PlayerStats du header
        if "header_size" in raw_data and "properties" in raw_data:
            props = raw_data.get("properties", {})
            player_stats = props.get("PlayerStats", [])
            
            if isinstance(player_stats, list):
                print(f"[DEBUG] Extraction de joueurs depuis PlayerStats: {len(player_stats)} entrées")
                for idx, player_stat in enumerate(player_stats):
                    if isinstance(player_stat, dict):
                        # Extraction des informations de base
                        player_name = player_stat.get("Name", f"Joueur {idx}")
                        player_team = player_stat.get("Team", 0)
                        
                        # Extraction des identifiants
                        platform = None
                        platform_id = None
                        epic_id = None
                        steam_id = None
                        psn_id = None
                        xbox_id = None
                        online_id = None
                        
                        # Récupérer l'ID de la plateforme
                        if isinstance(player_stat.get("Platform"), dict):
                            platform = player_stat.get("Platform", {}).get("value")
                        
                        # Extraire l'OnlineID (souvent pour PlayStation)
                        if "OnlineID" in player_stat and player_stat["OnlineID"] != "0":
                            online_id = str(player_stat["OnlineID"])
                            if platform == "OnlinePlatform_PS4":
                                psn_id = online_id
                        
                        # Tenter d'extraire l'EpicAccountId et autres IDs spécifiques
                        if "PlayerID" in player_stat and isinstance(player_stat["PlayerID"], dict):
                            player_id_fields = player_stat["PlayerID"].get("fields", {})
                            
                            # Epic Games ID
                            if "EpicAccountId" in player_id_fields and player_id_fields["EpicAccountId"]:
                                epic_id = player_id_fields["EpicAccountId"]
                            
                            # Autres IDs spécifiques à la plateforme
                            if "Uid" in player_id_fields and player_id_fields["Uid"] != "0":
                                uid = str(player_id_fields["Uid"])
                                if platform == "OnlinePlatform_Steam":
                                    steam_id = uid
                                elif platform == "OnlinePlatform_XboxOne":
                                    xbox_id = uid
                                else:
                                    platform_id = uid
                        
                        # Créer un dictionnaire temporaire pour normaliser l'ID
                        temp_player_data = {
                            "name": player_name,
                            "epic_id": epic_id,
                            "steam_id": steam_id,
                            "psn_id": psn_id,
                            "xbox_id": xbox_id,
                            "platform_id": platform_id,
                            "online_id": online_id
                        }
                        
                        # Générer un ID normalisé
                        normalized_id = normalize_player_id(temp_player_data)
                        
                        print(f"[DEBUG] ID joueur normalisé: {normalized_id}")
                        if epic_id: print(f"[DEBUG]   Epic ID: {epic_id}")
                        if steam_id: print(f"[DEBUG]   Steam ID: {steam_id}")
                        if psn_id: print(f"[DEBUG]   PSN ID: {psn_id}")
                        if xbox_id: print(f"[DEBUG]   Xbox ID: {xbox_id}")
                        if online_id: print(f"[DEBUG]   Online ID: {online_id}")
                        
                        # Statistiques
                        player_stats_details = PlayerStatsDetails(
                            score=player_stat.get("Score", 0),
                            goals=player_stat.get("Goals", 0),
                            assists=player_stat.get("Assists", 0),
                            saves=player_stat.get("Saves", 0),
                            shots=player_stat.get("Shots", 0)
                        )
                        
                        # Créer joueur
                        processed.players[normalized_id] = PlayerInfo(
                            id=normalized_id,
                            name=player_name,
                            team=player_team,
                            platform=platform,
                            is_bot=player_stat.get("bBot", False),
                            platform_id=platform_id,
                            epic_id=epic_id,
                            steam_id=steam_id,
                            psn_id=psn_id,
                            xbox_id=xbox_id,
                            stats=player_stats_details
                        )
                        
                        print(f"[DEBUG] Joueur extrait depuis PlayerStats: {player_name} (Équipe {player_team}, ID: {normalized_id})")
        
        print(f"[DEBUG] Total joueurs après extraction: {len(processed.players)}")
    
    # --- Calculer la durée du replay ---
    # Essayer d'extraire la durée du header d'abord
    if "NumFrames" in header_props and "RecordFPS" in header_props:
        num_frames = header_props["NumFrames"]
        fps = header_props["RecordFPS"]
        if isinstance(num_frames, (int, float)) and isinstance(fps, (int, float)) and fps > 0:
            processed.duration = num_frames / fps
            print(f"[DEBUG] Durée calculée: {processed.duration}s (Frames: {num_frames}, FPS: {fps})")
    
    # --- Extraire les frames ---
    # Extrayons d'abord la structure des frames pour voir ce qui est disponible
    print(f"[DEBUG] Extraction des frames depuis le contenu...")
    
    # Créer un map des acteurs pour les joueurs (si disponible)
    player_actor_map = {}
    if "players" in players_and_teams:
        for player_id, player_data in players_and_teams["players"].items():
            if "actor_id" in player_data:
                player_actor_map[player_id] = player_data["actor_id"]
    
    # Extraire les frames depuis la structure du contenu
    fps = 30.0  # Valeur par défaut
    if "header_size" in raw_data and "properties" in raw_data:
        props = raw_data.get("properties", {})
        fps = props.get("RecordFPS", fps)
    
    # Extraire les frames
    processed_frames, car_player_map = extract_frames_from_schema(raw_data, player_actor_map, fps, list(processed.players.keys()), processed.players)
    if processed_frames:
        processed.frames = processed_frames
        processed.car_player_map = car_player_map
        print(f"[DEBUG] Extracted {len(processed_frames)} frames")
        
        # Mettre à jour la durée si nous avons des frames et pas de durée explicite
        if processed_frames and processed.duration == 300.0:  # Si c'est encore la valeur par défaut
            processed.duration = processed_frames[-1].get("time", 300.0)
            print(f"[DEBUG] Durée mise à jour depuis les frames: {processed.duration}s")
    
    # --- Générer la timeline ---
    # Essayons d'extraire les buts et autres événements
    timeline_events = generate_timeline_events(
        {"duration": processed.duration, "teams": processed.teams, "players": processed.players}, 
        raw_data  # Passer les données brutes complètes au lieu de juste content
    )
    
    # S'assurer que les événements sont bien du type correct
    for event in timeline_events:
        if isinstance(event, dict) and event.get("type") == "goal":
            print(f"[DEBUG] Ajout de l'événement goal à {event.get('time')}s par {event.get('player')}")
            processed.timeline.append(TimelineEvent(
                type="goal",
                time=event.get("time", 0.0),
                player=event.get("player"),
                team=event.get("team")
            ))
        elif isinstance(event, dict) and event.get("type") == "goal_inferred":
            print(f"[DEBUG] Ajout de l'événement goal_inferred à {event.get('time')}s")
            processed.timeline.append(TimelineEvent(
                type="goal_inferred",
                time=event.get("time", 0.0),
                player=event.get("player"),
                team=event.get("team")
            ))
        else:
            # Ajouter tout autre type d'événement non null
            if isinstance(event, dict) and event.get("type") and event.get("type") != "unknown":
                processed.timeline.append(TimelineEvent(
                    type=event.get("type", "unknown"),
                    time=event.get("time", 0.0),
                    player=event.get("player"),
                    team=event.get("team")
                ))
    
    print(f"[INFO] rrrocket data processing finished. Teams: {len(processed.teams)}, Players: {len(processed.players)}, Frames: {len(processed.frames)}, Timeline events: {len(processed.timeline)}")
    return processed


def find_players_and_teams(data, depth=0, max_depth=10):
    """
    Fonction récursive qui explore la structure de données pour trouver les joueurs et les équipes.
    
    Args:
        data: Données à explorer
        depth: Profondeur actuelle de récursion
        max_depth: Profondeur maximale de récursion pour éviter une récursion infinie
    
    Returns:
        Dict avec deux clés: "players" et "teams" contenant les données trouvées
    """
    # Résultats pour stocker les données trouvées
    result = {"players": {}, "teams": {}}
    
    # Éviter une récursion excessive ou des données invalides
    if depth > max_depth or data is None:
        return result
    
    # Si nous avons un dictionnaire, explorer ses clés
    if isinstance(data, dict):
        # Vérifier si c'est un dictionnaire qui contient directement des données de joueur
        if "name" in data and "team" in data:
            player_id = data.get("id", f"player_{len(result['players'])}")
            result["players"][player_id] = data
        
        # Vérifier si c'est un dictionnaire qui contient directement des données d'équipe
        elif "score" in data and ("id" in data or "team_num" in data):
            team_id = data.get("id", data.get("team_num", f"team_{len(result['teams'])}"))
            result["teams"][team_id] = data
        
        # Explorer récursivement toutes les clés
        for key, value in data.items():
            # Si la clé indique des joueurs ou des équipes, explorer plus profondément
            if key in ["players", "teams", "PlayerStats", "Teams"]:
                # Vérifier que la valeur est valide pour la récursion
                if isinstance(value, (dict, list)):
                    try:
                        sub_results = find_players_and_teams(value, depth + 1, max_depth)
                        # Fusionner les résultats
                        result["players"].update(sub_results["players"])
                        result["teams"].update(sub_results["teams"])
                    except Exception as e:
                        print(f"[WARNING] Erreur lors de l'exploration de {key}: {e}")
            elif isinstance(value, (dict, list)):
                # Explorer récursivement
                try:
                    sub_results = find_players_and_teams(value, depth + 1, max_depth)
                    # Fusionner les résultats
                    result["players"].update(sub_results["players"])
                    result["teams"].update(sub_results["teams"])
                except Exception as e:
                    print(f"[WARNING] Erreur lors de l'exploration récursive: {e}")
    
    # Si nous avons une liste, explorer chaque élément
    elif isinstance(data, list):
        # Vérifier si c'est une liste qui contient directement des données de joueur ou d'équipe
        for i, item in enumerate(data):
            if isinstance(item, dict):
                # Si c'est un joueur
                if "name" in item and "team" in item:
                    player_id = item.get("id", f"player_{len(result['players'])}")
                    result["players"][player_id] = item
                
                # Si c'est une équipe
                elif "score" in item and ("id" in item or "team_num" in item):
                    team_id = item.get("id", item.get("team_num", f"team_{len(result['teams'])}"))
                    result["teams"][team_id] = item
            
            # Explorer récursivement chaque élément valide
            if isinstance(item, (dict, list)):
                try:
                    sub_results = find_players_and_teams(item, depth + 1, max_depth)
                    # Fusionner les résultats
                    result["players"].update(sub_results["players"])
                    result["teams"].update(sub_results["teams"])
                except Exception as e:
                    print(f"[WARNING] Erreur lors de l'exploration de l'élément {i}: {e}")
    
    return result


def normalize_player_id(player_data: Dict[str, Any]) -> str:
    """
    Génère un identifiant unique et normalisé pour un joueur à partir des informations disponibles.
    Priorité: EpicID > SteamID > PSNID > XboxID > OnlineID > Name
    """
    # Liste de priorité pour les différents types d'ID
    epic_id = player_data.get("epic_id")
    steam_id = player_data.get("steam_id")
    psn_id = player_data.get("psn_id")
    xbox_id = player_data.get("xbox_id")
    platform_id = player_data.get("platform_id")
    online_id = player_data.get("online_id")
    player_name = player_data.get("name", "Unknown")
    
    # Retourner le premier ID valide selon la priorité
    if epic_id and epic_id != "":
        return f"epic_{epic_id}"
    elif steam_id and steam_id != "0":
        return f"steam_{steam_id}"
    elif psn_id and psn_id != "0":
        return f"psn_{psn_id}"
    elif xbox_id and xbox_id != "0":
        return f"xbox_{xbox_id}"
    elif platform_id and platform_id not in ["0", "", None]:
        return f"platform_{platform_id}"
    elif online_id and online_id not in ["0", "", None]:
        return f"online_{online_id}"
    else:
        return f"name_{player_name}"


def get_player_team(player_id: str, players_data: Dict[str, Any]) -> Optional[int]:
    """Obtient l'équipe d'un joueur à partir de son ID."""
    if player_id in players_data:
        if isinstance(players_data[player_id], dict):
            return players_data[player_id].get("team")
        else:
            # Si c'est un objet Pydantic
            return getattr(players_data[player_id], "team", None)
    return None


# --- FastAPI Endpoints ---

@app.get("/")
async def root():
    # Redirect to React interface
    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="fr">
      <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Rocket League Replay Analyzer</title>
        <meta http-equiv="refresh" content="0;url=/static/viewer/index.html">
      </head>
      <body>
        <p>Redirection vers l'interface d'analyse...</p>
      </body>
    </html>
    """)

@app.post("/replays")
async def upload_replay(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith('.replay'):
        raise HTTPException(status_code=400, detail="Seuls les fichiers .replay sont acceptés")

    replay_id = str(uuid.uuid4())
    file_path = f"uploads/{replay_id}.replay"
    metadata_path = f"data/{replay_id}_meta.json"  # Path to metadata

    try:
        # Save file
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)

        # Analyze metadata part only (quick)
        success, metadata, message = await analyze_replay_metadata(replay_id, file_path)

        if not success:
            # Attempt to cleanup uploaded file if analysis fails
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except OSError as del_err: print(f"[ERROR] Failed to cleanup {file_path}: {del_err}")
            raise HTTPException(status_code=500, detail=f"Erreur d'analyse: {message}")

        # Start frames extraction in background
        background_tasks[replay_id] = {"status": "processing", "progress": 0}
        asyncio.create_task(process_frames_background(replay_id, file_path))

        # Renvoyer les métadonnées complètes et la basic info
        response_data = {
            "id": replay_id,
            "filename": file.filename,
            "duration": metadata.get("duration", 300.0) if metadata else 300.0,
            "metadata": metadata  # Inclure toutes les métadonnées
        }

        return response_data

    except HTTPException as http_exc:
        # Re-raise known HTTP exceptions
        raise http_exc
    except Exception as e:
        # Catch-all for unexpected errors during upload/analysis call
        print(f"[ERROR] Unexpected error in upload_replay for {replay_id}: {e}")
        traceback.print_exc()
        # Attempt cleanup
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except OSError as del_err: print(f"[ERROR] Failed cleanup {file_path}: {del_err}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur inattendue: {str(e)}")

@app.get("/replays/{replay_id}/status")
async def get_processing_status(replay_id: str):
    """
    Renvoie l'état actuel du traitement des frames pour un replay spécifique.
    """
    # Vérifier si le traitement est en cours
    if replay_id in background_tasks:
        return background_tasks[replay_id]
    
    # Vérifier si le fichier de frames existe (traitement terminé)
    frames_bin_path = f"data/{replay_id}_frames.bin"
    if os.path.exists(frames_bin_path):
        return {"status": "completed", "progress": 100}
    
    # Vérifier si au moins les métadonnées existent
    metadata_path = f"data/{replay_id}_meta.json"
    if os.path.exists(metadata_path):
        return {"status": "metadata_only", "progress": 50, "message": "Métadonnées disponibles, frames en attente de traitement"}
    
    # Aucune donnée trouvée pour ce replay
    raise HTTPException(status_code=404, detail="Aucun traitement trouvé pour ce replay")

async def process_frames_background(replay_id: str, file_path: str):
    """
    Traite les frames d'un replay en arrière-plan et génère le fichier binaire.
    """
    try:
        # Mettre à jour l'état
        background_tasks[replay_id] = {"status": "processing", "progress": 10, "message": "Extraction des frames..."}
        
        # Lancer l'extraction des frames
        success, message = await analyze_replay_frames(replay_id, file_path)
        
        if success:
            background_tasks[replay_id] = {"status": "completed", "progress": 100}
        else:
            background_tasks[replay_id] = {"status": "failed", "error": message, "progress": 0}
        
        # Nettoyer le dictionnaire après un certain temps pour éviter qu'il grossisse indéfiniment
        asyncio.create_task(cleanup_task_status(replay_id))
    
    except Exception as e:
        print(f"[ERROR] Background processing failed for {replay_id}: {e}")
        traceback.print_exc()
        background_tasks[replay_id] = {"status": "failed", "error": str(e), "progress": 0}
        asyncio.create_task(cleanup_task_status(replay_id))

async def cleanup_task_status(replay_id: str, delay: int = 3600):
    """
    Nettoie les entrées du dictionnaire de tâches après un certain délai.
    """
    try:
        await asyncio.sleep(delay)  # Attendre 1 heure par défaut
        if replay_id in background_tasks:
            del background_tasks[replay_id]
            print(f"[INFO] Cleaned up task status for {replay_id}")
    except Exception as e:
        print(f"[WARNING] Failed to clean up task status for {replay_id}: {e}")

async def analyze_replay_metadata(replay_id: str, file_path: str) -> Tuple[bool, Dict[str, Any], str]:
    """
    Analyse un fichier replay pour extraire uniquement les métadonnées (rapide).
    Retourne un tuple (success, metadata, message).
    """
    output_dir = "data"
    output_json = f"{output_dir}/{replay_id}_rrrocket.json"
    metadata_path = f"{output_dir}/{replay_id}_meta.json"
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Check if we already have the metadata
    if os.path.exists(metadata_path):
        print(f"[INFO] Metadata already exists for {replay_id}")
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            return True, metadata, "Metadata already exists"
        except Exception as e:
            print(f"[WARNING] Failed to read existing metadata for {replay_id}: {e}")
            # Continue with analysis
    
    try:
        # Exécuter rrrocket pour obtenir les métadonnées de base (plus rapide sans les frames)
        print(f"[INFO] Extracting metadata for {replay_id}")
        process = await asyncio.create_subprocess_exec(
            'rrrocket', file_path, 
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_msg = stderr.decode().strip() if stderr else "Unknown error"
            print(f"[ERROR] rrrocket failed for {replay_id}: {error_msg}")
            return False, None, f"rrrocket error: {error_msg}"
        
        # Parse les données JSON
        raw_json = stdout.decode('utf-8')
        try:
            raw_data = json.loads(raw_json)
            print(f"[INFO] Successfully parsed JSON for {replay_id}")
        except json.JSONDecodeError as json_err:
            print(f"[ERROR] Failed to parse rrrocket JSON for {replay_id}: {json_err}")
            return False, None, f"JSON parse error: {str(json_err)}"
        
        # Sauvegarder temporairement le JSON pour traitement ultérieur des frames
        with open(output_json, 'w', encoding='utf-8') as f:
            f.write(raw_json)
        
        # Extraire uniquement les métadonnées (sans traiter les frames)
        processed_data = process_replay_metadata(replay_id, raw_data)
        
        # Créer le JSON de métadonnées
        metadata_json = {
            "id": replay_id,
            "teams": {},
            "players": {},
            "timeline": [],
            "duration": processed_data.duration,
            "date": processed_data.date,
            "map_name": processed_data.map_name or "Unknown Map",
            "match_type": processed_data.match_type or "",
            "game_type": processed_data.game_type or "Unknown Game Type",
            "car_player_map": {}
        }
        
        # Convertir Teams (objets Pydantic -> dictionnaires)
        for team_id, team in processed_data.teams.items():
            if hasattr(team, "model_dump"):  # Pydantic v2
                metadata_json["teams"][team_id] = team.model_dump()
            elif hasattr(team, "dict"):  # Pydantic v1
                metadata_json["teams"][team_id] = team.dict()
            else:  # Fallback
                metadata_json["teams"][team_id] = {
                    "id": team.id if hasattr(team, "id") else team_id,
                    "name": team.name if hasattr(team, "name") else f"Team {team_id}",
                    "score": team.score if hasattr(team, "score") else 0
                }
        
        # Convertir Players (objets Pydantic -> dictionnaires)
        for player_id, player in processed_data.players.items():
            if hasattr(player, "model_dump"):  # Pydantic v2
                metadata_json["players"][player_id] = player.model_dump()
            elif hasattr(player, "dict"):  # Pydantic v1
                metadata_json["players"][player_id] = player.dict()
            else:  # Fallback
                player_dict = {
                    "id": player_id,
                    "name": player.name if hasattr(player, "name") else f"Player {player_id}",
                    "team": player.team if hasattr(player, "team") else 0,
                    "is_bot": player.is_bot if hasattr(player, "is_bot") else False,
                    "stats": {}
                }
                # Ajouter les stats si disponibles
                if hasattr(player, "stats"):
                    stats = player.stats
                    player_dict["stats"] = {
                        "score": stats.score if hasattr(stats, "score") else 0,
                        "goals": stats.goals if hasattr(stats, "goals") else 0,
                        "assists": stats.assists if hasattr(stats, "assists") else 0,
                        "saves": stats.saves if hasattr(stats, "saves") else 0,
                        "shots": stats.shots if hasattr(stats, "shots") else 0
                    }
                metadata_json["players"][player_id] = player_dict
        
        # Convertir Timeline (liste d'objets Pydantic -> liste de dictionnaires)
        for event in processed_data.timeline:
            if hasattr(event, "model_dump"):  # Pydantic v2
                metadata_json["timeline"].append(event.model_dump())
            elif hasattr(event, "dict"):  # Pydantic v1
                metadata_json["timeline"].append(event.dict())
            else:  # Fallback
                metadata_json["timeline"].append({
                    "type": event.type if hasattr(event, "type") else "unknown",
                    "time": event.time if hasattr(event, "time") else 0,
                    "player": event.player if hasattr(event, "player") else None,
                    "team": event.team if hasattr(event, "team") else None
                })
        
        # Sauvegarder les métadonnées
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata_json, f, indent=2)
            print(f"[INFO] Metadata written to {metadata_path}")
        
        return True, metadata_json, "Success"
    
    except Exception as e:
        print(f"[ERROR] Metadata extraction failed for {replay_id}: {e}")
        traceback.print_exc()
        return False, None, f"Metadata extraction error: {str(e)}"

async def analyze_replay_frames(replay_id: str, replay_path: str) -> Tuple[bool, str]:
    """Analyse les frames d'un replay et les stocke au format binaire."""
    # Vérifier si le fichier binaire existe déjà
    frames_binary_path = os.path.join("data", f"{replay_id}_frames.bin")
    if os.path.exists(frames_binary_path):
        print(f"[INFO] Le fichier de frames binaire existe déjà pour {replay_id}")
        return True, f"Frames déjà extraites pour le replay {replay_id}"
    
    # Vérifier si le fichier de métadonnées existe
    meta_path = os.path.join("data", f"{replay_id}_meta.json")
    if not os.path.exists(meta_path):
        print(f"[ERROR] Le fichier de métadonnées n'existe pas pour {replay_id}")
        return False, f"Fichier de métadonnées introuvable pour {replay_id}"
    
    try:
        # Charger les métadonnées
        with open(meta_path, "r") as f:
            metadata = json.load(f)
        
        # Limiter le nombre de frames à extraire
        # Si le replay est long, on risque un timeout
        max_frames = int(os.environ.get("MAX_FRAMES", 12000))
        
        # Obtenir le chemin de sortie pour rrrocket
        output_json = os.path.join("data", f"{replay_id}_output.json")
        
        # Exécuter rrrocket pour obtenir les données détaillées
        print(f"[INFO] Exécution de rrrocket pour l'extraction des frames de {replay_id}")
        command = ["rrrocket", "parse", replay_path, "-o", output_json]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            error_message = stderr.decode() if stderr else "Erreur inconnue"
            print(f"[ERROR] Erreur lors de l'exécution de rrrocket: {error_message}")
            return False, f"Erreur d'extraction avec rrrocket: {error_message}"
        
        # Vérifier si le fichier de sortie existe
        if not os.path.exists(output_json):
            print(f"[ERROR] Le fichier de sortie {output_json} n'a pas été créé")
            return False, "Le fichier de sortie de rrrocket n'a pas été créé"
        
        # Charger le fichier JSON généré par rrrocket
        print(f"[INFO] Chargement du fichier JSON généré par rrrocket: {output_json}")
        with open(output_json, "r") as f:
            content_data = json.load(f)
        
        # Extraire les informations nécessaires des métadonnées
        player_actor_map = metadata.get("player_actor_map", {})
        player_ids = list(metadata.get("players", {}).keys())
        players_data = metadata.get("players", {})
        fps = metadata.get("fps", 30.0)
        
        print(f"[INFO] Extraction de frames avec {len(player_ids)} joueurs, FPS={fps}")
        
        # Extraire les frames
        try:
            frames, car_player_map = extract_frames_from_schema(content_data, player_actor_map, fps, player_ids, players_data)
            print(f"[INFO] {len(frames)} frames extraites avec succès")
            
            # Limiter le nombre de frames si nécessaire
            if len(frames) > max_frames:
                print(f"[WARNING] Limitation à {max_frames} frames sur {len(frames)} extraites")
                # Prendre des frames régulièrement espacées pour garder la durée totale
                step = len(frames) / max_frames
                limited_frames = []
                for i in range(max_frames):
                    idx = min(int(i * step), len(frames) - 1)
                    limited_frames.append(frames[idx])
                frames = limited_frames
            
            # Écrire les frames au format binaire
            writer = BinaryFramesWriter()
            writer.write_frames_to_binary(frames, frames_binary_path)
            print(f"[INFO] {len(frames)} frames écrites dans {frames_binary_path}")
            
            # Supprimer le fichier JSON temporaire pour économiser de l'espace
            if os.path.exists(output_json):
                os.remove(output_json)
                print(f"[INFO] Fichier temporaire supprimé: {output_json}")
            
            return True, f"{len(frames)} frames extraites et enregistrées avec succès"
            
        except Exception as extraction_error:
            print(f"[ERROR] Erreur lors de l'extraction des frames: {extraction_error}")
            traceback.print_exc()
            return False, f"Erreur lors de l'extraction des frames: {str(extraction_error)}"
            
    except Exception as e:
        print(f"[ERROR] Exception dans analyze_replay_frames: {e}")
        traceback.print_exc()
        return False, f"Erreur lors de l'analyse des frames: {str(e)}"

async def analyze_replay(replay_id: str, file_path: str) -> Tuple[bool, str]:
    """Analyze a replay file using rrrocket and process the results.
    Returns a tuple of (success, message)"""
    
    # Cette fonction est gardée pour compatibilité, mais divisée en deux parties
    # pour l'extraction des métadonnées (rapide) et des frames (lente)
    try:
        # D'abord extraire les métadonnées
        success_meta, metadata, message_meta = await analyze_replay_metadata(replay_id, file_path)
        if not success_meta:
            return False, message_meta
        
        # Ensuite extraire les frames
        success_frames, message_frames = await analyze_replay_frames(replay_id, file_path)
        if not success_frames:
            return True, f"Metadata extracted successfully, but frames failed: {message_frames}"
        
        return True, "Success"
    except Exception as e:
        print(f"[ERROR] Analysis error for {replay_id}: {e}")
        traceback.print_exc()
        return False, f"Analysis error: {str(e)}"

# Fonction qui était manquante
def get_complete_metadata(base_metadata, players_data, teams_data, player_ids, raw_data):
    """
    Complète les métadonnées avec des informations supplémentaires.
    Cette fonction était référencée mais manquante dans le code.
    """
    # Création d'un dictionnaire de métadonnées complet
    complete_metadata = {
        "map": base_metadata.get("map", "Unknown Map"),
        "game_type": base_metadata.get("game_type", "Unknown Game Type"),
        "duration": base_metadata.get("duration", 300.0),
        "date": "",
        "match_guid": "",
        "match_name": "",
        "match_type": ""
    }
    
    # Essayer d'extraire des informations supplémentaires depuis les données brutes
    if isinstance(raw_data, dict):
        # Extraction de la date
        if "properties" in raw_data:
            props = raw_data.get("properties", {})
            complete_metadata["date"] = props.get("Date", "")
            complete_metadata["match_type"] = props.get("MatchType", "")
            complete_metadata["match_guid"] = props.get("Id", "")
            complete_metadata["match_name"] = props.get("ReplayName", "")
    
    return complete_metadata

def extract_player_actor_relations(raw_data: Dict[str, Any], players: Dict[str, Any]) -> Dict[str, int]:
    """
    Extrait les relations entre acteurs et joueurs à partir des données brutes.
    
    Args:
        raw_data: Données JSON brutes de rrrocket
        players: Dictionnaire des données de joueurs
        
    Returns:
        Dictionnaire de correspondance {player_id: actor_id}
    """
    player_actor_map = {}
    
    # Vérifier que players est bien un dictionnaire
    if not isinstance(players, dict):
        print(f"[WARNING] players n'est pas un dictionnaire mais un {type(players)}. Création d'un dictionnaire vide.")
        return player_actor_map
    
    # Fonction utilitaire pour valider et ajouter un actor_id au mapping
    def add_to_map(player_id: str, actor_id: Any):
        # Vérifier que l'actor_id est un entier valide
        try:
            if actor_id is not None:
                actor_id_int = int(actor_id)
                player_actor_map[player_id] = actor_id_int
                return True
        except (ValueError, TypeError):
            print(f"[WARNING] Valeur non entière pour actor_id: {actor_id} (joueur {player_id})")
        return False
    
    try:
        # 1. Extraire les correspondances depuis les PlayerStats
        if "properties" in raw_data:
            props = raw_data.get("properties", {})
            player_stats = props.get("PlayerStats", [])
            
            if isinstance(player_stats, list):
                print(f"[DEBUG] Extraction des acteurs depuis PlayerStats: {len(player_stats)} entrées")
                
                # Mapper les noms aux IDs des joueurs
                name_to_player_id = {}
                for player_id, player_data in players.items():
                    if isinstance(player_data, dict) and "name" in player_data:
                        name_to_player_id[player_data["name"]] = player_id
                
                for player_stat in player_stats:
                    if isinstance(player_stat, dict):
                        player_name = player_stat.get("Name")
                        actor_id = player_stat.get("PlayerID")
                        online_id = str(player_stat.get("OnlineID", "0"))
                        
                        # Chercher d'abord par OnlineID direct
                        if online_id != "0" and online_id in players:
                            if add_to_map(online_id, actor_id):
                                print(f"[DEBUG] Association directe par OnlineID: {online_id} -> {actor_id}")
                        
                        # Ensuite par nom
                        elif player_name and player_name in name_to_player_id:
                            player_id = name_to_player_id[player_name]
                            if add_to_map(player_id, actor_id):
                                print(f"[DEBUG] Association par nom: {player_name} ({player_id}) -> {actor_id}")
        
        # 2. Extraire depuis les objets PRI (PlayerReplicationInfo)
        if "objects" in raw_data:
            objects = raw_data.get("objects", [])
            if isinstance(objects, list):
                for obj in objects:
                    if isinstance(obj, dict) and "class_name" in obj:
                        class_name = obj.get("class_name", "")
                        
                        # Chercher les objets de type PlayerReplicationInfo
                        if "PlayerReplicationInfo" in class_name or "PRI" in class_name:
                            actor_id = obj.get("actor_id")
                            properties = obj.get("properties", {})
                            
                            player_name = properties.get("PlayerName")
                            unique_id = properties.get("UniqueId")
                            
                            # Chercher le joueur par son nom
                            if player_name:
                                for player_id, player_data in players.items():
                                    if isinstance(player_data, dict) and player_data.get("name") == player_name:
                                        if add_to_map(player_id, actor_id):
                                            print(f"[DEBUG] Association depuis PRI: {player_name} ({player_id}) -> {actor_id}")
                                        break
        
        # 3. Extraire depuis les acteurs
        if "actors" in raw_data:
            actors = raw_data.get("actors", [])
            if isinstance(actors, list):
                for actor in actors:
                    if isinstance(actor, dict):
                        actor_id = actor.get("actor_id")
                        actor_type = actor.get("actor_type", "")
                        object_name = actor.get("object_name", "")
                        
                        # Chercher les acteurs liés aux voitures/joueurs
                        if "car" in object_name.lower() or "vehicle" in object_name.lower():
                            properties = actor.get("properties", {})
                            
                            # Chercher une propriété qui contiendrait le nom du joueur ou un ID
                            for prop_name, prop_value in properties.items():
                                if prop_name.lower() in ["playername", "player_name", "name"]:
                                    player_name = prop_value
                                    
                                    # Chercher le joueur par son nom
                                    for player_id, player_data in players.items():
                                        if isinstance(player_data, dict) and player_data.get("name") == player_name:
                                            if add_to_map(player_id, actor_id):
                                                print(f"[DEBUG] Association depuis acteur: {player_name} ({player_id}) -> {actor_id}")
                                            break
        
        # 4. Si le dictionnaire est vide, essayer une approche plus directe
        if not player_actor_map:
            print("[WARNING] Aucune association acteur-joueur trouvée, tentative d'extraction directe")
            
            # Parcourir la structure complète à la recherche d'objets contenant des noms de joueurs
            def scan_for_player_relations(data, depth=0, max_depth=5):
                if depth > max_depth or not isinstance(data, (dict, list)):
                    return
                
                if isinstance(data, dict):
                    # Chercher des indices d'associations joueur-acteur
                    if "actor_id" in data and ("name" in data or "player_name" in data or "PlayerName" in data):
                        actor_id = data.get("actor_id")
                        player_name = data.get("name") or data.get("player_name") or data.get("PlayerName")
                        
                        if player_name:
                            for player_id, player_data in players.items():
                                if isinstance(player_data, dict) and player_data.get("name") == player_name:
                                    if add_to_map(player_id, actor_id):
                                        print(f"[DEBUG] Association par scan: {player_name} ({player_id}) -> {actor_id}")
                                    break
                    
                    # Explorer récursivement
                    for key, value in data.items():
                        scan_for_player_relations(value, depth + 1, max_depth)
                
                elif isinstance(data, list):
                    for item in data:
                        scan_for_player_relations(item, depth + 1, max_depth)
            
            # Lancer le scan sur les données brutes complètes
            scan_for_player_relations(raw_data)
        
        # Si on a toujours rien trouvé, créer des associations aléatoires
        if not player_actor_map and players:
            print("[WARNING] Création d'associations arbitraires acteur-joueur")
            start_actor_id = 100  # ID arbitraire de départ
            
            for i, player_id in enumerate(players.keys()):
                actor_id = start_actor_id + i
                player_actor_map[player_id] = actor_id
                print(f"[DEBUG] Association arbitraire: {player_id} -> {actor_id}")
    
    except Exception as e:
        print(f"[ERROR] Exception dans extract_player_actor_relations: {e}")
        traceback.print_exc()
    
    return player_actor_map


@app.get("/replays/{replay_id}")
async def get_replay_metadata(replay_id: str):
    """
    Récupère les métadonnées d'un replay (joueurs, équipes, etc.) sans les frames.
    """
    metadata_path = f"data/{replay_id}_meta.json"

    if not os.path.exists(metadata_path):
        print(f"[ERROR] Metadata file not found for {replay_id} at: {metadata_path}")
        raise HTTPException(status_code=404, detail=f"Métadonnées pour le replay {replay_id} non trouvées.")

    try:
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # S'assurer que chaque joueur a un ID correspondant à sa clé
        if "players" in metadata and isinstance(metadata["players"], dict):
            for player_id, player_data in list(metadata["players"].items()):
                if isinstance(player_data, dict) and "id" not in player_data:
                    player_data["id"] = player_id
        
        # Supprimer explicitement les champs frames et car_player_map s'ils existent pour alléger la réponse
        if "frames" in metadata:
            del metadata["frames"]
        
        if "car_player_map" in metadata:
            del metadata["car_player_map"]
            
        # Filtrer les événements de timeline vides ou non valides
        if "timeline" in metadata and isinstance(metadata["timeline"], list):
            filtered_timeline = [
                event for event in metadata["timeline"] 
                if isinstance(event, dict) and (event.get("type") != "unknown")
            ]
            
            # Si la timeline filtrée est vide, créer un événement de début de match
            if not filtered_timeline:
                duration = metadata.get("duration", 300.0)
                if duration > 0:
                    # Ajouter un événement de début de match
                    filtered_timeline.append({
                        "type": "match_start",
                        "time": 0.0,
                        "player": None,
                        "team": None
                    })
                    
                    # Si le match a une durée, ajouter aussi un événement de fin
                    filtered_timeline.append({
                        "type": "match_end",
                        "time": duration,
                        "player": None,
                        "team": None
                    })
            
            metadata["timeline"] = filtered_timeline
            
    except json.JSONDecodeError as json_err:
        print(f"[ERROR] JSON decode error for {metadata_path}: {json_err}")
        raise HTTPException(status_code=500, detail=f"Erreur lecture métadonnées replay {replay_id}: JSON invalide.")
    except Exception as read_err:
        print(f"[ERROR] Read error for {metadata_path}: {read_err}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur lecture métadonnées replay {replay_id}.")

    # Validate and return data using Pydantic model
    try:
        # Créer l'objet Pydantic
        response_data = ReplayDataProcessed(**metadata)
        
        # Convertir en dictionnaire 
        response_dict = response_data.dict()
        
        # Supprimer complètement les clés non désirées
        if "frames" in response_dict:
            del response_dict["frames"]
        
        if "car_player_map" in response_dict:
            del response_dict["car_player_map"]
        
        # Retourner le dictionnaire modifié
        return response_dict
    except Exception as val_err:
        print(f"[ERROR] Data validation error for {replay_id}: {val_err}")
        raise HTTPException(status_code=500, detail=f"Erreur de validation des métadonnées pour {replay_id}")


@app.get("/replays/{replay_id}/frames")
async def get_replay_frames_binary(replay_id: str):
    """
    Récupère les données de frames au format binaire.
    """
    metadata_path = f"data/{replay_id}_meta.json"
    frames_bin_path = f"data/{replay_id}_frames.bin"
    
    # Vérifier si les métadonnées existent
    if not os.path.exists(metadata_path):
        print(f"[ERROR] Metadata file not found for {replay_id} at: {metadata_path}")
        raise HTTPException(status_code=404, detail=f"Métadonnées pour le replay {replay_id} non trouvées.")
    
    # Vérifier si le fichier de frames existe
    if not os.path.exists(frames_bin_path):
        # Vérifier l'état du traitement en arrière-plan
        if replay_id in background_tasks:
            status = background_tasks[replay_id]
            raise HTTPException(
                status_code=202, 
                detail=f"Traitement des frames en cours: {status.get('progress', 0)}% - {status.get('message', 'En traitement...')}"
            )
        
        # Si le traitement n'est pas en cours, lancer l'extraction en arrière-plan
        print(f"[WARNING] Frames file not found for {replay_id}, starting background processing")
        file_path = f"uploads/{replay_id}.replay"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Fichier replay {replay_id} non trouvé. Veuillez le téléverser à nouveau.")
        
        # Lancer l'extraction en arrière-plan
        background_tasks[replay_id] = {"status": "processing", "progress": 0}
        asyncio.create_task(process_frames_background(replay_id, file_path))
        
        raise HTTPException(
            status_code=202, 
            detail=f"Traitement des frames démarré. Utilisez /replays/{replay_id}/status pour vérifier l'avancement."
        )
    
    try:
        return FileResponse(
            frames_bin_path, 
            media_type="application/octet-stream",
            filename=f"{replay_id}_frames.bin"
        )
    except Exception as e:
        print(f"[ERROR] Error sending frames binary file for {replay_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'envoi des frames binaires: {str(e)}")

@app.get("/replays/{replay_id}/frames.json")
async def get_replay_frames_json(replay_id: str):
    """
    Récupère les données de frames au format JSON (plus lent que la version binaire).
    """
    metadata_path = f"data/{replay_id}_meta.json"
    frames_bin_path = f"data/{replay_id}_frames.bin"
    
    # Vérifier si les métadonnées existent
    if not os.path.exists(metadata_path):
        print(f"[ERROR] Metadata file not found for {replay_id} at: {metadata_path}")
        raise HTTPException(status_code=404, detail=f"Métadonnées pour le replay {replay_id} non trouvées.")
    
    # Vérifier si le fichier de frames existe
    if not os.path.exists(frames_bin_path):
        # Vérifier l'état du traitement en arrière-plan
        if replay_id in background_tasks:
            status = background_tasks[replay_id]
            raise HTTPException(
                status_code=202, 
                detail=f"Traitement des frames en cours: {status.get('progress', 0)}% - {status.get('message', 'En traitement...')}"
            )
        
        # Si le traitement n'est pas en cours, lancer l'extraction en arrière-plan
        print(f"[WARNING] Frames file not found for {replay_id}, starting background processing")
        file_path = f"uploads/{replay_id}.replay"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Fichier replay {replay_id} non trouvé. Veuillez le téléverser à nouveau.")
        
        # Lancer l'extraction en arrière-plan
        background_tasks[replay_id] = {"status": "processing", "progress": 0}
        asyncio.create_task(process_frames_background(replay_id, file_path))
        
        raise HTTPException(
            status_code=202, 
            detail=f"Traitement des frames démarré. Utilisez /replays/{replay_id}/status pour vérifier l'avancement."
        )
    
    try:
        # Charger les métadonnées pour avoir les informations sur les joueurs et le car_player_map
        with open(metadata_path, 'r', encoding='utf-8') as f:
            metadata = json.load(f)
        
        # Lire les frames depuis le fichier binaire
        frames = await BinaryFramesReader.read_frames_from_binary(frames_bin_path)
        
        # Vérifier si les frames contiennent des voitures et les ajouter si nécessaire
        players_data = metadata.get("players", {})
        car_player_map = metadata.get("car_player_map", {})
        
        if not any(frame.get("cars") for frame in frames) and players_data:
            print(f"[WARNING] Les frames ne contiennent pas de voitures, ajout de voitures synthétiques")
            
            for frame in frames:
                cars = {}
                
                # Pour chaque joueur, créer une voiture si elle n'existe pas
                for player_id, player_data in players_data.items():
                    team = player_data.get("team", 0) if isinstance(player_data, dict) else 0
                    
                    # Générer une position basée sur l'équipe
                    x_pos = 0
                    y_pos = 3000 if team == 0 else -3000
                    
                    # Faire bouger légèrement la voiture en fonction du temps
                    time = frame.get("time", 0)
                    x_pos += 500 * math.sin(time * 0.3 + (0.5 if team == 0 else 0))
                    
                    # État de la voiture
                    cars[player_id] = {
                        "position": [x_pos, y_pos, 17],
                        "rotation": [0, 0, math.sin(time * 0.1), math.cos(time * 0.1)],
                        "boost": 33
                    }
                
                # Mettre à jour les voitures dans la frame
                frame["cars"] = cars
        
        # Retourner en JSON sans échantillonnage
        print(f"[INFO] Retournant les {len(frames)} frames complètes")
        return frames
    except Exception as e:
        print(f"[ERROR] Error reading frames for {replay_id}: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la lecture des frames: {str(e)}")

# --- Main execution block ---
if __name__ == "__main__":
    import uvicorn
    print("[INFO] Starting Rocket League Replay Analyzer server...")
    uvicorn.run(app, host="0.0.0.0", port=8000) 