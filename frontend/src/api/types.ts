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

export interface DiscussionOptions {
  target_id?: string;
  presented_clue_ids?: string[];
  action_id?: string;
}

export interface CharacterInfo {
  id: string;
  name: string;
  public_identity: string;
  role_script?: string;
  objectives?: string[];
  is_killer?: boolean;
  appearance: string;
  portrait_url?: string;
  dialogue_style?: string;
}

export interface Clue {
  id: string;
  title?: string;
  content: string;
  type: 'physical' | 'testimony' | 'document';
  holder_name: string;
  is_revealed: boolean;
}

export interface ChatMessage {
  speaker: string;
  message: string;
  action_id?: string;
  kind?: string;
}

export interface Story {
  delivery?: 'bundled' | 'downloaded' | null;
  cover_url?: string;
  num_characters?: number;
  origin?: 'builtin' | 'generated' | 'imported' | 'legacy';
  version?: number;
  summary?: string;
  difficulty?: string;
  estimated_minutes?: number | null;
  author?: string;
  license?: string;
  id: string;
  title: string;
  topic: string;
  created_at: string;
}

/** 公开案情简报（不含动机/真凶等谜底字段） */
export interface CaseBrief {
  title: string;
  background: string;
  victim: string;
  crime: string;
  location: string;
  time: string;
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
  case_brief?: CaseBrief;
}

export interface LoadGameResponse {
  game_id: string;
  story_id: string;
  phase: string;
  mode?: GameMode;
  max_rounds?: number;
  player: CharacterInfo;
  characters: CharacterInfo[];
  case_brief?: CaseBrief;
}

export interface GameStatus {
  game_id: string;
  story_id: string;
  game_ended: boolean;
  winner: string | null;
  is_speaking: boolean;
  phase: GamePhase;
  mode: GameMode;
  is_quick_mode: boolean;
  round: number;
  max_rounds: number;
  progress: { current: number; total: number };
  investigation_options: InvestigationOption[];
  last_event: GameEvent | null;
  player: CharacterInfo;
  characters: CharacterInfo[];
  case_brief: CaseBrief;
  available_actions: string[];
  round_progress?: { investigated: boolean; discussed: boolean };
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
  available_actions: string[];
}

export interface InvestigateResponse {
  found: Clue[];
  clue_board: ClueBoard;
  investigation_options: InvestigationOption[];
  event: GameEvent | null;
  available_actions: string[];
}

export interface PhaseResponse {
  phase: string;
  available_actions: string[];
  round?: number;
  investigation_options?: InvestigationOption[];
  last_event?: GameEvent | null;
  round_progress?: { investigated: boolean; discussed: boolean };
}

export interface VoteResponse {
  votes: Record<string, string>;
  vote_reasons?: Record<string, string>;
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
  advice_state?: 'available' | 'running' | 'completed' | 'unavailable';
  deductions?: { conclusion: string; evidence: { clue_id: string; title: string; quote: string; discovered: boolean }[] }[];
  player_verdict?: { target: string; correct: boolean };
  votes?: { voter: string; target: string; reason: string }[];
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
