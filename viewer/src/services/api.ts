import { Frame, ProcessingStatus, Replay, RawReplayData, RawFrame } from "../types/replay";
import { fetchData } from "../lib/utils";

// Utiliser le proxy configuré dans Vite au lieu de l'URL directe
const API_BASE = '/api';

export async function getReplayMetadata(replayId: string): Promise<Replay> {
  try {
    // Utiliser le nouvel endpoint /meta pour les métadonnées
    const metadata = await fetchData<Replay>(`${API_BASE}/replays/${replayId}/meta`);
    return metadata;
  } catch (error) {
    console.warn("Impossible d'obtenir les métadonnées complètes. Création d'une structure minimale.", error);
    
    // Si les métadonnées complètes ne sont pas disponibles, créer une structure minimale
    return {
      id: replayId,
      duration: 0, // Sera mis à jour avec la dernière frame
      map_name: "Unknown Map",
      game_type: "Unknown Game Type",
      match_type: "Unknown Match Type",
      teams: {},
      players: {},
      timeline: []
    };
  }
}

export async function getReplayFrames(replayId: string): Promise<Frame[]> {
  // Utiliser la nouvelle méthode pour récupérer et précompiler les frames brutes
  const frames = await getRawFramesAndProcess(replayId);
  
  // Mettre à jour la durée dans les métadonnées si nécessaire
  if (frames.length > 0) {
    const lastFrame = frames[frames.length - 1];
    const totalDuration = lastFrame.time;
    
    // Pas besoin de mettre à jour les métadonnées ici, car elles sont déjà chargées séparément
  }
  
  return frames;
}

export async function getReplayStatus(replayId: string): Promise<ProcessingStatus> {
  return fetchData<ProcessingStatus>(`${API_BASE}/replays/${replayId}/status`);
}

// Nouvelle fonction pour récupérer et traiter les frames brutes de rrrocket
export async function getRawFramesAndProcess(replayId: string): Promise<Frame[]> {
  console.log("Récupération et précompilation des frames brutes pour", replayId);
  
  try {
    // Utiliser le nouvel endpoint /raw pour les données brutes complètes
    const response = await fetch(`${API_BASE}/replays/${replayId}/raw`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const rawData: RawReplayData = await response.json();
    return processRawFrames(rawData);
  } catch (error) {
    console.error("Erreur lors de la récupération des frames brutes:", error);
    throw error;
  }
}

export function processRawFrames(rawData: RawReplayData): Frame[] {
  console.log("Précompilation des frames...");
  
  // Debuggage: afficher la structure du JSON reçu pour comprendre ce qu'on a reçu
  console.log("Structure JSON reçue:", Object.keys(rawData));
  console.log("network_frames existe:", !!rawData.network_frames);
  if (rawData.network_frames) {
    console.log("Nombre de frames dans le JSON:", rawData.network_frames.frames.length);
  }
  
  // Examiner une frame pour comprendre sa structure
  if (rawData.network_frames && rawData.network_frames.frames.length > 0) {
    const sampleFrame = rawData.network_frames.frames[0];
    console.log("Structure d'une frame:", Object.keys(sampleFrame));
    
    if (sampleFrame.updated_actors && sampleFrame.updated_actors.length > 0) {
      console.log("Nombre d'acteurs mis à jour dans la première frame:", sampleFrame.updated_actors.length);
    }
    
    if (sampleFrame.new_actors && sampleFrame.new_actors.length > 0) {
      console.log("Nombre de nouveaux acteurs dans la première frame:", sampleFrame.new_actors.length);
      console.log("Premier nouvel acteur:", sampleFrame.new_actors[0]);
    }
  }
  
  const frames: Frame[] = [];
  
  // Approche alternative avec conservation d'état entre les frames
  console.log("Approche alternative : détection d'acteurs plus robuste");
  
  // État global (conservé entre les frames)
  const globalState = {
    ball: {
      position: [0, 0, 93] as [number, number, number],
      rotation: [0, 0, 0, 1] as [number, number, number, number],
      velocity: [0, 0, 0] as [number, number, number],
      lastUpdated: 0,
      actorId: 0  // ID actuel de la balle, peut changer au cours du replay
    },
    cars: {} as Record<string, {
      position: [number, number, number];
      rotation: [number, number, number, number];
      velocity: [number, number, number];
      boost: number;
      lastUpdated: number;
      actorId: number;
      active: boolean; // Indique si la voiture est active dans la frame courante
    }>,
    nextCarIndex: 1, // Pour générer des IDs de voiture uniques
    // Map pour suivre les acteurs qui sont des balles ou des voitures
    actorTypes: new Map<number, { type: 'ball' | 'car', id: string }>()
  };
  
  // Identifiants d'objets importants (indices dans le tableau objects)
  const ballTypeIds = findObjectTypeIndices(rawData.objects, "Ball_TA");
  const carTypeIds = findObjectTypeIndices(rawData.objects, "Car_TA");
  
  console.log("Types identifiés:", { 
    ballTypes: ballTypeIds, 
    carTypes: carTypeIds
  });
  
  // Pour chaque frame brute dans le replay
  let frameCount = 0;
  for (const rawFrame of rawData.network_frames.frames) {
    frameCount++;
    
    // Traiter les nouveaux acteurs d'abord pour mettre à jour notre map d'acteurs
    if (rawFrame.new_actors && rawFrame.new_actors.length > 0) {
      for (const actor of rawFrame.new_actors) {
        // Détecter si c'est une balle
        if (ballTypeIds.includes(actor.object_id)) {
          if (frameCount > 10) { // Ne pas logger les acteurs initiaux
            console.log(`Nouvelle balle détectée à la frame ${frameCount}, actorId=${actor.actor_id}, objectId=${actor.object_id}`);
          }
          
          // Mettre à jour l'ID de la balle dans l'état global
          globalState.ball.actorId = actor.actor_id;
          globalState.actorTypes.set(actor.actor_id, { type: 'ball', id: 'ball' });
        }
        // Détecter si c'est une voiture
        else if (carTypeIds.includes(actor.object_id)) {
          const carId = `car_${globalState.nextCarIndex++}`;
          if (frameCount > 10) { // Ne pas logger les acteurs initiaux
            console.log(`Nouvelle voiture détectée à la frame ${frameCount}, actorId=${actor.actor_id}, carId=${carId}, objectId=${actor.object_id}`);
          }
          
          // Créer une nouvelle entrée pour cette voiture
          globalState.cars[carId] = {
            position: [0, 0, 0],
            rotation: [0, 0, 0, 1],
            velocity: [0, 0, 0],
            boost: 0,
            lastUpdated: frameCount,
            actorId: actor.actor_id,
            active: true
          };
          
          globalState.actorTypes.set(actor.actor_id, { type: 'car', id: carId });
        }
      }
    }
    
    // Avant de traiter les mises à jour, marquer toutes les voitures comme inactives
    // pour cette frame (elles seront réactivées si elles sont mises à jour)
    if (frameCount > 20) { // Ignorer les frames initiales
      for (const carId in globalState.cars) {
        // Une voiture est considérée inactive si elle n'a pas été mise à jour 
        // depuis plus de 5 frames et n'est pas un acteur connu
        if (frameCount - globalState.cars[carId].lastUpdated > 5 && 
            !globalState.actorTypes.has(globalState.cars[carId].actorId)) {
          globalState.cars[carId].active = false;
        }
      }
    }
    
    // Traiter les acteurs supprimés
    if (rawFrame.deleted_actors && rawFrame.deleted_actors.length > 0) {
      for (const deletedId of rawFrame.deleted_actors) {
        // Si c'était une balle ou une voiture connue, le noter
        const actorInfo = globalState.actorTypes.get(deletedId);
        if (actorInfo) {
          if (frameCount > 10) { // Ne pas logger les acteurs initiaux
            console.log(`Acteur supprimé à la frame ${frameCount}: ${actorInfo.type} ${actorInfo.id}, actorId=${deletedId}`);
          }
          
          // Supprimer l'acteur de notre map
          globalState.actorTypes.delete(deletedId);
          
          // Si c'était une voiture, la marquer comme inactive mais ne pas la supprimer complètement
          // pour maintenir la continuité visuelle
          if (actorInfo.type === 'car') {
            globalState.cars[actorInfo.id].active = false;
          }
        }
      }
    }
    
    // Structure pour stocker l'état actuel de la balle et des voitures
    const frameState: {
      time: number;
      delta: number;
      ball: {
        position: [number, number, number];
        rotation: [number, number, number, number];
        velocity: [number, number, number];
      };
      cars: Record<string, {
        position: [number, number, number];
        rotation: [number, number, number, number];
        velocity: [number, number, number];
        boost: number;
      }>;
    } = {
      time: rawFrame.time,
      delta: rawFrame.delta,
      ball: {
        position: [...globalState.ball.position],
        rotation: [...globalState.ball.rotation],
        velocity: [...globalState.ball.velocity]
      },
      cars: {}
    };
    
    // Copier les états des voitures du global au frame actuel
    for (const [carId, carState] of Object.entries(globalState.cars)) {
      if (carState.active) {
        frameState.cars[carId] = {
          position: [...carState.position],
          rotation: [...carState.rotation],
          velocity: [...carState.velocity],
          boost: carState.boost
        };
      }
    }
    
    // Traiter les acteurs mis à jour
    for (const update of rawFrame.updated_actors || []) {
      // Vérifier si nous avons un acteur connu
      const actorInfo = globalState.actorTypes.get(update.actor_id);
      
      // Si c'est un acteur connu et qu'il a un RigidBody
      if (actorInfo && update.attribute && update.attribute.RigidBody) {
        const rb = update.attribute.RigidBody;
        
        // Balle
        if (actorInfo.type === 'ball') {
          if (rb.location) {
            // Mettre à jour l'état global de la balle
            globalState.ball.position = [
              rb.location.x || 0, 
              rb.location.y || 0, 
              rb.location.z || 0
            ];
            globalState.ball.lastUpdated = frameCount;
            
            // Mettre à jour l'état de la balle pour cette frame
            frameState.ball.position = [...globalState.ball.position];
            
            if (rb.rotation) {
              globalState.ball.rotation = [
                rb.rotation.x || 0, 
                rb.rotation.y || 0, 
                rb.rotation.z || 0, 
                rb.rotation.w || 1
              ];
              frameState.ball.rotation = [...globalState.ball.rotation];
            }
            
            if (rb.linear_velocity) {
              globalState.ball.velocity = [
                rb.linear_velocity.x || 0, 
                rb.linear_velocity.y || 0, 
                rb.linear_velocity.z || 0
              ];
              frameState.ball.velocity = [...globalState.ball.velocity];
            }
            
            if (frameCount % 1000 === 0) { // Limiter les logs
              console.log(`Balle mise à jour à t=${rawFrame.time}, pos=[${frameState.ball.position}], frame ${frameCount}`);
            }
          }
        }
        // Voiture
        else if (actorInfo.type === 'car') {
          const carId = actorInfo.id;
          
          // Marquer la voiture comme active
          globalState.cars[carId].active = true;
          
          if (rb.location) {
            // Mettre à jour l'état global de la voiture
            globalState.cars[carId].position = [
              rb.location.x || 0, 
              rb.location.y || 0, 
              rb.location.z || 0
            ];
            globalState.cars[carId].lastUpdated = frameCount;
            
            // Mettre à jour l'état de la voiture pour cette frame
            frameState.cars[carId].position = [...globalState.cars[carId].position];
          }
          
          if (rb.rotation) {
            globalState.cars[carId].rotation = [
              rb.rotation.x || 0, 
              rb.rotation.y || 0, 
              rb.rotation.z || 0, 
              rb.rotation.w || 1
            ];
            frameState.cars[carId].rotation = [...globalState.cars[carId].rotation];
          }
          
          if (rb.linear_velocity) {
            globalState.cars[carId].velocity = [
              rb.linear_velocity.x || 0, 
              rb.linear_velocity.y || 0, 
              rb.linear_velocity.z || 0
            ];
            frameState.cars[carId].velocity = [...globalState.cars[carId].velocity];
          }
        }
      }
      // Détection heuristique pour d'autres acteurs (hors de notre carte d'acteurs connus)
      // Cela peut aider à détecter de nouveaux acteurs entre les buts
      else if (update.attribute && update.attribute.RigidBody) {
        const rb = update.attribute.RigidBody;
        
        // Si l'acteur a un RigidBody mais n'est pas dans notre carte
        // et qu'il a une position Z élevée, c'est probablement une balle
        if (rb.location && rb.location.z > 40) {
          // Vérifier s'il se trouve dans la zone de jeu
          const isInField = Math.abs(rb.location.x) < 5000 && Math.abs(rb.location.y) < 5000;
          
          if (isInField) {
            console.log(`Possible nouvelle balle détectée à la frame ${frameCount}, actorId=${update.actor_id}, pos=[${rb.location.x}, ${rb.location.y}, ${rb.location.z}]`);
            
            // Mettre à jour l'ID de la balle et notre carte d'acteurs
            globalState.ball.actorId = update.actor_id;
            globalState.actorTypes.set(update.actor_id, { type: 'ball', id: 'ball' });
            
            // Mettre à jour la position
            globalState.ball.position = [
              rb.location.x || 0, 
              rb.location.y || 0, 
              rb.location.z || 0
            ];
            globalState.ball.lastUpdated = frameCount;
            
            // Mettre à jour l'état de la balle pour cette frame
            frameState.ball.position = [...globalState.ball.position];
            
            if (rb.rotation) {
              globalState.ball.rotation = [
                rb.rotation.x || 0, 
                rb.rotation.y || 0, 
                rb.rotation.z || 0, 
                rb.rotation.w || 1
              ];
              frameState.ball.rotation = [...globalState.ball.rotation];
            }
            
            if (rb.linear_velocity) {
              globalState.ball.velocity = [
                rb.linear_velocity.x || 0, 
                rb.linear_velocity.y || 0, 
                rb.linear_velocity.z || 0
              ];
              frameState.ball.velocity = [...globalState.ball.velocity];
            }
          }
        }
        // Sinon, c'est peut-être une voiture
        else if (rb.location && rb.location.z < 40) {
          // Vérifier s'il se trouve dans la zone de jeu
          const isInField = Math.abs(rb.location.x) < 5000 && Math.abs(rb.location.y) < 5000;
          
          if (isInField) {
            const carId = `car_${globalState.nextCarIndex++}`;
            console.log(`Possible nouvelle voiture détectée à la frame ${frameCount}, actorId=${update.actor_id}, carId=${carId}, pos=[${rb.location.x}, ${rb.location.y}, ${rb.location.z}]`);
            
            // Créer une nouvelle entrée pour cette voiture
            globalState.cars[carId] = {
              position: [rb.location.x || 0, rb.location.y || 0, rb.location.z || 0],
              rotation: rb.rotation ? 
                [rb.rotation.x || 0, rb.rotation.y || 0, rb.rotation.z || 0, rb.rotation.w || 1] : 
                [0, 0, 0, 1],
              velocity: rb.linear_velocity ? 
                [rb.linear_velocity.x || 0, rb.linear_velocity.y || 0, rb.linear_velocity.z || 0] : 
                [0, 0, 0],
              boost: 0,
              lastUpdated: frameCount,
              actorId: update.actor_id,
              active: true
            };
            
            // Ajouter à notre carte d'acteurs
            globalState.actorTypes.set(update.actor_id, { type: 'car', id: carId });
            
            // Mettre à jour l'état de la voiture pour cette frame
            frameState.cars[carId] = {
              position: [...globalState.cars[carId].position],
              rotation: [...globalState.cars[carId].rotation],
              velocity: [...globalState.cars[carId].velocity],
              boost: 0
            };
          }
        }
      }
    }
    
    // Ajouter la frame au résultat
    frames.push(frameState);
    
    // Logs périodiques pour suivre la progression
    if (frameCount % 1000 === 0 || frameCount === 1) {
      console.log(`Traitement en cours: ${frameCount}/${rawData.network_frames.frames.length} frames`);
    }
  }
  
  console.log(`Précompilation terminée: ${frames.length} frames générées sur ${frameCount} traitées`);
  // Afficher quelques statistiques
  const activeCarCount = Object.values(globalState.cars).filter(car => car.active).length;
  console.log(`Nombre de voitures détectées: ${Object.keys(globalState.cars).length} (${activeCarCount} actives)`);
  console.log(`Dernière mise à jour de la balle: frame ${globalState.ball.lastUpdated}`);
  console.log(`Acteurs connus à la fin: ${globalState.actorTypes.size}`);
  
  return frames;
}

// Fonction utilitaire pour trouver les indices des types d'objets qui contiennent une chaîne spécifique
function findObjectTypeIndices(objects: string[], searchString: string): number[] {
  return objects.reduce<number[]>((indices, objectType, index) => {
    if (objectType.includes(searchString)) {
      indices.push(index);
    }
    return indices;
  }, []);
}


