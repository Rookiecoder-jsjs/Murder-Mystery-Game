// Game Context — 全局状态管理
// 约定：除 speak 外的动作失败时设置 state.error 并向外抛出，由调用方决定提示方式；
// speak 的失败在服务端已有讨论历史兜底，内部完成重同步与提示。

import {
  useCallback,
  useRef,
  useReducer,
  type ReactNode,
} from 'react';
import { api, ApiError } from '../api/client';
import { useToast } from '../components/common';
import type {
  AccuseResponse,
  CharacterInfo,
  ChatMessage,
  Clue,
  ClueBoard,
  GamePhase,
  GameMode,
  GameStatus,
  RevealInfo,
  VoteResponse,
} from '../api/types';
import { GameContext, type GameState } from './game-context';

type GameAction =
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

const initialState: GameState = {
  gameId: null,
  storyId: null,
  topic: '',
  player: null,
  characters: [],
  phase: 'introduction',
  mode: 'classic',
  round: 1,
  maxRounds: 5,
  investigationActionsRemaining: null,
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

function gameReducer(state: GameState, action: GameAction): GameState {
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
        ...state,
        gameId,
        player: status.player,
        characters: status.characters,
        phase: status.phase,
        mode: status.mode,
        round: status.round,
        maxRounds: status.max_rounds,
        investigationActionsRemaining: status.investigation_actions_remaining ?? null,
        investigationOptions: status.investigation_options,
        lastEvent: status.last_event,
        availableActions: status.available_actions,
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
      return { ...state, revealInfo: action.payload };
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

function errMsg(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请重试';
}

export function GameProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const { notify } = useToast();
  const speakAbortRef = useRef<AbortController | null>(null);

  // 返回新建的 gameId，由页面负责导航到 /game/:gameId
  const createGame = useCallback(async (topic: string, playerName?: string, mode: GameMode = 'classic') => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const response = await api.createGame(topic, playerName, mode);
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: response.topic,
          player: response.player,
          characters: response.characters,
          phase: response.phase,
          mode: response.mode,
          maxRounds: response.max_rounds,
        },
      });
      return response.game_id;
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  const loadGame = useCallback(async (storyId: string, mode: GameMode = 'classic') => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const response = await api.loadGame(storyId, mode);
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: '',
          player: response.player,
          characters: response.characters,
          phase: response.phase,
          mode: response.mode,
          maxRounds: response.max_rounds,
        },
      });
      return response.game_id;
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // 刷新/刷新页面后按 URL 中的 id 续局
  const resumeGame = useCallback(async (gameId: string) => {
    speakAbortRef.current?.abort();
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const [status, clueBoard, historyResp] = await Promise.all([
        api.getGameStatus(gameId),
        api.getClues(gameId),
        api.getDiscussionHistory(gameId),
      ]);
      dispatch({
        type: 'GAME_RESUMED',
        payload: { gameId, status, clueBoard, history: historyResp.history },
      });
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, []);

  // 轮询友好的刷新：成功/失败用布尔值表达，不吞错也不弹错
  const refreshStatus = useCallback(async (): Promise<boolean> => {
    if (!state.gameId) return false;
    try {
      const status = await api.getGameStatus(state.gameId);
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          phase: status.phase,
          mode: status.mode,
          round: status.round,
          maxRounds: status.max_rounds,
          investigationActionsRemaining: status.investigation_actions_remaining ?? null,
          investigationOptions: status.investigation_options,
          lastEvent: status.last_event,
          availableActions: status.available_actions,
          player: status.player,
          characters: status.characters,
          connectionLost: false,
        },
      });
      return true;
    } catch {
      return false;
    }
  }, [state.gameId]);

  const refreshClues = useCallback(async (): Promise<boolean> => {
    if (!state.gameId) return false;
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
      return true;
    } catch {
      return false;
    }
  }, [state.gameId]);

  const refreshDiscussionHistory = useCallback(async (): Promise<boolean> => {
    if (!state.gameId) return false;
    try {
      const { history } = await api.getDiscussionHistory(state.gameId);
      dispatch({ type: 'SET_DISCUSSION_HISTORY', payload: history });
      return true;
    } catch {
      return false;
    }
  }, [state.gameId]);

  const setConnectionLost = useCallback((lost: boolean) => {
    dispatch({ type: 'SET_CONNECTION_LOST', payload: lost });
  }, []);

  const investigate = useCallback(async (leadId?: string): Promise<Clue[]> => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.investigate(state.gameId, leadId);
      dispatch({
        type: 'SET_CLUES',
        payload: {
          clues: result.clue_board.clues,
          accusationPoints: result.clue_board.accusation_points,
          scenePublicClues: result.clue_board.scene_public_clues,
        },
      });
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          investigationOptions: result.investigation_options,
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.event,
        },
      });
      return result.found;
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId]);

  const introduce = useCallback(
    async (message?: string) => {
      if (!state.gameId) throw new ApiError('游戏尚未开始');
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null });
      try {
        const result = await api.introduce(state.gameId, message);
        const intros: ChatMessage[] = [
          {
            speaker: state.player?.name ?? '你',
            message: result.player_introduction ?? '',
          },
          ...(result.ai_introductions ?? []),
        ];
        dispatch({ type: 'SET_INTRODUCTIONS', payload: intros });
        // 阶段保持 introduction，由介绍页按钮手动进入搜证
      } catch (error) {
        dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
        throw error;
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [state.gameId, state.player?.name],
  );

  const nextPhase = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.nextPhase(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          investigationOptions: result.investigation_options ?? [],
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.last_event ?? null,
        },
      });
      if (result.round !== undefined) {
        dispatch({ type: 'SET_ROUND', payload: result.round });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId]);

  const startVoting = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.startVoting(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      if (result.round !== undefined) {
        dispatch({ type: 'SET_ROUND', payload: result.round });
      }
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId]);

  const returnToInvestigation = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.returnToInvestigation(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({ type: 'SET_ROUND', payload: result.round ?? 1 });
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          investigationOptions: result.investigation_options ?? [],
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.last_event ?? null,
        },
      });
      await refreshClues();
      await refreshDiscussionHistory();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId, refreshClues, refreshDiscussionHistory]);

  const returnToDiscussion = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.returnToDiscussion(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({ type: 'SET_ROUND', payload: result.round ?? 1 });
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          investigationOptions: result.investigation_options ?? [],
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.last_event ?? null,
        },
      });
      await refreshDiscussionHistory();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId, refreshDiscussionHistory]);

  const speak = useCallback(
    async (message: string) => {
      const gameId = state.gameId;
      const playerName = state.player?.name ?? '你';
      if (!gameId || state.isSpeaking) return;

      speakAbortRef.current?.abort();
      const controller = new AbortController();
      speakAbortRef.current = controller;

      // 乐观回显：服务端不再重复发送玩家消息
      dispatch({
        type: 'ADD_DISCUSSION_MESSAGES',
        payload: [{ speaker: playerName, message }],
      });
      dispatch({ type: 'SET_SPEAKING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null });
      try {
        for await (const msg of api.speakStream(gameId, message, controller.signal)) {
          dispatch({ type: 'ADD_DISCUSSION_MESSAGES', payload: [msg] });
        }
      } catch (error) {
        if (controller.signal.aborted) return; // 被新一轮发言/重置打断，静默
        // 不做批量降级（会重复入库）。改用服务端历史重同步，保留已到达内容。
        try {
          const { history } = await api.getDiscussionHistory(gameId);
          const ownRecorded = history.some(
            (m) => m.speaker === playerName && m.message === message,
          );
          dispatch({
            type: 'SET_DISCUSSION_HISTORY',
            payload: ownRecorded
              ? history
              : [...history, { speaker: playerName, message }],
          });
          notify('连接中断，已为你同步最新消息', 'error');
        } catch {
          notify(errMsg(error), 'error');
        }
      } finally {
        if (speakAbortRef.current === controller) {
          speakAbortRef.current = null;
          dispatch({ type: 'SET_SPEAKING', payload: false });
        }
      }
    },
    [state.gameId, state.player?.name, state.isSpeaking, notify],
  );

  const vote = useCallback(
    async (characterName: string): Promise<VoteResponse> => {
      if (!state.gameId) throw new ApiError('游戏尚未开始');
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null });
      try {
        const result = await api.vote(state.gameId, characterName);
        if (result.game_ended) {
          let revealInfo = result.reveal ?? null;
          if (!revealInfo) {
            try {
              revealInfo = await api.getReveal(state.gameId);
            } catch {
              // RevealPhase 会自愈式补取
            }
          }
          dispatch({
            type: 'GAME_ENDED',
            payload: { winner: result.winner || 'unknown', revealInfo },
          });
        }
        return result;
      } catch (error) {
        dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
        throw error;
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [state.gameId],
  );

  const accuse = useCallback(
    async (characterName: string): Promise<AccuseResponse> => {
      if (!state.gameId) throw new ApiError('游戏尚未开始');
      dispatch({ type: 'SET_LOADING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null });
      try {
        const result = await api.accuse(state.gameId, characterName);
        if (result.game_ended) {
          dispatch({
            type: 'GAME_ENDED',
            payload: {
              winner: result.winner || 'unknown',
              revealInfo: result.reveal ?? null,
            },
          });
        }
        return result;
      } catch (error) {
        dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
        throw error;
      } finally {
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    },
    [state.gameId],
  );

  // RevealPhase 自愈：揭晓信息缺失时补取
  const loadReveal = useCallback(async () => {
    if (!state.gameId) return;
    try {
      const reveal = await api.getReveal(state.gameId);
      dispatch({ type: 'SET_REVEAL_INFO', payload: reveal });
    } catch {
      // 保持加载提示，交由用户重试或轮询恢复
    }
  }, [state.gameId]);

  const resetGame = useCallback(() => {
    speakAbortRef.current?.abort();
    dispatch({ type: 'RESET_GAME' });
  }, []);

  return (
    <GameContext.Provider
      value={{
        state,
        createGame,
        loadGame,
        resumeGame,
        refreshStatus,
        refreshClues,
        refreshDiscussionHistory,
        setConnectionLost,
        introduce,
        nextPhase,
        startVoting,
        returnToInvestigation,
        returnToDiscussion,
        investigate,
        speak,
        vote,
        accuse,
        loadReveal,
        resetGame,
      }}
    >
      {children}
    </GameContext.Provider>
  );
}
