import type { CaseBrief, CharacterInfo, ChatMessage, Clue, ClueBoard, GamePhase, GameMode, GameStatus, RevealInfo } from '../api/types';
import type { GameState } from './game-context';

export type GameAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_SPEAKING'; payload: boolean }
  | { type: 'SET_CONNECTION_LOST'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | {
      type: 'GAME_CREATED';
      payload: {
        gameId: string;
        storyId: string;
        topic: string;
        caseBrief?: CaseBrief | null;
        player: CharacterInfo;
        characters: CharacterInfo[];
        phase: string;
        mode?: GameMode;
        maxRounds?: number;
      };
    }
  | {
      type: 'GAME_RESUMED';
      payload: {
        gameId: string;
        status: GameStatus;
        clueBoard: ClueBoard;
        history: ChatMessage[];
      };
    }
  | { type: 'SET_GAME_STATUS'; payload: Partial<GameState> }
  | { type: 'SET_PHASE'; payload: GamePhase }
  | { type: 'SET_ROUND'; payload: number }
  | { type: 'SET_CLUES'; payload: { clues: Clue[]; accusationPoints: number; scenePublicClues: Clue[] } }
  | { type: 'ADD_DISCUSSION_MESSAGES'; payload: ChatMessage[] }
  | { type: 'SET_DISCUSSION_HISTORY'; payload: ChatMessage[] }
  | { type: 'SET_INTRODUCTIONS'; payload: ChatMessage[] }
  | { type: 'SET_REVEAL_INFO'; payload: RevealInfo }
  | { type: 'GAME_ENDED'; payload: { winner: string; revealInfo: RevealInfo | null } }
  | { type: 'RESET_GAME' };

export const initialState: GameState = {
  gameId: null,
  storyId: null,
  topic: '',
  caseBrief: null,
  player: null,
  characters: [],
  phase: 'introduction',
  mode: 'classic',
  round: 1,
  maxRounds: 5,
  investigationOptions: [],
  lastEvent: null,
  clues: [],
  accusationPoints: 1,
  scenePublicClues: [],
  discussionHistory: [],
  availableActions: [],
  gameEnded: false,
  winner: null,
  revealInfo: null,
  isLoading: false,
  isSpeaking: false,
  connectionLost: false,
  error: null,
  currentDiscussionMessages: [],
  introductions: [],
};

export function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_SPEAKING':
      return { ...state, isSpeaking: action.payload };
    case 'SET_CONNECTION_LOST':
      return { ...state, connectionLost: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload };
    case 'GAME_CREATED':
      return {
        ...initialState,
        gameId: action.payload.gameId,
        storyId: action.payload.storyId,
        topic: action.payload.topic,
        caseBrief: action.payload.caseBrief ?? null,
        player: action.payload.player,
        characters: action.payload.characters,
        phase: action.payload.phase as GamePhase,
        mode: action.payload.mode ?? 'classic',
        maxRounds: action.payload.maxRounds ?? 5,
        investigationOptions: [],
        lastEvent: null,
      };
    case 'GAME_RESUMED': {
      const { gameId, status, clueBoard, history } = action.payload;
      return {
        ...initialState,
        gameId,
        storyId: status.story_id,
        gameEnded: status.game_ended,
        winner: status.winner,
        isSpeaking: status.is_speaking,
        introductions: status.phase === 'introduction' ? history : [],
        caseBrief: status.case_brief ?? null,
        player: status.player,
        characters: status.characters,
        phase: status.phase,
        mode: status.mode,
        round: status.round,
        maxRounds: status.max_rounds,
        investigationOptions: status.investigation_options,
        lastEvent: status.last_event,
        availableActions: status.available_actions,
        roundProgress: status.round_progress,
        clues: clueBoard.clues,
        accusationPoints: clueBoard.accusation_points,
        scenePublicClues: clueBoard.scene_public_clues,
        currentDiscussionMessages: history,
        isLoading: false,
        connectionLost: false,
        error: null,
      };
    }
    case 'SET_GAME_STATUS':
      return { ...state, ...action.payload };
    case 'SET_PHASE':
      return { ...state, phase: action.payload };
    case 'SET_ROUND':
      return { ...state, round: action.payload };
    case 'SET_CLUES':
      return {
        ...state,
        clues: action.payload.clues,
        accusationPoints: action.payload.accusationPoints,
        scenePublicClues: action.payload.scenePublicClues,
      };
    case 'ADD_DISCUSSION_MESSAGES':
      return {
        ...state,
        currentDiscussionMessages: [
          ...state.currentDiscussionMessages,
          ...action.payload,
        ],
      };
    case 'SET_DISCUSSION_HISTORY':
      return { ...state, currentDiscussionMessages: action.payload };
    case 'SET_INTRODUCTIONS':
      return { ...state, introductions: action.payload };
    case 'SET_REVEAL_INFO':
      return { ...state, phase: 'reveal', gameEnded: true, winner: action.payload.winner, revealInfo: action.payload };
    case 'GAME_ENDED':
      // 游戏结束必然进入揭晓阶段（后端契约曾被投票分支破坏，这里双保险）
      return {
        ...state,
        phase: 'reveal',
        gameEnded: true,
        winner: action.payload.winner,
        revealInfo: action.payload.revealInfo,
        isLoading: false,
      };
    case 'RESET_GAME':
      return initialState;
    default:
      return state;
  }
}
