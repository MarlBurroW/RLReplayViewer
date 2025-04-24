import json
import traceback
from typing import Dict, Any, Tuple, List, Optional

from replay_analyzer.models.replay import TeamStats, PlayerInfo, PlayerStatsDetails, TimelineEvent
from replay_analyzer.models.frames import ReplayDataProcessed
from replay_analyzer.utils.helpers import get_prop_value, normalize_player_id


def find_players_and_teams(data: Dict, depth: int = 0, max_depth: int = 10) -> Dict[str, Dict]:
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
    
    # --- Deuxième passage : Extraire les équipes et les joueurs, en utilisant les correspondances d'acteur ---
    print("[DEBUG] Second Pass: Extracting Team and Player Data...")
    for key, prop_data in header_props:
        prop_value = get_prop_value(prop_data)

        # Extract Teams
        if key == 'Teams' and prop_data.get('kind') == 'ArrayProperty' and isinstance(prop_value, list):
            print(f"[DEBUG] Processing Teams Property (found {len(prop_value)} entries)")
            for team_index, team_prop_list in enumerate(prop_value):
                if isinstance(team_prop_list, dict) and 'elements' in team_prop_list:
                    team_data: Dict[str, Any] = {'id': str(team_index)}
                    print(f"[DEBUG]  Processing Team Index {team_index}")
                    for sub_key, sub_prop in team_prop_list['elements']:
                        sub_value = get_prop_value(sub_prop)
                        kind = sub_prop.get('kind')
                        if sub_key == 'Score' and kind == 'IntProperty':
                            team_data['score'] = sub_value
                            print(f"[DEBUG]    Found Score: {sub_value}")
                        elif sub_key == 'TeamName' and kind == 'NameProperty':
                            team_data['name'] = sub_value
                    if 'score' in team_data: # Only add if score was found
                        teams[str(team_index)] = team_data
                    else:
                        print(f"[WARNING] Team index {team_index} processed, but no 'Score' found.")


def process_replay_metadata(replay_id: str, raw_data: Dict[str, Any]) -> ReplayDataProcessed:
    """Traite les données JSON brutes pour extraire métadonnées et frames."""
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
    
    print(f"[DEBUG] Propriétés extraites du header: {list(header_props.keys())}")
    
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
        processed.teams["0"] = TeamStats(id="0", name="Équipe Bleue", score=0)
        processed.teams["1"] = TeamStats(id="1", name="Équipe Orange", score=0)
    
    # Si nous avons trouvé des joueurs
    if players_and_teams.get("players"):
        for player_id, player_data in players_and_teams["players"].items():
            # Extraire les statistiques du joueur
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
    
    # Génération de la timeline (simplement des événements de début et fin)
    processed.timeline = [
        TimelineEvent(type="match_start", time=0.0),
        TimelineEvent(type="match_end", time=processed.duration)
    ]
    
    print(f"[INFO] Traitement des métadonnées terminé pour {replay_id}")
    return processed


def generate_timeline_events(processed_data: Dict[str, Any], raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Génère des événements de timeline (buts, etc.)"""
    timeline = []
    duration = processed_data.get("duration", 300.0)
    
    # Ajouter au moins des événements de début et fin de match
    timeline.append({
        "type": "match_start",
        "time": 0.0
    })
    
    timeline.append({
        "type": "match_end",
        "time": duration
    })
    
    # Trier les événements par temps
    timeline.sort(key=lambda x: x["time"])
    return timeline 