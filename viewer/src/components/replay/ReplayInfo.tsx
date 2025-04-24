import React from "react";
import { Replay } from "../../types/replay";
import { formatTime } from "../../lib/utils";

interface ReplayInfoProps {
  replay: Replay;
}

export function ReplayInfo({ replay }: ReplayInfoProps) {
  // Vérifier que les objets teams et players existent
  const hasTeams = replay.teams && Object.keys(replay.teams).length > 0;
  const hasPlayers = replay.players && Object.keys(replay.players).length > 0;

  return (
    <div className="bg-card p-4 rounded-lg border border-border mb-6">
      <h2 className="text-xl font-semibold mb-4">Replay Information</h2>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <div className="mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Map</h3>
            <p>{replay.map_name || "Unknown Map"}</p>
          </div>
          
          <div className="mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Duration</h3>
            <p>{formatTime(replay.duration)}</p>
          </div>
          
          <div className="mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Game Type</h3>
            <p>{replay.game_type || "Unknown Game Type"}</p>
          </div>
        </div>
        
        <div>
          {hasTeams && (
            <>
              <h3 className="text-sm font-medium text-muted-foreground mb-2">Teams</h3>
              <div className="space-y-2">
                {Object.values(replay.teams).map((team) => (
                  <div key={team.id} className="flex justify-between p-2 rounded bg-background">
                    <span>{team.name}</span>
                    <span className="font-bold">{team.score}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          
          {hasPlayers && (
            <>
              <h3 className="text-sm font-medium text-muted-foreground mt-4 mb-2">Players</h3>
              <div className="space-y-2">
                {Object.values(replay.players).map((player) => (
                  <div 
                    key={player.id} 
                    className="flex justify-between p-2 rounded bg-background"
                  >
                    <span className={`${player.team === 0 ? "text-blue-400" : "text-orange-400"} flex items-center`}>
                      {player.is_bot && (
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 mr-1" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect width="18" height="10" x="3" y="8" rx="2" /><path d="M12 8v10" /><path d="M17 8v10" /><path d="M7 8v10" /><path d="M17 14h4" /><path d="M7 14H3" /><path d="m12 3-1 1 1 1 1-1z" /></svg>
                      )}
                      {player.name}
                    </span>
                    <span className="font-bold">{player.stats?.score || 0}</span>
                  </div>
                ))}
              </div>
            </>
          )}
          
          {!hasTeams && !hasPlayers && (
            <div className="p-4 bg-amber-50 text-amber-700 rounded">
              Information limitée disponible pour ce replay. 
              Les données de joueurs et d'équipes ne sont pas accessibles dans ce format.
            </div>
          )}
        </div>
      </div>
    </div>
  );
} 