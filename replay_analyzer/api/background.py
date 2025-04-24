import asyncio
import os
import traceback
import json
from typing import Dict, Any

from replay_analyzer.utils.binary import BinaryFramesWriter
from replay_analyzer.extractors.frames import extract_frames_from_schema


# Stockage des tâches en arrière-plan
background_tasks = {}


async def process_frames_background(replay_id: str, file_path: str, raw_data: Dict[str, Any], 
                                   player_actor_map: Dict[str, int], player_ids: list, 
                                   players_data: Dict[str, Any], fps: float = 30.0):
    """
    Traite les frames d'un replay en arrière-plan et génère le fichier binaire.
    """
    try:
        # Mettre à jour l'état
        background_tasks[replay_id] = {"status": "processing", "progress": 10, "message": "Extraction des frames..."}
        
        # Extraire les frames en utilisant les méthodes appropriées sans génération synthétique
        try:
            frames, car_player_map = extract_frames_from_schema(raw_data, player_actor_map, fps, player_ids, players_data)
            
            if not frames:
                background_tasks[replay_id] = {
                    "status": "failed", 
                    "error": "Aucune frame n'a pu être extraite", 
                    "progress": 0
                }
                return
            
            # Mettre à jour l'état
            background_tasks[replay_id] = {
                "status": "processing", 
                "progress": 50, 
                "message": f"Écriture de {len(frames)} frames en binaire..."
            }
            
            # Écrire les frames au format binaire
            frames_bin_path = f"data/{replay_id}_frames.bin"
            writer = BinaryFramesWriter()
            writer.write_frames_to_binary(frames, frames_bin_path)
            
            # Mettre à jour l'état
            background_tasks[replay_id] = {"status": "completed", "progress": 100}
            print(f"[INFO] Traitement des frames terminé pour {replay_id}")
        
        except Exception as e:
            print(f"[ERROR] Erreur lors de l'extraction des frames: {e}")
            traceback.print_exc()
            background_tasks[replay_id] = {
                "status": "failed", 
                "error": str(e), 
                "progress": 0
            }
        
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


def get_task_status(replay_id: str) -> Dict[str, Any]:
    """
    Récupère l'état actuel d'une tâche d'arrière-plan.
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
    return {"status": "unknown", "progress": 0, "message": "Aucune tâche trouvée pour ce replay"} 