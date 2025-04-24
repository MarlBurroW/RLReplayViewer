import React, { useState, useEffect, useRef, useCallback } from "react";
import { useParams } from "react-router-dom";
import { ReplayScene } from "../components/replay/ReplayScene";
import { ReplayControls } from "../components/replay/ReplayControls";
import { ReplayInfo } from "../components/replay/ReplayInfo";
import { Frame, Replay } from "../types/replay";
import { getReplayFrames, getReplayMetadata } from "../services/api";
import { Button } from "../components/ui/button";

export default function ReplayViewer() {
  const { replayId } = useParams<{ replayId: string }>();
  const [replay, setReplay] = useState<Replay | null>(null);
  const [frames, setFrames] = useState<Frame[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  
  // Référence à l'intervalle d'animation
  const animationIntervalRef = useRef<number | null>(null);
  // Référence à la frame courante pour l'animation
  const currentFrameRef = useRef<number>(0);
  
  // Garder la référence à jour avec l'état
  useEffect(() => {
    currentFrameRef.current = currentFrame;
  }, [currentFrame]);

  // Fonction pour charger les métadonnées et les frames du replay
  const loadReplayData = useCallback(async () => {
    if (!replayId) return;
    
    try {
      setIsLoading(true);
      setError(null);
      
      // Récupération des métadonnées
      const replayData = await getReplayMetadata(replayId);
      setReplay(replayData);
      
      // Récupération et précompilation des frames
      console.log("Chargement des frames...");
      const framesData = await getReplayFrames(replayId);
      setFrames(framesData);
      console.log(`${framesData.length} frames chargées`);
    } catch (err) {
      console.error("Error loading replay data:", err);
      setError(err instanceof Error ? err.message : "Failed to load replay data");
    } finally {
      setIsLoading(false);
    }
  }, [replayId]);

  // Charger les données au chargement de la page
  useEffect(() => {
    loadReplayData();
    
    // Nettoyer les intervalles au démontage
    return () => {
      if (animationIntervalRef.current !== null) {
        clearInterval(animationIntervalRef.current);
      }
    };
  }, [loadReplayData]);

  // Gérer l'animation avec un simple setInterval
  useEffect(() => {
    const stopAnimation = () => {
      if (animationIntervalRef.current !== null) {
        clearInterval(animationIntervalRef.current);
        animationIntervalRef.current = null;
        console.log("Animation arrêtée");
      }
    };
    
    const startAnimation = () => {
      stopAnimation(); // Arrêter toute animation existante
      
      // Calculer l'intervalle en fonction de la vitesse
      const intervalTime = Math.max(10, Math.round(33 / playbackSpeed)); // Min 10ms, max ~30fps
      
      console.log(`Démarrage de l'animation avec intervalle de ${intervalTime}ms, vitesse x${playbackSpeed}`);
      
      animationIntervalRef.current = window.setInterval(() => {
        // Utiliser la référence pour accéder à la frame courante
        const currentFrameValue = currentFrameRef.current;
        
        // Ne pas continuer si on est à la fin
        if (currentFrameValue >= frames.length - 1) {
          console.log("Fin de l'animation atteinte");
          stopAnimation();
          setIsPlaying(false);
          return;
        }
        
        // Avancer à la frame suivante
        const nextFrame = currentFrameValue + 1;
        const nextTime = frames[nextFrame]?.time || 0;
        
        // Log moins fréquent pour éviter de surcharger la console
        if (nextFrame % 30 === 0) {
          console.log(`Animation en cours: frame ${nextFrame}/${frames.length}, temps: ${nextTime.toFixed(2)}`);
        }
        
        // Mettre à jour l'état (cela mettra aussi à jour currentFrameRef via l'effet)
        setCurrentFrame(nextFrame);
        setCurrentTime(nextTime);
      }, intervalTime);
    };
    
    // Démarrer ou arrêter l'animation selon l'état de lecture
    if (isPlaying && frames.length > 0) {
      startAnimation();
    } else {
      stopAnimation();
    }
    
    // Nettoyer au démontage ou lorsque les dépendances changent
    return () => {
      stopAnimation();
    };
  }, [isPlaying, frames, playbackSpeed]); // Ne plus dépendre de currentFrame
  
  // Fonctions de contrôle de lecture
  const handlePlay = useCallback(() => {
    console.log("Play pressed, starting from frame", currentFrame);
    setIsPlaying(true);
  }, [currentFrame]);
  
  const handlePause = useCallback(() => {
    console.log("Pause pressed");
    setIsPlaying(false);
  }, []);
  
  const handleSeek = useCallback((time: number) => {
    // Arrêter la lecture pendant la recherche
    setIsPlaying(false);
    setCurrentTime(time);
    
    // Trouver la frame correspondant au temps spécifié
    let frameIndex = 0;
    
    // Recherche binaire pour trouver la frame plus efficacement
    let left = 0;
    let right = frames.length - 1;
    
    while (left <= right) {
      const mid = Math.floor((left + right) / 2);
      
      if (frames[mid].time <= time && (mid === frames.length - 1 || frames[mid + 1].time > time)) {
        frameIndex = mid;
        break;
      } else if (frames[mid].time > time) {
        right = mid - 1;
      } else {
        left = mid + 1;
      }
    }
    
    console.log(`Seek à ${time}s, frame: ${frameIndex}`);
    setCurrentFrame(frameIndex);
  }, [frames]);
  
  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary mb-4"></div>
        <p className="text-muted-foreground">Chargement des données du replay...</p>
      </div>
    );
  }
  
  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px]">
        <div className="text-destructive text-xl mb-4">Erreur</div>
        <p className="text-muted-foreground mb-4">{error}</p>
        <Button onClick={loadReplayData}>Réessayer</Button>
      </div>
    );
  }
  
  if (!replay || frames.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-[600px]">
        <p className="text-muted-foreground">Aucune donnée de replay disponible</p>
      </div>
    );
  }
  
  return (
    <div className="space-y-6">
      <ReplayInfo replay={replay} />
      
      <ReplayScene 
        replay={replay} 
        frames={frames} 
        currentFrame={currentFrame} 
      />
      
      <ReplayControls 
        replay={replay}
        isPlaying={isPlaying}
        currentTime={currentTime}
        currentFrame={currentFrame}
        totalFrames={frames.length}
        onPlay={handlePlay}
        onPause={handlePause}
        onSeek={handleSeek}
        playbackSpeed={playbackSpeed}
        onSpeedChange={setPlaybackSpeed}
      />
    </div>
  );
} 