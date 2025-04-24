import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "../components/ui/button";

export default function HomePage() {
  const [replayId, setReplayId] = useState("");
  const navigate = useNavigate();
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (replayId.trim()) {
      navigate(`/replay/${replayId.trim()}`);
    }
  };
  
  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      <div className="w-full max-w-md bg-card p-8 rounded-lg border border-border">
        <h1 className="text-2xl font-bold mb-6 text-center">Rocket League Replay Viewer</h1>
        
        <p className="mb-6 text-muted-foreground text-center">
          Enter a replay ID to view it
        </p>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="replayId" className="block text-sm font-medium mb-1">
              Replay ID
            </label>
            <input
              id="replayId"
              type="text"
              value={replayId}
              onChange={(e) => setReplayId(e.target.value)}
              className="w-full p-2 rounded-md border border-input bg-background"
              placeholder="Enter the replay ID"
              required
            />
          </div>
          
          <Button type="submit" className="w-full">
            View Replay
          </Button>
        </form>
        
        <div className="mt-8 text-sm text-muted-foreground">
          <p className="text-center">
            You can find the replay ID in the URL after uploading a replay file.
          </p>
        </div>
      </div>
    </div>
  );
} 