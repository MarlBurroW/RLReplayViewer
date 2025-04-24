export class ReplayParser {
  // Fonction principale pour traiter les données du replay
  async processReplay(replayData: any, progressCallback: (progress: number) => void): Promise<any> {
    try {
      // Informations de base du replay
      const metadata = this.extractMetadata(replayData);
      
      // Dictionnaires pour l'association d'objets
      const objects = replayData.objects || [];
      const names = replayData.names || [];
      
      // Préparer le suivi des acteurs
      const actorStates: Map<number, any> = new Map();
      const carActors: Map<number, string> = new Map(); // actor_id -> player_id
      let ballActor: number | null = null;
      const boostActors: Map<number, any> = new Map();
      
      // Préparer le résultat
      const processedFrames = [];
      
      // Obtenir les frames
      const frames = replayData.network_frames?.frames || [];
      const totalFrames = frames.length;
      
      // Pour chaque frame
      for (let i = 0; i < totalFrames; i++) {
        const frame = frames[i];
        
        // Mettre à jour la progression
        if (i % 10 === 0) { // Mise à jour tous les 10 frames pour éviter trop d'appels
          progressCallback((i / totalFrames) * 100);
        }
        
        // Traiter les nouveaux acteurs
        for (const actor of frame.new_actors || []) {
          const objectType = objects[actor.object_id] || '';
          
          // Identifier le type d'acteur
          if (objectType.includes('Ball_TA')) {
            ballActor = actor.actor_id;
            actorStates.set(actor.actor_id, {
              type: 'ball',
              location: actor.initial_trajectory?.location,
              rotation: actor.initial_trajectory?.rotation
            });
          } 
          else if (objectType.includes('Car_TA')) {
            actorStates.set(actor.actor_id, {
              type: 'car',
              location: actor.initial_trajectory?.location,
              rotation: actor.initial_trajectory?.rotation,
              boost: 0
            });
          }
          else if (objectType.includes('VehiclePickup_Boost_TA')) {
            boostActors.set(actor.actor_id, {
              location: actor.initial_trajectory?.location,
              active: true
            });
          }
        }
        
        // Traiter les mises à jour des acteurs
        for (const update of frame.updated_actors || []) {
          const actor = actorStates.get(update.actor_id);
          if (!actor) continue;
          
          // Mise à jour de la balle
          if (actor.type === 'ball' && update.attribute?.RigidBody) {
            const rigidBody = update.attribute.RigidBody;
            actor.location = rigidBody.location;
            actor.rotation = rigidBody.rotation;
            actor.linearVelocity = rigidBody.linear_velocity;
            actor.angularVelocity = rigidBody.angular_velocity;
          }
          
          // Mise à jour d'une voiture
          else if (actor.type === 'car') {
            if (update.attribute?.RigidBody) {
              const rigidBody = update.attribute.RigidBody;
              actor.location = rigidBody.location;
              actor.rotation = rigidBody.rotation;
              actor.linearVelocity = rigidBody.linear_velocity;
              actor.angularVelocity = rigidBody.angular_velocity;
            }
            
            // Mise à jour du boost
            if (update.attribute?.ReplicatedBoost) {
              actor.boost = update.attribute.ReplicatedBoost.boost_amount;
            }
            
            // Association à un joueur
            if (update.attribute?.UniqueId) {
              const uniqueId = update.attribute.UniqueId;
              // Logique d'association basée sur l'ID unique (simplifié)
              if (uniqueId.system_id === 11 && uniqueId.remote_id?.Epic) {
                // ID Epic Games
                const playerId = `epic_${uniqueId.remote_id.Epic}`;
                carActors.set(update.actor_id, playerId);
              } else if (uniqueId.system_id === 2 && uniqueId.remote_id?.PlayStation?.online_id) {
                // ID PlayStation
                const playerId = `ps_${uniqueId.remote_id.PlayStation.online_id}`;
                carActors.set(update.actor_id, playerId);
              }
              // Ajouter d'autres plateformes au besoin
            }
            
            // Association via Reservation
            if (update.attribute?.Reservation) {
              const reservation = update.attribute.Reservation;
              const playerName = reservation.name;
              
              // Chercher le joueur par nom
              const player = metadata.players.find((p: any) => p.name === playerName);
              if (player) {
                carActors.set(update.actor_id, player.id);
              }
            }
          }
          
          // Mise à jour des boosts
          else if (boostActors.has(update.actor_id)) {
            const boost = boostActors.get(update.actor_id);
            // Si l'attribut de ramassage est défini, mettre à jour l'état
            if (update.attribute?.PickupNew || update.attribute?.ReplicatedPickupData) {
              boost.active = false; // Le boost a été pris
            }
          }
        }
        
        // Supprimer les acteurs supprimés
        for (const deletedActorId of frame.deleted_actors || []) {
          actorStates.delete(deletedActorId);
          carActors.delete(deletedActorId);
          boostActors.delete(deletedActorId);
          if (ballActor === deletedActorId) {
            ballActor = null;
          }
        }
        
        // Créer la frame traitée
        const processedFrame = {
          time: frame.time,
          delta: frame.delta,
          ball: null as any,
          cars: [] as any[],
          boosts: [] as any[]
        };
        
        // Ajouter la balle si elle existe
        if (ballActor && actorStates.has(ballActor)) {
          const ballState = actorStates.get(ballActor);
          processedFrame.ball = {
            position: ballState.location || { x: 0, y: 0, z: 0 },
            rotation: ballState.rotation,
            velocity: ballState.linearVelocity,
            angularVelocity: ballState.angularVelocity
          };
        }
        
        // Ajouter les voitures
        for (const [actorId, actor] of actorStates.entries()) {
          if (actor.type === 'car') {
            const playerId = carActors.get(actorId) || 'unknown';
            processedFrame.cars.push({
              id: actorId.toString(),
              player_id: playerId,
              position: actor.location || { x: 0, y: 0, z: 0 },
              rotation: actor.rotation || { pitch: 0, yaw: 0, roll: 0 },
              velocity: actor.linearVelocity,
              angularVelocity: actor.angularVelocity,
              boost: actor.boost || 0
            });
          }
        }
        
        // Ajouter les boosts
        for (const [actorId, boost] of boostActors.entries()) {
          processedFrame.boosts.push({
            id: actorId.toString(),
            position: boost.location || { x: 0, y: 0, z: 0 },
            active: boost.active
          });
        }
        
        processedFrames.push(processedFrame);
      }
      
      // Rapport final de progression
      progressCallback(100);
      
      return {
        metadata,
        frames: processedFrames
      };
    } catch (error) {
      console.error('Erreur lors du traitement du replay:', error);
      throw error;
    }
  }
  
  // Extraire les métadonnées du replay
  private extractMetadata(replayData: any): any {
    const properties = replayData.properties || {};
    
    // Extraire les joueurs
    const players = (properties.PlayerStats || []).map((player: any) => {
      // Extraire l'ID du joueur
      let playerId = '';
      if (player.PlayerID?.fields?.EpicAccountId) {
        playerId = `epic_${player.PlayerID.fields.EpicAccountId}`;
      } else if (player.OnlineID && player.OnlineID !== '0') {
        playerId = `platform_${player.OnlineID}`;
      } else {
        playerId = `name_${player.Name}`;
      }
      
      return {
        id: playerId,
        name: player.Name || 'Unknown',
        team: player.Team || 0,
        score: player.Score || 0,
        goals: player.Goals || 0,
        assists: player.Assists || 0,
        saves: player.Saves || 0,
        shots: player.Shots || 0
      };
    });
    
    return {
      id: replayData.id || '',
      mapName: properties.MapName || 'Unknown Map',
      matchType: properties.MatchType || 'Unknown Mode',
      teamSize: properties.TeamSize || 0,
      duration: properties.TotalSecondsPlayed || 0,
      date: properties.Date || '',
      players
    };
  }
} 