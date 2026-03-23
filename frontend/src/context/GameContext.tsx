// Game Context - Global state management for the murder mystery game

import { createContext, useContext, useReducer, useCallback, useEffect, useRef, type ReactNode } from 'react';
import { api } from '../api/client';
import type {
  CharacterInfo,
  Clue,
  ChatMessage,
  RevealInfo,
  GamePhase,
} from '../api/types';

interface GameState {
  gameId: string | null;
  storyId: string | null;
  topic: string;
  player: CharacterInfo | null;
  characters: CharacterInfo[];
  phase: GamePhase;
  round: number;
  maxRounds: number;
  clues: Clue[];
  accusationPoints: number;
  scenePublicClues: Clue[];
  discussionHistory: ChatMessage[];
  availableActions: string[];
  gameEnded: boolean;
  winner: string | null;
  revealInfo: RevealInfo | null;
  isLoading: boolean;
  error: string | null;
  currentDiscussionMessages: ChatMessage[];
}

type GameAction =
  | { type: 'SET_LOADING'; payload: boolean }
  | { type: 'SET_ERROR'; payload: string | null }
  | { type: 'GAME_CREATED'; payload: { gameId: string; storyId: string; topic: string; player: CharacterInfo; characters: CharacterInfo[]; phase: string } }
  | { type: 'SET_GAME_STATUS'; payload: Partial<GameState> }
  | { type: 'SET_PHASE'; payload: GamePhase }
  | { type: 'SET_ROUND'; payload: number }
  | { type: 'SET_CLUES'; payload: { clues: Clue[]; accusationPoints: number; scenePublicClues: Clue[] } }
  | { type: 'ADD_DISCUSSION_MESSAGES'; payload: ChatMessage[] }
  | { type: 'CLEAR_DISCUSSION_MESSAGES' }
  | { type: 'GAME_ENDED'; payload: { winner: string; revealInfo: RevealInfo } }
  | { type: 'RESET_GAME' };

const initialState: GameState = {
  gameId: null,
  storyId: null,
  topic: '',
  player: null,
  characters: [],
  phase: 'introduction',
  round: 1,
  maxRounds: 5,
  clues: [],
  accusationPoints: 1,
  scenePublicClues: [],
  discussionHistory: [],
  availableActions: [],
  gameEnded: false,
  winner: null,
  revealInfo: null,
  isLoading: false,
  error: null,
  currentDiscussionMessages: [],
};

function gameReducer(state: GameState, action: GameAction): GameState {
  switch (action.type) {
    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };
    case 'SET_ERROR':
      return { ...state, error: action.payload, isLoading: false };
    case 'GAME_CREATED':
      return {
        ...state,
        gameId: action.payload.gameId,
        storyId: action.payload.storyId,
        topic: action.payload.topic,
        player: action.payload.player,
        characters: action.payload.characters,
        phase: action.payload.phase as GamePhase,
        isLoading: false,
        error: null,
      };
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
        currentDiscussionMessages: [...state.currentDiscussionMessages, ...action.payload],
      };
    case 'CLEAR_DISCUSSION_MESSAGES':
      return { ...state, currentDiscussionMessages: [] };
    case 'GAME_ENDED':
      return {
        ...state,
        gameEnded: true,
        winner: action.payload.winner,
        revealInfo: action.payload.revealInfo,
      };
    case 'RESET_GAME':
      return initialState;
    default:
      return state;
  }
}

interface GameContextValue {
  state: GameState;
  createGame: (topic: string, playerName?: string) => Promise<void>;
  loadGame: (storyId: string) => Promise<void>;
  refreshStatus: () => Promise<void>;
  refreshClues: () => Promise<void>;
  introduce: (message?: string) => Promise<void>;
  nextPhase: () => Promise<void>;
  startVoting: () => Promise<void>;
  speak: (message: string) => Promise<void>;
  vote: (characterName: string) => Promise<void>;
  accuse: (characterName: string) => Promise<void>;
  resetGame: () => void;
}

const GameContext = createContext<GameContextValue | null>(null);

export function GameProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const pollingIntervalRef = useRef<number | null>(null);

  const clearPolling = useCallback(() => {
    if (pollingIntervalRef.current) {
      clearInterval(pollingIntervalRef.current);
      pollingIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => clearPolling();
  }, [clearPolling]);

  const createGame = useCallback(async (topic: string, playerName?: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const response = await api.createGame(topic, playerName);
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: response.topic,
          player: response.player,
          characters: response.characters,
          phase: response.phase,
        },
      });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to create game' });
    }
  }, []);

  const loadGame = useCallback(async (storyId: string) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const response = await api.loadGame(storyId);
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: '',
          player: response.player,
          characters: response.characters,
          phase: response.phase,
        },
      });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to load game' });
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const status = await api.getGameStatus(state.gameId);
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          phase: status.phase as GamePhase,
          round: status.round,
          maxRounds: status.max_rounds,
          availableActions: status.available_actions,
          player: status.player,
          characters: status.characters,
        },
      });
    } catch (error) {
      console.error('Failed to refresh status:', error);
    }
  }, [state.gameId]);

  const refreshClues = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const clueBoard = await api.getClues(state.gameId);
      dispatch({
        type: 'SET_CLUES',
        payload: {
          clues: clueBoard.clues,
          accusationPoints: clueBoard.accusation_points,
          scenePublicClues: clueBoard.scene_public_clues,
        },
      });
    } catch (error) {
      console.error('Failed to refresh clues:', error);
    }
  }, [state.gameId]);

  const introduce = useCallback(async (message?: string) => {
    if (!state.gameId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      await api.introduce(state.gameId, message);
      dispatch({ type: 'SET_PHASE', payload: 'investigation' });
      dispatch({ type: 'SET_LOADING', payload: false });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to introduce' });
    }
  }, [state.gameId]);

  const nextPhase = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const result = await api.nextPhase(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      if (result.round !== undefined) {
        dispatch({ type: 'SET_ROUND', payload: result.round });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to advance phase' });
    }
  }, [state.gameId]);

  const startVoting = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const result = await api.startVoting(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      if (result.round !== undefined) {
        dispatch({ type: 'SET_ROUND', payload: result.round });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to start voting' });
    }
  }, [state.gameId]);

  const returnToInvestigation = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const result = await api.returnToInvestigation(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({ type: 'SET_ROUND', payload: result.round || 1 });
      dispatch({ type: 'CLEAR_DISCUSSION_MESSAGES' });
      // 刷新线索
      await refreshClues();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to return to investigation' });
    }
  }, [state.gameId, refreshClues]);

  const speak = useCallback(async (message: string) => {
    if (!state.gameId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const result = await api.speak(state.gameId, message);
      dispatch({ type: 'ADD_DISCUSSION_MESSAGES', payload: result.messages });
      dispatch({ type: 'SET_LOADING', payload: false });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to speak' });
    }
  }, [state.gameId]);

  const vote = useCallback(async (characterName: string) => {
    if (!state.gameId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const result = await api.vote(state.gameId, characterName);
      if (result.game_ended) {
        const reveal = await api.getReveal(state.gameId);
        dispatch({
          type: 'GAME_ENDED',
          payload: { winner: result.winner || 'unknown', revealInfo: reveal },
        });
      }
      return result;
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to vote' });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId]);

  const accuse = useCallback(async (characterName: string) => {
    if (!state.gameId) return;
    dispatch({ type: 'SET_LOADING', payload: true });
    try {
      const result = await api.accuse(state.gameId, characterName);
      if (result.game_ended && result.reveal) {
        dispatch({
          type: 'GAME_ENDED',
          payload: { winner: result.winner || 'unknown', revealInfo: result.reveal },
        });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: error instanceof Error ? error.message : 'Failed to accuse' });
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId]);

  const resetGame = useCallback(() => {
    clearPolling();
    dispatch({ type: 'RESET_GAME' });
  }, [clearPolling]);

  return (
    <GameContext.Provider
      value={{
        state,
        createGame,
        loadGame,
        refreshStatus,
        refreshClues,
        introduce,
        nextPhase,
        startVoting,
        returnToInvestigation,
        speak,
        vote,
        accuse,
        resetGame,
      }}
    >
      {children}
    </GameContext.Provider>
  );
}

export function useGame() {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
}
