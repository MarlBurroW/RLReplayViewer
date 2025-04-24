import traceback
from typing import Dict, List, Any, Tuple, Optional

from replay_analyzer.utils.helpers import get_player_team


def extract_frames_from_schema(content_data: Dict[str, Any], player_actor_map: Dict[str, int], 
                                fps: float, player_ids: List[str], 
                                players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Extrait les frames à partir des structures de données connues, sans générer de frames synthétiques.
    
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
            frames, car_player_map = extract_frames_from_network_frames(content_data, player_actor_map, fps, player_ids, players_data)
        
        # Si pas de frames depuis network_frames, essayer la structure ticks (ancienne)
        if not frames and "ticks" in content_data:
            print("[INFO] Extraction des frames depuis ticks")
            frames, car_player_map = extract_frames_from_ticks(content_data, player_actor_map, fps, player_ids, players_data)
        
        # Si toujours pas de frames, essayer la structure frames (alternative)
        if not frames and "frames" in content_data:
            print("[INFO] Extraction des frames depuis frames")
            frames, car_player_map = extract_frames_from_direct(content_data, player_actor_map, fps, player_ids, players_data)
        
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

def extract_frames_from_network_frames(content_data: Dict[str, Any], player_actor_map: Dict[str, int], 
                                     fps: float, player_ids: List[str], players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait les frames à partir de la structure network_frames."""
    frames = []
    car_player_map = {}
    
    if not content_data.get("network_frames"):
        return frames, car_player_map
    
    try:
        network_frames = content_data["network_frames"]
        
        # Collecter les timestamps uniques
        timestamps = set()
        for frame_data in network_frames:
            if "time" in frame_data:
                timestamps.add(frame_data["time"])
        
        if not timestamps:
            print("[WARNING] Aucun timestamp trouvé dans network_frames")
            return frames, car_player_map
        
        # Convertir en liste et trier
        timestamp_list = sorted(list(timestamps))
        
        # Si trop de timestamps, échantillonner
        if len(timestamp_list) > 600:
            sample_rate = len(timestamp_list) // 600
            timestamp_list = [timestamp_list[i] for i in range(0, len(timestamp_list), sample_rate)]
        
        # Créer les frames
        for time in timestamp_list:
            frame = {
                "time": time,
                "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
                "cars": {}
            }
            
            # Trouver les données pour ce timestamp
            for frame_data in network_frames:
                if frame_data.get("time") == time:
                    # Traiter la balle
                    if "ball" in frame_data and isinstance(frame_data["ball"], dict):
                        process_ball_data(frame_data["ball"], frame)
                    
                    # Traiter les voitures
                    if "cars" in frame_data and isinstance(frame_data["cars"], dict):
                        for car_id, car_data in frame_data["cars"].items():
                            process_car_data(car_id, car_data, frame, car_player_map, player_actor_map, players_data)
            
            frames.append(frame)
        
        return frames, car_player_map
    
    except Exception as e:
        print(f"[ERROR] Exception lors de l'extraction depuis network_frames: {e}")
        traceback.print_exc()
        return [], {}

def extract_frames_from_ticks(content_data: Dict[str, Any], player_actor_map: Dict[str, int], 
                             fps: float, player_ids: List[str], players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait les frames à partir de la structure ticks."""
    frames = []
    car_player_map = {}
    
    if not content_data.get("ticks"):
        return frames, car_player_map
    
    try:
        ticks = content_data["ticks"]
        
        # Collecter les timestamps uniques
        timestamps = set()
        for tick in ticks:
            if "time" in tick:
                timestamps.add(tick["time"])
        
        if not timestamps:
            print("[WARNING] Aucun timestamp trouvé dans ticks")
            return frames, car_player_map
        
        # Convertir en liste et trier
        timestamp_list = sorted(list(timestamps))
        
        # Si trop de timestamps, échantillonner
        if len(timestamp_list) > 600:
            sample_rate = len(timestamp_list) // 600
            timestamp_list = [timestamp_list[i] for i in range(0, len(timestamp_list), sample_rate)]
        
        # Créer les frames
        for time in timestamp_list:
            frame = {
                "time": time,
                "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
                "cars": {}
            }
            
            # Trouver les données pour ce timestamp
            for tick in ticks:
                if tick.get("time") == time:
                    # Traiter les acteurs
                    if "actors" in tick and isinstance(tick["actors"], dict):
                        for actor_id, actor_data in tick["actors"].items():
                            # Traiter la balle
                            if actor_data.get("type") == "ball":
                                process_ball_data(actor_data, frame)
                            
                            # Traiter les voitures
                            elif actor_data.get("type") == "car":
                                # Déterminer si cet acteur est associé à un joueur
                                if int(actor_id) in player_actor_map:
                                    player_id = player_actor_map[int(actor_id)]
                                    process_car_data(actor_id, actor_data, frame, car_player_map, player_actor_map, players_data, player_id)
            
            frames.append(frame)
        
        return frames, car_player_map
    
    except Exception as e:
        print(f"[ERROR] Exception lors de l'extraction depuis ticks: {e}")
        traceback.print_exc()
        return [], {}

def extract_frames_from_direct(content_data: Dict[str, Any], player_actor_map: Dict[str, int], 
                              fps: float, player_ids: List[str], players_data: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """Extrait les frames à partir de la structure frames directe."""
    frames = []
    car_player_map = {}
    
    if not content_data.get("frames"):
        return frames, car_player_map
    
    try:
        direct_frames = content_data["frames"]
        
        # Collecter les timestamps si disponibles
        timestamps = []
        for frame_data in direct_frames:
            if "time" in frame_data:
                timestamps.append(frame_data["time"])
        
        # Si pas de timestamps, générer des timestamps artificiels
        if not timestamps:
            duration = content_data.get("duration", 300)
            timestamps = [i / fps for i in range(int(duration * fps))]
        
        # Si trop de timestamps, échantillonner
        if len(timestamps) > 600:
            sample_rate = len(timestamps) // 600
            timestamps = [timestamps[i] for i in range(0, len(timestamps), sample_rate)]
        
        # Créer les frames
        for i, time in enumerate(timestamps):
            frame = {
                "time": time,
                "ball": {"position": [0, 0, 93], "velocity": [0, 0, 0]},
                "cars": {}
            }
            
            # Obtenir les données de frame correspondantes
            if i < len(direct_frames):
                frame_data = direct_frames[i]
                
                # Traiter la balle
                if "ball" in frame_data and isinstance(frame_data["ball"], dict):
                    process_ball_data(frame_data["ball"], frame)
                
                # Traiter les voitures
                if "cars" in frame_data and isinstance(frame_data["cars"], dict):
                    for car_id, car_data in frame_data["cars"].items():
                        process_car_data(car_id, car_data, frame, car_player_map, player_actor_map, players_data)
            
            frames.append(frame)
        
        return frames, car_player_map
    
    except Exception as e:
        print(f"[ERROR] Exception lors de l'extraction directe des frames: {e}")
        traceback.print_exc()
        return [], {}

def process_ball_data(ball_data: Dict[str, Any], frame: Dict[str, Any]) -> None:
    """
    Traite les données d'une balle et les ajoute à la frame.
    """
    if not isinstance(ball_data, dict):
        return
    
    ball_state = {
        "position": [0, 0, 93],  # Position par défaut
        "velocity": [0, 0, 0]    # Vitesse par défaut
    }
    
    # Position - différents formats possibles
    if "position" in ball_data and isinstance(ball_data["position"], list):
        ball_state["position"] = ball_data["position"][:3]
    elif "loc" in ball_data and isinstance(ball_data["loc"], list):
        ball_state["position"] = ball_data["loc"][:3]
    
    # Vitesse - différents formats possibles
    if "velocity" in ball_data and isinstance(ball_data["velocity"], list):
        ball_state["velocity"] = ball_data["velocity"][:3]
    elif "vel" in ball_data and isinstance(ball_data["vel"], list):
        ball_state["velocity"] = ball_data["vel"][:3]
    
    frame["ball"] = ball_state

def process_car_data(car_id_str: str, car_data: Dict[str, Any], frame: Dict[str, Any], 
                    car_player_map: Dict[str, str], actor_player_map: Dict[int, str], 
                    players_data: Dict[str, Any], direct_player_id: Optional[str] = None) -> None:
    """
    Traite les données d'une voiture et les ajoute à la frame si possible.
    
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