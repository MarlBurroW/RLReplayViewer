from typing import Dict, List, Optional
from pydantic import BaseModel


class BallState(BaseModel):
    """État de la balle dans une frame."""
    position: List[float] = [0.0, 0.0, 93.0]
    rotation: List[float] = [0.0, 0.0, 0.0, 1.0]
    velocity: List[float] = [0.0, 0.0, 0.0]


class CarState(BaseModel):
    """État d'une voiture dans une frame."""
    position: List[float] = [0.0, 0.0, 17.0]
    rotation: List[float] = [0.0, 0.0, 0.0, 1.0]
    velocity: Optional[List[float]] = None
    boost: int = 33


class FrameData(BaseModel):
    """Données d'une frame."""
    time: float
    delta: float
    ball: Optional[BallState] = None
    cars: Dict[str, CarState] = {}


class ReplayDataProcessed(BaseModel):
    """Données complètes d'un replay traité."""
    id: str
    teams: Dict[str, 'TeamStats'] = {}
    players: Dict[str, 'PlayerInfo'] = {}
    timeline: List['TimelineEvent'] = []
    frames: List[FrameData] = []
    duration: float = 300.0
    map_name: Optional[str] = None
    match_type: Optional[str] = None
    game_type: Optional[str] = None
    date: Optional[str] = None
    car_player_map: Dict[str, str] = {}  # {car_id: player_id}


class ProcessingStatus(BaseModel):
    """Statut de traitement d'un replay."""
    status: str  # "processing", "completed", "failed", "metadata_only"
    progress: int  # 0-100
    message: Optional[str] = None
    error: Optional[str] = None 