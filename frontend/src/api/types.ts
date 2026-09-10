// API types for the murder mystery game

export type GamePhase = 'introduction' | 'investigation' | 'discussion' | 'voting' | 'reveal';
export type GameMode = 'classic' | 'quick';

export interface InvestigationOption {
  id: string;
  title: string;
  description: string;
  kind: string;
}

export interface GameEvent {
  type: string;
  title: string;
  message: string;
  clue_id?: string;
}

export interface CharacterInfo {
  id: string;
  name: string;
  public_identity: string;
  is_killer?: boolean;
  appearance: string;
  portrait_url?: string;
  dialogue_style?: string;
}

export interface Clue {
  id: string;
  content: string;
  type: 'physical' | 'testimony' | 'document';
  holder_name: string;
  is_revealed: boolean;
}

export interface ChatMessage {
  speaker: string;
  message: string;
}

export interface Story {
  id: string;
  title: string;
  topic: string;
  created_at: string;
}

export interface CreateGameResponse {
  game_id: string;
  story_id: string;
  topic: string;
  phase: string;
  mode?: GameMode;
  max_rounds?: number;
  player: CharacterInfo;
  characters: CharacterInfo[];
}

export interface LoadGameResponse {
  game_id: string;
  story_id: string;
  phase: string;
  mode?: GameMode;
  max_rounds?: number;
  player: CharacterInfo;
  characters: CharacterInfo[];
}

export interface GameStatus {
  game_id: string;
  phase: GamePhase;
  mode: GameMode;
  is_quick_mode: boolean;
  round: number;
  max_rounds: number;
  progress: { current: number; total: number };
  investigation_count?: number;
  investigation_actions_remaining?: number | null;
  investigation_options: InvestigationOption[];
  last_event: GameEvent | null;
  player: CharacterInfo;
  characters: CharacterInfo[];
  available_actions: string[];
}

export interface ClueBoard {
  clues: Clue[];
  accusation_points: number;
  scene_public_clues: Clue[];
}

export interface IntroductionResponse {
  player_introduction: string;
  ai_introductions: ChatMessage[];
  new_phase: string;
}

export interface SpeakResponse {
  messages: ChatMessage[];
  phase: string;
}

export interface InvestigateResponse {
  found: Clue[];
  clue_board: ClueBoard;
  investigation_options: InvestigationOption[];
  investigation_actions_remaining?: number | null;
  event: GameEvent | null;
}

export interface PhaseResponse {
  phase: string;
  round?: number;
  investigation_actions_remaining?: number | null;
  investigation_options?: InvestigationOption[];
  last_event?: GameEvent | null;
}

export interface VoteResponse {
  votes: Record<string, string>;
  result: string;
  game_ended: boolean;
  winner: string | null;
  phase: string;
  all_submitted: boolean;
  reveal?: RevealInfo;
}

export interface AccuseResponse {
  correct: boolean;
  message: string;
  game_ended: boolean;
  winner: string | null;
  reveal?: RevealInfo;
}

export interface RevealInfo {
  story_content: string;
  winner: string;
  case_info: {
    title: string;
    background: string;
    victim: string;
    crime: string;
    motive: string;
    true_killer: string;
    true_killer_name?: string;
  };
}
