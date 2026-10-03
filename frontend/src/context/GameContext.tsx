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
import { isAndroid, nativeSnapshot } from '../api/native';
import { useToast } from '../components/common';
import type {
  AccuseResponse,
  DiscussionOptions,
  ChatMessage,
  Clue,
  GamePhase,
  GameMode,
  VoteResponse,
} from '../api/types';
import { GameContext } from './game-context';
import { gameReducer, initialState } from './game-reducer';

function errMsg(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请重试';
}

export function GameProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const { notify } = useToast();
  const speakAbortRef = useRef<AbortController | null>(null);
  const activeGameIdRef = useRef<string | null>(null);

  // 返回新建的 gameId，由页面负责导航到 /game/:gameId
  const createGame = useCallback(async (topic: string, playerName?: string, mode: GameMode = 'classic', characterCount?: number) => {
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const response = await api.createGame(topic, playerName, mode, characterCount);
      activeGameIdRef.current = response.game_id;
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: response.topic,
          caseBrief: response.case_brief,
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
      activeGameIdRef.current = response.game_id;
      dispatch({
        type: 'GAME_CREATED',
        payload: {
          gameId: response.game_id,
          storyId: response.story_id,
          topic: '',
          caseBrief: response.case_brief,
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
    speakAbortRef.current = null;
    activeGameIdRef.current = gameId;
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const snapshot = isAndroid ? await nativeSnapshot(gameId) : null;
      const [status, clueBoard, historyResp] = snapshot
        ? [snapshot.status, snapshot.clues, { history: snapshot.history }] as const
        : await Promise.all([
        api.getGameStatus(gameId),
        api.getClues(gameId),
        api.getDiscussionHistory(gameId),
      ]);
      if (activeGameIdRef.current !== gameId) return;
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
      if (activeGameIdRef.current !== state.gameId) return false;
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          phase: status.phase,
          gameEnded: status.game_ended,
          winner: status.winner,
          isSpeaking: Boolean(speakAbortRef.current) || status.is_speaking,
          mode: status.mode,
          round: status.round,
          maxRounds: status.max_rounds,
          investigationOptions: status.investigation_options,
          lastEvent: status.last_event,
          availableActions: status.available_actions,
          roundProgress: status.round_progress,
          player: status.player,
          characters: status.characters,
          // 简报只在到达时覆盖，避免旧后端缺字段时把已有值刷成 undefined
          ...(status.case_brief ? { caseBrief: status.case_brief } : {}),
          connectionLost: false,
        },
      });
      if (status.phase === 'discussion' && !speakAbortRef.current) {
        const { history } = await api.getDiscussionHistory(state.gameId);
        if (activeGameIdRef.current === state.gameId && !speakAbortRef.current) {
          dispatch({ type: 'SET_DISCUSSION_HISTORY', payload: history });
        }
      }
      return true;
    } catch {
      return false;
    }
  }, [state.gameId]);

  const refreshClues = useCallback(async (): Promise<boolean> => {
    if (!state.gameId) return false;
    try {
      const clueBoard = await api.getClues(state.gameId);
      if (activeGameIdRef.current !== state.gameId) return false;
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
      if (activeGameIdRef.current !== state.gameId) return false;
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
          availableActions: result.available_actions,
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
          availableActions: result.available_actions,
          investigationOptions: result.investigation_options ?? [],
          lastEvent: result.last_event ?? null,
          roundProgress: result.round_progress,
        },
      });
      if (result.round !== undefined) {
        dispatch({ type: 'SET_ROUND', payload: result.round });
      }
      await refreshClues();
    } catch (error) {
      dispatch({ type: 'SET_ERROR', payload: errMsg(error) });
      throw error;
    } finally {
      dispatch({ type: 'SET_LOADING', payload: false });
    }
  }, [state.gameId, refreshClues]);

  const startVoting = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await api.startVoting(state.gameId);
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({ type: 'SET_GAME_STATUS', payload: { availableActions: result.available_actions, lastEvent: result.last_event ?? null } });
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

  const changeInvestigation = useCallback(async (nextRound = false) => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    dispatch({ type: 'SET_LOADING', payload: true });
    dispatch({ type: 'SET_ERROR', payload: null });
    try {
      const result = await (nextRound ? api.nextInvestigationRound(state.gameId) : api.returnToInvestigation(state.gameId));
      dispatch({ type: 'SET_PHASE', payload: result.phase as GamePhase });
      dispatch({ type: 'SET_ROUND', payload: result.round ?? 1 });
      dispatch({
        type: 'SET_GAME_STATUS',
        payload: {
          availableActions: result.available_actions,
          investigationOptions: result.investigation_options ?? [],
          lastEvent: result.last_event ?? null,
          roundProgress: result.round_progress,
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

  const returnToInvestigation = useCallback(() => changeInvestigation(), [changeInvestigation]);
  const startNextRound = useCallback(() => changeInvestigation(true), [changeInvestigation]);

  const collectBallotAdvice = useCallback(async () => {
    if (!state.gameId) throw new ApiError('游戏尚未开始');
    const reveal = await api.collectBallotAdvice(state.gameId);
    if (activeGameIdRef.current === state.gameId) dispatch({ type: 'SET_REVEAL_INFO', payload: reveal });
  }, [state.gameId]);

  const speak = useCallback(
    async (message: string, options: DiscussionOptions = {}) => {
      const gameId = state.gameId;
      const playerName = state.player?.name ?? '你';
      if (!gameId || state.isSpeaking) return { recorded: false, completed: false };
      options = { ...options, action_id: options.action_id || crypto.randomUUID() };
      let recorded = false;
      let completed = false;

      speakAbortRef.current?.abort();
      const controller = new AbortController();
      speakAbortRef.current = controller;

      // Only recorded questions enter history; an unsent draft remains editable.
      dispatch({ type: 'SET_SPEAKING', payload: true });
      dispatch({ type: 'SET_ERROR', payload: null });
      try {
        for await (const msg of api.speakStream(gameId, message, controller.signal, options)) {
          if (controller.signal.aborted || activeGameIdRef.current !== gameId) return { recorded, completed };
          if (msg.speaker === playerName) recorded = true;
          dispatch({ type: 'ADD_DISCUSSION_MESSAGES', payload: [msg] });
        }
        completed = recorded = true;
      } catch (error) {
        if (controller.signal.aborted) return { recorded, completed };
        // 不做批量降级（会重复入库）。改用服务端历史重同步，保留已到达内容。
        try {
          const { history } = await api.getDiscussionHistory(gameId);
          recorded = history.some((m) => m.action_id === options.action_id && m.kind === 'question');
          dispatch({
            type: 'SET_DISCUSSION_HISTORY',
            payload: history,
          });
          notify(recorded ? `${errMsg(error)}，问题已保存，可继续原任务` : `${errMsg(error)}，草稿已保留`, 'error');
        } catch {
          dispatch({ type: 'SET_CONNECTION_LOST', payload: true });
          notify(errMsg(error), 'error');
        }
      } finally {
        if (speakAbortRef.current === controller) {
          speakAbortRef.current = null;
          dispatch({ type: 'SET_SPEAKING', payload: false });
          if (activeGameIdRef.current === gameId) {
            await refreshStatus();
            await refreshClues();
            await refreshDiscussionHistory();
          }
        }
      }
      return { recorded, completed };
    },
    [state.gameId, state.player?.name, state.isSpeaking, notify, refreshStatus, refreshClues, refreshDiscussionHistory],
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
      if (activeGameIdRef.current !== state.gameId) return;
      dispatch({ type: 'SET_REVEAL_INFO', payload: reveal });
    } catch {
      // 保持加载提示，交由用户重试或轮询恢复
    }
  }, [state.gameId]);

  const resetGame = useCallback(() => {
    speakAbortRef.current?.abort();
    speakAbortRef.current = null;
    activeGameIdRef.current = null;
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
        startNextRound,
        collectBallotAdvice,
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
