import React from "react";
import { Button } from "../ui/button";
import { formatTime } from "../../lib/utils";
import { Replay } from "../../types/replay";

interface ReplayControlsProps {
  replay: Replay;
  isPlaying: boolean;
  currentTime: number;
  currentFrame: number;
  totalFrames: number;
  onPlay: () => void;
  onPause: () => void;
  onSeek: (time: number) => void;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
}

export function ReplayControls({
  replay,
  isPlaying,
  currentTime,
  currentFrame,
  totalFrames,
  onPlay,
  onPause,
  onSeek,
  playbackSpeed,
  onSpeedChange,
}: ReplayControlsProps) {
  
  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    onSeek(value);
  };
  
  const playPauseIcon = isPlaying ? (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-pause"><rect x="6" y="4" width="4" height="16" /><rect x="14" y="4" width="4" height="16" /></svg>
  ) : (
    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-play"><polygon points="5 3 19 12 5 21 5 3" /></svg>
  );
  
  return (
    <div className="bg-card p-4 rounded-lg border border-border">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-sm text-muted-foreground">
          {formatTime(currentTime)} / {formatTime(replay.duration)}
        </div>
        <div className="text-sm text-muted-foreground">
          Frame: {currentFrame + 1} / {totalFrames}
        </div>
      </div>
      
      <div className="mb-6">
        <input
          type="range"
          min={0}
          max={replay.duration}
          step={0.01}
          value={currentTime}
          onChange={handleSliderChange}
          className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
        />
      </div>
      
      <div className="flex justify-between items-center">
        <div className="flex gap-2">
          <Button
            onClick={isPlaying ? onPause : onPlay}
            variant="default"
            size="icon"
            className="h-10 w-10"
          >
            {playPauseIcon}
          </Button>
          
          <Button
            onClick={() => onSeek(0)}
            variant="outline"
            size="icon"
            className="h-10 w-10"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="lucide lucide-skip-back"><polygon points="19 20 9 12 19 4 19 20" /><line x1="5" x2="5" y1="19" y2="5" /></svg>
          </Button>
        </div>
        
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Speed:</span>
          <select 
            value={playbackSpeed} 
            onChange={(e) => onSpeedChange(parseFloat(e.target.value))}
            className="bg-secondary text-foreground rounded px-2 py-1 text-sm"
          >
            <option value="0.25">0.25x</option>
            <option value="0.5">0.5x</option>
            <option value="1">1x</option>
            <option value="2">2x</option>
            <option value="4">4x</option>
          </select>
        </div>
      </div>
    </div>
  );
} 