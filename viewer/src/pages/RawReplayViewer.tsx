import { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Button } from "../components/ui/button";
import { Slider } from "../components/ui/slider";
import { ReplayParser } from "../utils/ReplayParser";

interface Player {
  id: string;
  name: string;
  team: number;
}

interface Car {
  id: string;
  player_id: string;
  position: [number, number, number];
  rotation: [number, number, number];
  velocity: [number, number, number];
  angular_velocity: [number, number, number];
  boost: number;
  player_name?: string;
  team?: number;
}

interface Ball {
  position: [number, number, number];
  rotation: [number, number, number];
  velocity: [number, number, number];
  angular_velocity: [number, number, number];
}

interface Frame {
  time: number;
  cars: Car[];
  ball: Ball;
}

interface ReplayData {
  metadata: {
    id: string;
    mapName: string;
    matchType: string;
    teamSize: number;
    duration: number;
    date: string;
    players: Player[];
  };
  frames: Frame[];
}

export default function RawReplayViewer() {
  const { replayId } = useParams<{ replayId: string }>();
  const [replayData, setReplayData] = useState<ReplayData | null>(null);
  const [rawReplayData, setRawReplayData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [processingData, setProcessingData] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentFrameIndex, setCurrentFrameIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        // Charger les données brutes du replay avec le nouvel endpoint /raw
        const response = await fetch(`/api/replays/${replayId}/raw`);
        
        if (!response.ok) {
          throw new Error(`Erreur HTTP: ${response.status}`);
        }
        
        const rawData = await response.json();
        setRawReplayData(rawData);
        
        // Traiter les données avec notre parser
        setProcessingData(true);
        const parser = new ReplayParser();
        const processedData = await parser.processReplay(rawData, () => {});
        
        setReplayData(processedData);
      } catch (err) {
        console.error("Erreur:", err);
        setError(err instanceof Error ? err.message : 'Une erreur est survenue');
      } finally {
        setLoading(false);
        setProcessingData(false);
      }
    };

    fetchData();
  }, [replayId]);

  useEffect(() => {
    let interval: number | null = null;
    
    if (isPlaying && replayData?.frames.length) {
      interval = window.setInterval(() => {
        setCurrentFrameIndex((prevIndex) => {
          if (prevIndex >= replayData.frames.length - 1) {
            setIsPlaying(false);
            return prevIndex;
          }
          return prevIndex + 1;
        });
      }, 1000 / 30 / playbackSpeed); // Assume 30 FPS
    }
    
    return () => {
      if (interval) window.clearInterval(interval);
    };
  }, [isPlaying, replayData, playbackSpeed]);

  const handleSliderChange = (values: number[]) => {
    if (values.length > 0) {
      setCurrentFrameIndex(values[0]);
    }
  };

  const togglePlayback = () => {
    if (currentFrameIndex >= (replayData?.frames.length || 0) - 1) {
      setCurrentFrameIndex(0);
    }
    setIsPlaying(!isPlaying);
  };

  if (loading) return <div className="flex items-center justify-center h-96">Chargement des données...</div>;
  if (processingData) return <div className="flex items-center justify-center h-96">Traitement des données...</div>;
  if (error) return <div className="bg-red-50 text-red-500 p-4 rounded-md">Erreur: {error}</div>;
  if (!replayData) return <div className="bg-amber-50 text-amber-500 p-4 rounded-md">Aucune donnée disponible</div>;

  const currentFrame = replayData.frames[currentFrameIndex];
  const totalFrames = replayData.frames.length;

  return (
    <div className="space-y-6 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Visualiseur de Replay (données brutes)</h1>
        <div className="flex items-center space-x-2">
          <Button
            onClick={togglePlayback}
            variant="default"
          >
            {isPlaying ? 'Pause' : 'Lecture'}
          </Button>
          <div className="flex items-center space-x-2">
            <span className="text-sm text-muted-foreground">Vitesse:</span>
            <select
              value={playbackSpeed}
              onChange={(e) => setPlaybackSpeed(Number(e.target.value))}
              className="p-1 bg-background border border-input rounded-md text-sm"
            >
              <option value={0.5}>0.5x</option>
              <option value={1}>1x</option>
              <option value={2}>2x</option>
              <option value={4}>4x</option>
            </select>
          </div>
        </div>
      </div>

      <div className="bg-card p-4 rounded-md border border-border">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm text-muted-foreground">
            Frame: {currentFrameIndex + 1} / {totalFrames}
          </span>
          <span className="text-sm text-muted-foreground">
            Temps: {currentFrame.time.toFixed(2)}s
          </span>
        </div>
        <Slider
          min={0}
          max={totalFrames - 1}
          step={1}
          value={[currentFrameIndex]}
          onValueChange={handleSliderChange}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-card p-4 rounded-md border border-border">
          <h2 className="text-lg font-semibold mb-4">Voitures</h2>
          <div className="space-y-4 max-h-[500px] overflow-y-auto">
            {currentFrame.cars.map((car) => (
              <div key={car.id} className="p-3 bg-background rounded-md border border-border">
                <div className="flex justify-between mb-2">
                  <span className="font-medium">ID: {car.id}</span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${car.team === 0 ? 'bg-blue-100 text-blue-800' : 'bg-orange-100 text-orange-800'}`}>
                    Équipe {car.team === 0 ? 'Bleue' : 'Orange'}
                  </span>
                </div>
                <p><span className="text-muted-foreground">Joueur:</span> {car.player_name || 'Inconnu'}</p>
                <p><span className="text-muted-foreground">Position:</span> [{car.position.map(p => p.toFixed(2)).join(', ')}]</p>
                <p><span className="text-muted-foreground">Rotation:</span> [{car.rotation.map(r => r.toFixed(2)).join(', ')}]</p>
                <p><span className="text-muted-foreground">Vitesse:</span> [{car.velocity.map(v => v.toFixed(2)).join(', ')}]</p>
                <p><span className="text-muted-foreground">Boost:</span> {car.boost.toFixed(0)}%</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="bg-card p-4 rounded-md border border-border mb-6">
            <h2 className="text-lg font-semibold mb-4">Balle</h2>
            <div className="p-3 bg-background rounded-md border border-border">
              <p><span className="text-muted-foreground">Position:</span> [{currentFrame.ball.position.map(p => p.toFixed(2)).join(', ')}]</p>
              <p><span className="text-muted-foreground">Rotation:</span> [{currentFrame.ball.rotation.map(r => r.toFixed(2)).join(', ')}]</p>
              <p><span className="text-muted-foreground">Vitesse:</span> [{currentFrame.ball.velocity.map(v => v.toFixed(2)).join(', ')}]</p>
              <p><span className="text-muted-foreground">Vitesse angulaire:</span> [{currentFrame.ball.angular_velocity.map(v => v.toFixed(2)).join(', ')}]</p>
            </div>
          </div>
          
          <div className="bg-card p-4 rounded-md border border-border">
            <h2 className="text-lg font-semibold mb-4">Joueurs</h2>
            <div className="space-y-2 max-h-[250px] overflow-y-auto">
              {replayData.metadata.players.map((player) => (
                <div key={player.id} className="p-3 bg-background rounded-md border border-border">
                  <div className="flex justify-between">
                    <span className="font-medium">{player.name}</span>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${player.team === 0 ? 'bg-blue-100 text-blue-800' : 'bg-orange-100 text-orange-800'}`}>
                      Équipe {player.team === 0 ? 'Bleue' : 'Orange'}
                    </span>
                  </div>
                  <p className="text-sm text-muted-foreground">ID: {player.id}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 