import { createContext } from 'react';
import type {
  AccuseResponse,
  CaseBrief,
  CharacterInfo,
  ChatMessage,
  Clue,
  GamePhase,
  GameEvent,
  GameMode,
  InvestigationOption,
  RevealInfo,
  VoteResponse,
} from '../api/types';

export interface GameState {
  gameId: string | null;
  storyId: string | null;
  topic: string;
  caseBrief: CaseBrief | null;
  player: CharacterInfo | null;
  characters: CharacterInfo[];
  phase: GamePhase;
  mode: GameMode;
  round: number;
  maxRounds: number;
  investigationOptions: InvestigationOption[];
  lastEvent: GameEvent | null;
  clues: Clue[];
  accusationPoints: number;
  scenePublicClues: Clue[];
  discussionHistory: ChatMessage[];
  availableActions: string[];
  gameEnded: boolean;
  winner: string | null;
  revealInfo: RevealInfo | null;
  isLoading: boolean;
  isSpeaking: boolean;
  connectionLost: boolean;
  error: string | null;
  currentDiscussionMessages: ChatMessage[];
  introductions: ChatMessage[];
}

export interface GameContextValue {
  state: GameState;
  createGame: (topic: string, playerName?: string, mode?: GameMode) => Promise<string>;
  loadGame: (storyId: string, mode?: GameMode) => Promise<string>;
  resumeGame: (gameId: string) => Promise<void>;
  refreshStatus: () => Promise<boolean>;
  refreshClues: () => Promise<boolean>;
  refreshDiscussionHistory: () => Promise<boolean>;
  setConnectionLost: (lost: boolean) => void;
  introduce: (message?: string) => Promise<void>;
  nextPhase: () => Promise<void>;
  startVoting: () => Promise<void>;
  returnToInvestigation: () => Promise<void>;
  investigate: (leadId?: string) => Promise<Clue[]>;
  speak: (message: string) => Promise<void>;
  vote: (characterName: string) => Promise<VoteResponse>;
  accuse: (characterName: string) => Promise<AccuseResponse>;
  loadReveal: () => Promise<void>;
  resetGame: () => void;
}

export const GameContext = createContext<GameContextValue | null>(null);
