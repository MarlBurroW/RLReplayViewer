from typing import Dict, List, Optional, Any
from pydantic import BaseModel


class ReplayInfo(BaseModel):
    """Informations de base sur un replay."""
    id: str
    filename: str
    duration: Optional[float] = None


class TeamStats(BaseModel):
    """Statistiques d'une équipe."""
    id: str
    score: int = 0
    name: str


class PlayerStatsDetails(BaseModel):
    """Détails des statistiques d'un joueur."""
    score: int = 0
    goals: int = 0
    assists: int = 0
    saves: int = 0
    shots: int = 0


class PlayerStats(BaseModel):
    """Statistiques d'un joueur."""
    id: str
    name: str
    score: int = 0
    goals: int = 0
    assists: int = 0
    saves: int = 0
    shots: int = 0
    team: int = 0


class PlayerInfo(BaseModel):
    """Informations sur un joueur."""
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
    """Événement de la timeline."""
    type: str
    time: float
    player_id: Optional[str] = None
    player: Optional[str] = None
    team: Optional[int] = None
    description: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class ReplayDataProcessed(BaseModel):
    """Métadonnées complètes d'un replay traité."""
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
    team0_score: int = 0
    team1_score: int = 0
    score: Optional[Dict[str, Any]] = None
    metadata_status: Optional[str] = "completed"
    frames_status: Optional[str] = None 