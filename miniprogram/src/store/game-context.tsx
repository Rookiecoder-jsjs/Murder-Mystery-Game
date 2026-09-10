import Taro from '@tarojs/taro'
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  type PropsWithChildren,
} from 'react'
import { gameApi } from '@/services/game-api'
import { ApiError } from '@/services/http'
import type {
  AccuseResponse,
  CharacterInfo,
  ChatMessage,
  Clue,
  GamePhase,
  GameMode,
  GameEvent,
  InvestigationOption,
  RevealInfo,
  VoteResponse,
  FinalDeduction,
} from '@/types/game'

const LAST_GAME_KEY = 'murder_mystery_last_game_id'

export interface GameState {
  gameId: string | null
  storyId: string | null
  topic: string
  player: CharacterInfo | null
  characters: CharacterInfo[]
  phase: GamePhase
  mode: GameMode
  round: number
  maxRounds: number
  investigationActionsRemaining: number | null
  investigationOptions: InvestigationOption[]
  lastEvent: GameEvent | null
  investigationCount: number
  clues: Clue[]
  scenePublicClues: Clue[]
  accusationPoints: number
  introductions: ChatMessage[]
  discussionHistory: ChatMessage[]
  availableActions: string[]
  finalDeduction: FinalDeduction | null
  revealInfo: RevealInfo | null
  winner: string | null
  gameEnded: boolean
  isLoading: boolean
  isSpeaking: boolean
  error: string | null
}

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
  investigationCount: 0,
  clues: [],
  scenePublicClues: [],
  accusationPoints: 1,
  introductions: [],
  discussionHistory: [],
  availableActions: [],
  finalDeduction: null,
  revealInfo: null,
  winner: null,
  gameEnded: false,
  isLoading: false,
  isSpeaking: false,
  error: null,
}

type Action =
  | { type: 'PATCH'; payload: Partial<GameState> }
  | { type: 'RESET' }

function reducer(state: GameState, action: Action): GameState {
  if (action.type === 'RESET') return initialState
  return { ...state, ...action.payload }
}

interface GameContextValue {
  state: GameState
  createGame: (topic: string, mode?: GameMode) => Promise<string>
  loadGame: (storyId: string, mode?: GameMode) => Promise<string>
  resumeGame: (gameId: string) => Promise<void>
  introduce: (message: string) => Promise<void>
  investigate: (leadId?: string) => Promise<Clue[]>
  nextPhase: () => Promise<void>
  returnToInvestigation: () => Promise<void>
  returnToDiscussion: () => Promise<void>
  startVoting: () => Promise<void>
  speak: (message: string) => Promise<void>
  vote: (characterName: string) => Promise<VoteResponse>
  submitDeduction: (targetId: string, evidenceIds: string[], reason: string) => Promise<FinalDeduction>
  accuse: (characterName: string) => Promise<AccuseResponse>
  loadReveal: (gameId?: string) => Promise<RevealInfo>
  resetGame: () => void
}

const GameContext = createContext<GameContextValue | null>(null)

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请重试'
}

function persistLastGame(gameId: string): void {
  Taro.setStorageSync(LAST_GAME_KEY, gameId)
}

export function getLastGameId(): string {
  return Taro.getStorageSync<string>(LAST_GAME_KEY) || ''
}

export function GameProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(reducer, initialState)

  const createGame = useCallback(async (topic: string, mode: GameMode = 'classic') => {
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.createGame(topic, mode)
      persistLastGame(result.game_id)
      dispatch({
        type: 'PATCH',
        payload: {
          gameId: result.game_id,
          storyId: result.story_id,
          topic: result.topic || topic,
          player: result.player,
          characters: result.characters,
          phase: result.phase,
          mode: result.mode || mode,
          maxRounds: result.max_rounds || (mode === 'quick' ? 3 : 5),
          investigationOptions: [],
          lastEvent: null,
          round: 1,
          investigationActionsRemaining: null,
          clues: [],
          scenePublicClues: [],
          introductions: [],
          discussionHistory: [],
          revealInfo: null,
          winner: null,
          gameEnded: false,
          finalDeduction: null,
        },
      })
      return result.game_id
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [])

  const loadGame = useCallback(async (storyId: string, mode: GameMode = 'classic') => {
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.loadGame(storyId, mode)
      persistLastGame(result.game_id)
      dispatch({
        type: 'PATCH',
        payload: {
          gameId: result.game_id,
          storyId: result.story_id,
          topic: '',
          player: result.player,
          characters: result.characters,
          phase: result.phase,
          mode: result.mode || mode,
          maxRounds: result.max_rounds || (mode === 'quick' ? 3 : 5),
          investigationOptions: [],
          lastEvent: null,
          round: 1,
          investigationActionsRemaining: null,
          clues: [],
          scenePublicClues: [],
          introductions: [],
          discussionHistory: [],
          revealInfo: null,
          winner: null,
          gameEnded: false,
          finalDeduction: null,
        },
      })
      return result.game_id
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [])

  const resumeGame = useCallback(async (gameId: string) => {
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const [status, clueBoard, history] = await Promise.all([
        gameApi.getStatus(gameId),
        gameApi.getClues(gameId),
        gameApi.getDiscussionHistory(gameId),
      ])
      persistLastGame(gameId)
      dispatch({
        type: 'PATCH',
        payload: {
          gameId,
          phase: status.phase,
          mode: status.mode,
          round: status.round,
          maxRounds: status.max_rounds,
          investigationActionsRemaining: status.investigation_actions_remaining ?? null,
          investigationOptions: status.investigation_options,
          lastEvent: status.last_event,
          investigationCount: status.investigation_count || 0,
          player: status.player,
          characters: status.characters,
          availableActions: status.available_actions,
          finalDeduction: status.final_deduction ?? clueBoard.final_deduction ?? null,
          clues: clueBoard.clues,
          scenePublicClues: clueBoard.scene_public_clues,
          accusationPoints: clueBoard.accusation_points,
          discussionHistory: history.history,
          introductions: status.phase === 'introduction' ? history.history : state.introductions,
          gameEnded: status.phase === 'reveal',
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [state.introductions])

  const requireGameId = useCallback(() => {
    if (!state.gameId) throw new ApiError('游戏尚未开始')
    return state.gameId
  }, [state.gameId])

  const introduce = useCallback(async (message: string) => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.introduce(gameId, message)
      dispatch({
        type: 'PATCH',
        payload: {
          introductions: [
            { speaker: state.player?.name || '你', message: result.player_introduction },
            ...result.ai_introductions,
          ],
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.player?.name])

  const investigate = useCallback(async (leadId?: string) => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.investigate(gameId, leadId)
      dispatch({
        type: 'PATCH',
        payload: {
          clues: result.clue_board.clues,
          scenePublicClues: result.clue_board.scene_public_clues,
          accusationPoints: result.clue_board.accusation_points,
          investigationOptions: result.investigation_options,
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.event,
          investigationCount: state.investigationCount + 1,
        },
      })
      return result.found
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.investigationCount])

  const nextPhase = useCallback(async () => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.nextPhase(gameId)
      dispatch({
        type: 'PATCH',
        payload: {
          phase: result.phase,
          round: result.round || state.round,
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          investigationOptions: result.investigation_options || [],
          lastEvent: result.last_event || null,
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.round])

  const returnToInvestigation = useCallback(async () => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const [phase, clueBoard] = await Promise.all([
        gameApi.returnToInvestigation(gameId),
        gameApi.getClues(gameId),
      ])
      dispatch({
        type: 'PATCH',
        payload: {
          phase: phase.phase,
          round: phase.round || state.round,
          investigationActionsRemaining: phase.investigation_actions_remaining ?? null,
          clues: clueBoard.clues,
          scenePublicClues: clueBoard.scene_public_clues,
          accusationPoints: clueBoard.accusation_points,
          investigationOptions: phase.investigation_options || [],
          lastEvent: phase.last_event || null,
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.round])

  const returnToDiscussion = useCallback(async () => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.returnToDiscussion(gameId)
      dispatch({
        type: 'PATCH',
        payload: {
          phase: result.phase,
          round: result.round || state.round,
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          investigationOptions: result.investigation_options || [],
          lastEvent: result.last_event || null,
          finalDeduction: null,
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.round])

  const startVoting = useCallback(async () => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.startVoting(gameId)
      dispatch({
        type: 'PATCH',
        payload: {
          phase: result.phase,
          round: result.round || state.round,
          investigationOptions: result.investigation_options || [],
          investigationActionsRemaining: result.investigation_actions_remaining ?? null,
          lastEvent: result.last_event || null,
          finalDeduction: null,
        },
      })
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.round])

  const speak = useCallback(async (message: string) => {
    const gameId = requireGameId()
    const ownMessage = { speaker: state.player?.name || '你', message }
    const optimisticHistory = [...state.discussionHistory, ownMessage]
    dispatch({
      type: 'PATCH',
      payload: { isSpeaking: true, error: null, discussionHistory: optimisticHistory },
    })
    try {
      const result = await gameApi.speak(gameId, message)
      dispatch({
        type: 'PATCH',
        payload: {
          discussionHistory: [...optimisticHistory, ...result.messages],
          phase: result.phase,
        },
      })
    } catch (error) {
      try {
        const latest = await gameApi.getDiscussionHistory(gameId)
        dispatch({ type: 'PATCH', payload: { discussionHistory: latest.history } })
      } catch {
        dispatch({ type: 'PATCH', payload: { discussionHistory: state.discussionHistory } })
      }
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isSpeaking: false } })
    }
  }, [requireGameId, state.discussionHistory, state.player?.name])

  const vote = useCallback(async (characterName: string) => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.vote(gameId, characterName)
      dispatch({
        type: 'PATCH',
        payload: {
          phase: result.game_ended ? 'reveal' : result.phase,
          gameEnded: result.game_ended,
          winner: result.winner,
          revealInfo: result.reveal || null,
        },
      })
      return result
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId])

  const submitDeduction = useCallback(async (
    targetId: string,
    evidenceIds: string[],
    reason: string,
  ) => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.submitDeduction(gameId, targetId, evidenceIds, reason)
      dispatch({ type: 'PATCH', payload: { finalDeduction: result } })
      return result
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId])

  const accuse = useCallback(async (characterName: string) => {
    const gameId = requireGameId()
    dispatch({ type: 'PATCH', payload: { isLoading: true, error: null } })
    try {
      const result = await gameApi.accuse(gameId, characterName)
      dispatch({
        type: 'PATCH',
        payload: result.game_ended
          ? {
              phase: 'reveal',
              gameEnded: true,
              winner: result.winner,
              revealInfo: result.reveal || null,
              accusationPoints: 0,
            }
          : { accusationPoints: Math.max(0, state.accusationPoints - 1) },
      })
      return result
    } catch (error) {
      dispatch({ type: 'PATCH', payload: { error: messageOf(error) } })
      throw error
    } finally {
      dispatch({ type: 'PATCH', payload: { isLoading: false } })
    }
  }, [requireGameId, state.accusationPoints])

  const loadReveal = useCallback(async (gameId?: string) => {
    const targetId = gameId || requireGameId()
    const result = await gameApi.getReveal(targetId)
    dispatch({
      type: 'PATCH',
      payload: {
        gameId: targetId,
        revealInfo: result,
        winner: result.winner,
        phase: 'reveal',
        gameEnded: true,
        characters: result.characters || state.characters,
      },
    })
    return result
  }, [requireGameId, state.characters])

  const resetGame = useCallback(() => {
    Taro.removeStorageSync(LAST_GAME_KEY)
    dispatch({ type: 'RESET' })
  }, [])

  const value = useMemo<GameContextValue>(() => ({
    state,
    createGame,
    loadGame,
    resumeGame,
    introduce,
    investigate,
    nextPhase,
    returnToInvestigation,
    returnToDiscussion,
    startVoting,
    speak,
    vote,
    submitDeduction,
    accuse,
    loadReveal,
    resetGame,
  }), [
    state,
    createGame,
    loadGame,
    resumeGame,
    introduce,
    investigate,
    nextPhase,
    returnToInvestigation,
    returnToDiscussion,
    startVoting,
    speak,
    vote,
    submitDeduction,
    accuse,
    loadReveal,
    resetGame,
  ])

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>
}

export function useGame(): GameContextValue {
  const context = useContext(GameContext)
  if (!context) throw new Error('useGame 必须在 GameProvider 内使用')
  return context
}
