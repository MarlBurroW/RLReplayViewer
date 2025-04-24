export interface Replay {
  id: string;
  duration: number;
  map_name?: string;
  game_type?: string;
  match_type?: string;
  date?: string;
  teams: Record<string, Team>;
  players: Record<string, Player>;
  timeline: TimelineEvent[];
}

export interface Frame {
  time: number;
  delta: number;
  ball: BallState;
  cars: Record<string, CarState>;
}

export interface BallState {
  position: [number, number, number];
  rotation: [number, number, number, number];
  velocity: [number, number, number];
}

export interface CarState {
  position: [number, number, number];
  rotation: [number, number, number, number];
  boost: number;
  velocity?: [number, number, number];
}

export interface Team {
  id: string;
  name: string;
  score: number;
}

export interface PlayerStats {
  score: number;
  goals: number;
  assists: number;
  saves: number;
  shots: number;
}

export interface Player {
  id: string;
  name: string;
  team: number;
  platform?: string;
  is_bot: boolean;
  stats: PlayerStats;
  platform_id?: string;
  epic_id?: string;
  steam_id?: string;
  psn_id?: string;
  xbox_id?: string;
}

export interface TimelineEvent {
  type: string;
  time: number;
  player?: string;
  team?: number;
}

export interface ProcessingStatus {
  status: "processing" | "completed" | "failed" | "metadata_only";
  progress: number;
  message?: string;
  error?: string;
}

// Types pour le format brut de rrrocket
export interface RawReplayData {
  objects: string[];
  network_frames: {
    frames: RawFrame[];
  };
}

export interface RawFrame {
  time: number;
  delta: number;
  new_actors: RawActor[];
  deleted_actors: number[];
  updated_actors: RawUpdatedActor[];
}

export interface RawActor {
  actor_id: number;
  object_id: number;
  initial_trajectory?: {
    location: {
      x: number;
      y: number;
      z: number;
    };
    rotation: {
      x: number;
      y: number;
      z: number;
      w: number;
    };
  };
}

export interface RawUpdatedActor {
  actor_id: number;
  stream_id: number;
  object_id: number;
  attribute: {
    RigidBody?: {
      sleeping: boolean;
      location: {
        x: number;
        y: number;
        z: number;
      };
      rotation: {
        x: number;
        y: number;
        z: number;
        w: number;
      };
      linear_velocity: {
        x: number;
        y: number;
        z: number;
      };
      angular_velocity: {
        x: number;
        y: number;
        z: number;
      };
    };
    Int?: number;
    Byte?: number;
    ReplicatedBoost?: {
      boost_amount: number;
    };
  };
} 