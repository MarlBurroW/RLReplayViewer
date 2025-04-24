import React, { useRef, useEffect, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls, Grid, Html, Environment, useGLTF } from '@react-three/drei';
import { Bloom, EffectComposer } from '@react-three/postprocessing';
import * as THREE from 'three';
import { Frame, Replay } from '../../types/replay';

// Animation de frames
interface ReplaySceneProps {
  replay: Replay;
  frames: Frame[];
  currentFrame: number;
}

// Fonction pour convertir les coordonnées de Rocket League vers Three.js
// Dans Rocket League: X est avant/arrière, Y est droite/gauche, Z est haut/bas
// Dans Three.js: X est droite/gauche, Y est haut/bas, Z est avant/arrière
function convertPosition(position: [number, number, number]): [number, number, number] {
  // Permutation des axes: [X, Y, Z] RL -> [Y, Z, X] Three.js
  // Et inversion de l'axe Z pour orienter le terrain correctement
  return [position[1], position[2], -position[0]];
}

// Fonction pour convertir les rotations
function convertRotation(rotation: [number, number, number, number]): [number, number, number, number] {
  // Le quaternion doit aussi être ajusté pour correspondre à la nouvelle orientation
  // Dans un quaternion: [x, y, z, w]
  // Permutation identique aux positions, mais plus complexe pour les quaternions
  // Pour une rotation simple, on échange les composantes du quaternion
  return [rotation[1], rotation[2], -rotation[0], rotation[3]];
}

function Ball({ position, rotation }: { position: [number, number, number]; rotation: [number, number, number, number] }) {
  // Convertir les coordonnées pour la balle
  const convertedPosition = convertPosition(position);
  const convertedRotation = convertRotation(rotation);
  
  return (
    <mesh position={convertedPosition} quaternion={new THREE.Quaternion().fromArray(convertedRotation)}>
      <sphereGeometry args={[92.75, 32, 32]} />
      <meshStandardMaterial color="white" />
    </mesh>
  );
}

interface CarProps {
  position: [number, number, number];
  rotation: [number, number, number, number];
  boost: number;
  team: number;
  name: string;
}

function Car({ position, rotation, boost, team, name }: CarProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  // Convertir les coordonnées pour la voiture
  const convertedPosition = convertPosition(position);
  const convertedRotation = convertRotation(rotation);

  // Couleurs d'équipe
  const teamColors = {
    0: new THREE.Color(0x0044ff), // Bleu
    1: new THREE.Color(0xff4400), // Orange
  };

  useEffect(() => {
    if (meshRef.current) {
      // Appliquer la rotation convertie
      meshRef.current.quaternion.set(
        convertedRotation[0],
        convertedRotation[1],
        convertedRotation[2],
        convertedRotation[3]
      );
    }
  }, [rotation]);

  return (
    <group position={convertedPosition}>
      <mesh ref={meshRef} scale={[1, 0.4, 2]}>
        <boxGeometry args={[100, 40, 80]} />
        <meshStandardMaterial color={teamColors[team as 0 | 1]} />
      </mesh>
      
      {/* Boost indicator */}
      <Html position={[0, 80, 0]} center transform distanceFactor={10}>
        <div className="px-2 py-1 bg-black/70 rounded text-white text-sm whitespace-nowrap">
          {name} ({boost})
        </div>
      </Html>
    </group>
  );
}

function Field() {
  // Ajustement des dimensions du terrain pour correspondre aux coordonnées converties
  return (
    <>
      {/* Ground - Ajuster la rotation et les dimensions pour correspondre aux axes convertis */}
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.1, 0]}>
        <planeGeometry args={[10240, 8192]} /> {/* Inverser les dimensions pour le nouveau système d'axes */}
        <meshStandardMaterial color="#3b6d3a" />
      </mesh>
      
      {/* Goals - Corriger les positions pour être aux extrémités avant/arrière */}
      {/* But bleu (équipe 0) */}
      <mesh position={[-5120, 0, 0]} rotation={[0, Math.PI/2, 0]}>
        <boxGeometry args={[1800, 620, 10]} />
        <meshStandardMaterial color="#3344aa" transparent opacity={0.7} />
      </mesh>
      
      {/* But orange (équipe 1) */}
      <mesh position={[5120, 0, 0]} rotation={[0, Math.PI/2, 0]}>
        <boxGeometry args={[1800, 620, 10]} />
        <meshStandardMaterial color="#aa4433" transparent opacity={0.7} />
      </mesh>
      
      {/* Structures des buts - Corriger les positions */}
      {/* Structure du but bleu */}
      <group position={[-5120, 0, 0]} rotation={[0, Math.PI/2, 0]}>
        {/* Montant gauche */}
        <mesh position={[-900, 310, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[20, 620, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
        {/* Montant droit */}
        <mesh position={[900, 310, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[20, 620, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
        {/* Barre transversale */}
        <mesh position={[0, 620, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[1820, 20, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
      </group>
      
      {/* Structure du but orange */}
      <group position={[5120, 0, 0]} rotation={[0, Math.PI/2, 0]}>
        {/* Montant gauche */}
        <mesh position={[-900, 310, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[20, 620, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
        {/* Montant droit */}
        <mesh position={[900, 310, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[20, 620, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
        {/* Barre transversale */}
        <mesh position={[0, 620, 0]} rotation={[0, 0, 0]}>
          <boxGeometry args={[1820, 20, 20]} />
          <meshStandardMaterial color="#bbbbbb" />
        </mesh>
      </group>
      
      {/* Center field */}
      <mesh position={[0, 0, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <ringGeometry args={[0, 1024, 32]} />
        <meshStandardMaterial color="white" side={THREE.DoubleSide} />
      </mesh>
      
      {/* Lignes du terrain - Corriger pour la nouvelle orientation */}
      <group position={[0, 1, 0]}>
        {/* Ligne centrale */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0, 0]}>
          <planeGeometry args={[10, 8192]} />
          <meshStandardMaterial color="white" side={THREE.DoubleSide} />
        </mesh>
        
        {/* Ligne de but - équipe bleue */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[-5120, 0, 0]}>
          <planeGeometry args={[10, 8192]} />
          <meshStandardMaterial color="white" side={THREE.DoubleSide} />
        </mesh>
        
        {/* Ligne de but - équipe orange */}
        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[5120, 0, 0]}>
          <planeGeometry args={[10, 8192]} />
          <meshStandardMaterial color="white" side={THREE.DoubleSide} />
        </mesh>
      </group>
      
      {/* Grid and helpers - Ajuster les dimensions */}
      <Grid 
        args={[10240, 20480]} 
        cellSize={1024} 
        cellThickness={0.6} 
        cellColor="#fff" 
        position={[0, 0, 0]} 
        rotation={[-Math.PI / 2, 0, 0]} 
      />
    </>
  );
}

function Scene({ replay, frames, currentFrame }: ReplaySceneProps) {
  const { camera } = useThree();
  
  useEffect(() => {
    // Position initiale de la caméra - vue aérienne du terrain
    camera.position.set(0, 6000, 0); // Plus haut pour voir tout le terrain
    camera.lookAt(0, 0, 0);
    
    // Augmenter la distance du plan far pour voir plus loin
    if (camera instanceof THREE.PerspectiveCamera) {
      camera.far = 20000; // Augmenter la distance du plan far
      camera.updateProjectionMatrix(); // Nécessaire après modification des paramètres de projection
    }
  }, [camera]);
  
  // Si pas de frames, ne rien afficher
  if (!frames || frames.length === 0 || currentFrame < 0 || currentFrame >= frames.length) {
    return null;
  }
  
  const frame = frames[currentFrame];
  const players = replay.players;

  // Map pour associer les IDs de voitures générés lors de la précompilation aux joueurs réels
  // Cette fonction sera appelée pour chaque rendu donc nous la gardons simple
  const getTeamAndNameForCar = (carId: string): { team: number, name: string } => {
    // Essayer d'extraire le vrai ID du joueur à partir de l'ID de la voiture
    // L'ID de voiture peut contenir l'ID du joueur sous forme "player_X_Y" où X est l'ID du joueur
    let playerId = '';
    let team = 0;
    let name = `Joueur ${carId}`;
    
    // Essayer de trouver l'ID du joueur dans l'ID de la voiture
    if (carId.startsWith('player_')) {
      const parts = carId.split('_');
      if (parts.length >= 2) {
        playerId = parts[1];
      }
    }
    
    // Si on a trouvé un ID de joueur, chercher dans les métadonnées
    if (playerId && players[playerId]) {
      team = players[playerId].team;
      name = players[playerId].name;
    } else {
      // Si on ne trouve pas le joueur, essayer de déduire l'équipe à partir de la position
      // Regarder la position Z de la voiture dans le premier frame pour déterminer de quel côté elle est
      if (frame && frame.cars[carId]) {
        const carPosition = frame.cars[carId].position;
        // Si Z (axe avant/arrière dans RL) est négatif, c'est l'équipe bleue, sinon l'équipe orange
        team = carPosition[0] < 0 ? 0 : 1;
      }
    }
    
    return { team, name };
  };

  return (
    <>
      {/* Augmenter l'intensité de la lumière ambiante pour une meilleure visibilité */}
      <ambientLight intensity={0.8} />
      <directionalLight position={[10, 10, 10]} intensity={1.5} castShadow />
      
      <Field />
      
      {/* Render Ball */}
      <Ball 
        position={frame.ball.position} 
        rotation={frame.ball.rotation}
      />
      
      {/* Render Cars - Maintenant avec les nouvelles IDs */}
      {Object.entries(frame.cars).map(([carId, carState]) => {
        const { team, name } = getTeamAndNameForCar(carId);
        
        return (
          <Car 
            key={carId}
            position={carState.position}
            rotation={carState.rotation}
            boost={carState.boost}
            team={team}
            name={name}
          />
        );
      })}
      
      <OrbitControls 
        enableDamping 
        dampingFactor={0.05} 
        screenSpacePanning={false} 
        minDistance={1000} // Augmenter la distance minimale
        maxDistance={15000} // Augmenter la distance maximale
        maxPolarAngle={Math.PI / 2}
      />
      
      <EffectComposer>
        <Bloom luminanceThreshold={0.6} luminanceSmoothing={0.9} height={300} />
      </EffectComposer>
      
      <Environment preset="city" />
    </>
  );
}

export function ReplayScene({ replay, frames, currentFrame }: ReplaySceneProps) {
  return (
    <div className="h-[600px] w-full bg-black/95 rounded-lg overflow-hidden">
      <Canvas shadows camera={{ fov: 45, near: 0.1, far: 20000 }}>
        <Scene replay={replay} frames={frames} currentFrame={currentFrame} />
      </Canvas>
    </div>
  );
} 