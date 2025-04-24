from typing import Any, Dict, Optional, List, Tuple
import math
import uuid
import os
import json
import struct
import asyncio
import subprocess


def get_prop_value(prop_dict: Dict) -> Any:
    """Extrait la valeur réelle d'une structure de propriété de Rattletrap."""
    if not isinstance(prop_dict, dict) or 'value' not in prop_dict:
        return None
    val_container = prop_dict['value']
    # La valeur réelle est souvent imbriquée (ex: {"int": 5}, {"array": [...]})
    if isinstance(val_container, dict) and len(val_container) == 1:
        return list(val_container.values())[0]
    return val_container


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


def generate_replay_id() -> str:
    """Génère un ID unique pour un replay."""
    return str(uuid.uuid4())


def create_directory_if_not_exists(directory_path: str) -> None:
    """Crée un répertoire s'il n'existe pas déjà."""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


# Dictionnaire global pour suivre l'état des tâches en arrière-plan
_background_tasks_status = {}


def set_background_task_status(task_id: str, status: Dict[str, Any]) -> None:
    """
    Définit l'état d'une tâche d'arrière-plan.
    
    Args:
        task_id: Identifiant de la tâche
        status: Dictionnaire contenant l'état de la tâche
    """
    _background_tasks_status[task_id] = status


def get_background_task_status(task_id: str) -> Optional[Dict[str, Any]]:
    """
    Récupère l'état d'une tâche d'arrière-plan.
    
    Args:
        task_id: Identifiant de la tâche
    
    Returns:
        Dictionnaire contenant l'état de la tâche ou None si la tâche n'existe pas
    """
    return _background_tasks_status.get(task_id)


async def run_command(cmd: List[str], output_file: Optional[str] = None) -> Tuple[int, str, str]:
    """
    Exécute une commande système de manière asynchrone.
    
    Args:
        cmd: Liste contenant la commande et ses arguments
        output_file: Chemin vers le fichier où rediriger la sortie standard
    
    Returns:
        Tuple contenant (code de retour, sortie standard, erreur standard)
    """
    if output_file is None:
        # Exécution normale avec capture de la sortie
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )
    else:
        # Pour rediriger la sortie vers un fichier, nous devons utiliser shell=True
        # avec une string plutôt qu'un tableau d'arguments
        cmd_str = " ".join(f'"{c}"' if ' ' in c else c for c in cmd)
        cmd_str += f" > \"{output_file}\""
        
        process = await asyncio.create_subprocess_shell(
            cmd_str,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=True
        )
        
        stdout, stderr = await process.communicate()
        return (
            process.returncode,
            stdout.decode('utf-8', errors='replace'),
            stderr.decode('utf-8', errors='replace')
        )


class BinaryFramesWriter:
    """Classe pour écrire des frames dans un format binaire."""
    
    @staticmethod
    def write_frames_to_binary(frames: List[Dict[str, Any]], output_file: str) -> None:
        """
        Écrit des frames dans un fichier binaire.
        
        Structure du fichier:
        - Header: "RLFRAMES" (8 bytes)
        - Version: 1 (2 bytes, unsigned short)
        - Nombre de frames: unsigned int (4 bytes)
        - Pour chaque frame:
            - Timestamp: float (8 bytes)
            - Position de la balle (x, y, z): 3 floats (12 bytes)
            - Vitesse de la balle (x, y, z): 3 floats (12 bytes)
            - Nombre de voitures: unsigned short (2 bytes)
            - Pour chaque voiture:
                - ID de la voiture: unsigned short (2 bytes)
                - ID du joueur: unsigned short (2 bytes)
                - Position (x, y, z): 3 floats (12 bytes)
                - Rotation (pitch, yaw, roll): 3 floats (12 bytes)
                - Vitesse (x, y, z): 3 floats (12 bytes)
                - Boost: unsigned char (1 byte)
        
        Args:
            frames: Liste des frames à écrire
            output_file: Chemin du fichier de sortie
        """
        with open(output_file, 'wb') as f:
            # Écriture du header
            f.write(b'RLFRAMES')
            
            # Écriture de la version
            f.write(struct.pack('<H', 1))
            
            # Écriture du nombre de frames
            f.write(struct.pack('<I', len(frames)))
            
            # Écriture des frames
            for frame in frames:
                # Timestamp
                f.write(struct.pack('<d', frame.get('time', 0.0)))
                
                # Balle
                ball = frame.get('ball', {})
                ball_pos = ball.get('position', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                ball_vel = ball.get('velocity', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                
                # S'assurer que nous avons des valeurs numériques pour les coordonnées
                pos_x = float(ball_pos.get('x', 0.0))
                pos_y = float(ball_pos.get('y', 0.0))
                pos_z = float(ball_pos.get('z', 0.0))
                
                vel_x = float(ball_vel.get('x', 0.0))
                vel_y = float(ball_vel.get('y', 0.0))
                vel_z = float(ball_vel.get('z', 0.0))
                
                f.write(struct.pack('<fff', pos_x, pos_y, pos_z))
                f.write(struct.pack('<fff', vel_x, vel_y, vel_z))
                
                # Voitures
                cars = frame.get('cars', [])
                # Vérifier si cars est une liste (nouveau format) ou un dictionnaire (ancien format)
                if isinstance(cars, list):
                    f.write(struct.pack('<H', len(cars)))
                    
                    for car_data in cars:
                        # Conversion de l'ID de la voiture en entier
                        car_id_str = car_data.get('id', '0')
                        car_id_int = int(car_id_str) if isinstance(car_id_str, (int, str)) and car_id_str and car_id_str.isdigit() else 0
                        
                        # ID du joueur
                        player_id = car_data.get('player_id', 0)
                        # Convertir uniquement si c'est un nombre ou une chaîne représentant un nombre
                        try:
                            player_id_int = int(player_id) if isinstance(player_id, (int, str)) and player_id else 0
                        except ValueError:
                            # Si la conversion échoue (par exemple avec "unknown"), utiliser 0
                            player_id_int = 0
                        
                        # Écriture des IDs
                        f.write(struct.pack('<HH', car_id_int, player_id_int))
                        
                        # Position
                        pos = car_data.get('position', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                        pos_x = float(pos.get('x', 0.0))
                        pos_y = float(pos.get('y', 0.0))
                        pos_z = float(pos.get('z', 0.0))
                        f.write(struct.pack('<fff', pos_x, pos_y, pos_z))
                        
                        # Rotation
                        rot = car_data.get('rotation', {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0})
                        pitch = float(rot.get('pitch', 0.0))
                        yaw = float(rot.get('yaw', 0.0))
                        roll = float(rot.get('roll', 0.0))
                        f.write(struct.pack('<fff', pitch, yaw, roll))
                        
                        # Vitesse
                        vel = car_data.get('velocity', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                        vel_x = float(vel.get('x', 0.0))
                        vel_y = float(vel.get('y', 0.0))
                        vel_z = float(vel.get('z', 0.0))
                        f.write(struct.pack('<fff', vel_x, vel_y, vel_z))
                        
                        # Boost
                        boost = car_data.get('boost', 0)
                        boost_int = int(boost) if isinstance(boost, (int, float)) else 0
                        boost_int = max(0, min(255, boost_int))  # Limiter à 0-255
                        f.write(struct.pack('<B', boost_int))
                else:
                    # Ancien format (dictionnaire)
                    f.write(struct.pack('<H', len(cars)))
                    
                    for car_id, car_data in cars.items():
                        # Conversion de l'ID de la voiture en entier
                        car_id_int = int(car_id) if isinstance(car_id, (int, str)) and car_id and str(car_id).isdigit() else 0
                        
                        # ID du joueur
                        player_id = car_data.get('player_id', 0)
                        # Convertir uniquement si c'est un nombre ou une chaîne représentant un nombre
                        try:
                            player_id_int = int(player_id) if isinstance(player_id, (int, str)) and player_id else 0
                        except ValueError:
                            # Si la conversion échoue (par exemple avec "unknown"), utiliser 0
                            player_id_int = 0
                        
                        # Écriture des IDs
                        f.write(struct.pack('<HH', car_id_int, player_id_int))
                        
                        # Position
                        pos = car_data.get('position', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                        pos_x = float(pos.get('x', 0.0))
                        pos_y = float(pos.get('y', 0.0))
                        pos_z = float(pos.get('z', 0.0))
                        f.write(struct.pack('<fff', pos_x, pos_y, pos_z))
                        
                        # Rotation
                        rot = car_data.get('rotation', {'pitch': 0.0, 'yaw': 0.0, 'roll': 0.0})
                        pitch = float(rot.get('pitch', 0.0))
                        yaw = float(rot.get('yaw', 0.0))
                        roll = float(rot.get('roll', 0.0))
                        f.write(struct.pack('<fff', pitch, yaw, roll))
                        
                        # Vitesse
                        vel = car_data.get('velocity', {'x': 0.0, 'y': 0.0, 'z': 0.0})
                        vel_x = float(vel.get('x', 0.0))
                        vel_y = float(vel.get('y', 0.0))
                        vel_z = float(vel.get('z', 0.0))
                        f.write(struct.pack('<fff', vel_x, vel_y, vel_z))
                        
                        # Boost
                        boost = car_data.get('boost', 0)
                        boost_int = int(boost) if isinstance(boost, (int, float)) else 0
                        boost_int = max(0, min(255, boost_int))  # Limiter à 0-255
                        f.write(struct.pack('<B', boost_int))


class BinaryFramesReader:
    """Classe pour lire des frames depuis un format binaire."""
    
    @staticmethod
    def read_frames_from_binary(input_file: str) -> List[Dict[str, Any]]:
        """
        Lit des frames depuis un fichier binaire.
        
        Structure du fichier: voir BinaryFramesWriter.write_frames_to_binary
        
        Args:
            input_file: Chemin du fichier d'entrée
        
        Returns:
            Liste des frames lues
        """
        frames = []
        
        with open(input_file, 'rb') as f:
            # Lecture du header
            header = f.read(8)
            if header != b'RLFRAMES':
                raise ValueError("Format de fichier non valide. Header attendu: 'RLFRAMES'")
            
            # Lecture de la version
            version = struct.unpack('<H', f.read(2))[0]
            if version != 1:
                raise ValueError(f"Version non prise en charge: {version}")
            
            # Lecture du nombre de frames
            frame_count = struct.unpack('<I', f.read(4))[0]
            
            # Lecture des frames
            for _ in range(frame_count):
                frame = {}
                
                # Timestamp
                frame['time'] = struct.unpack('<d', f.read(8))[0]
                
                # Balle
                ball_pos_x, ball_pos_y, ball_pos_z = struct.unpack('<fff', f.read(12))
                ball_vel_x, ball_vel_y, ball_vel_z = struct.unpack('<fff', f.read(12))
                
                frame['ball'] = {
                    'position': {'x': ball_pos_x, 'y': ball_pos_y, 'z': ball_pos_z},
                    'velocity': {'x': ball_vel_x, 'y': ball_vel_y, 'z': ball_vel_z}
                }
                
                # Voitures
                car_count = struct.unpack('<H', f.read(2))[0]
                cars = []
                
                for _ in range(car_count):
                    car_id, player_id = struct.unpack('<HH', f.read(4))
                    
                    pos_x, pos_y, pos_z = struct.unpack('<fff', f.read(12))
                    rot_pitch, rot_yaw, rot_roll = struct.unpack('<fff', f.read(12))
                    vel_x, vel_y, vel_z = struct.unpack('<fff', f.read(12))
                    boost = struct.unpack('<B', f.read(1))[0]
                    
                    car = {
                        'id': str(car_id),
                        'player_id': str(player_id),
                        'position': {'x': pos_x, 'y': pos_y, 'z': pos_z},
                        'rotation': {'pitch': rot_pitch, 'yaw': rot_yaw, 'roll': rot_roll},
                        'velocity': {'x': vel_x, 'y': vel_y, 'z': vel_z},
                        'boost': boost
                    }
                    cars.append(car)
                
                frame['cars'] = cars
                frames.append(frame)
        
        return frames 