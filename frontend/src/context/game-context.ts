import { createContext } from 'react';
import type {
  AccuseResponse,
  CharacterInfo,
  ChatMessage,
  Clue,
  GamePhase,
  GameEvent,
  GameMode,
  InvestigationOption,
  RevealInfo,
  VoteResponse,
  FinalDeduction,
} from '../api/types';

export interface GameState {
  gameId: string | null;
  storyId: string | null;
  topic: string;
  player: CharacterInfo | null;
  characters: CharacterInfo[];
  phase: GamePhase;
  mode: GameMode;
  round: number;
  maxRounds: number;
  investigationActionsRemaining: number | null;
  investigationOptions: InvestigationOption[];
  lastEvent: GameEvent | null;
  clues: Clue[];
  accusationPoints: number;
  scenePublicClues: Clue[];
  discussionHistory: ChatMessage[];
  availableActions: string[];
  finalDeduction: FinalDeduction | null;
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
  returnToDiscussion: () => Promise<void>;
  investigate: (leadId?: string) => Promise<Clue[]>;
  speak: (message: string) => Promise<void>;
  vote: (characterName: string) => Promise<VoteResponse>;
  submitDeduction: (
    targetId: string,
    evidenceIds: string[],
    reason: string,
  ) => Promise<FinalDeduction>;
  accuse: (characterName: string) => Promise<AccuseResponse>;
  loadReveal: () => Promise<void>;
  resetGame: () => void;
}

export const GameContext = createContext<GameContextValue | null>(null);
