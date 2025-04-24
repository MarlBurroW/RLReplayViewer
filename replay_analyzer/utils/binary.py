import struct
import os
import traceback
from typing import List, Dict, Any
import aiofiles


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