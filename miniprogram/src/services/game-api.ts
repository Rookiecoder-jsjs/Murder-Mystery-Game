import { request } from './http'
import type {
  AccuseResponse,
  ClueBoard,
  GameBootstrap,
  GameMode,
  GameStatus,
  IntroductionResponse,
  InvestigateResponse,
  PhaseResponse,
  RevealInfo,
  SpeakResponse,
  Story,
  VoteResponse,
  FinalDeduction,
} from '@/types/game'

export const gameApi = {
  listStories: () => request<{ stories: Story[] }>('/stories'),

  createGame: (topic: string, mode: GameMode = 'classic') => request<GameBootstrap>('/games', {
    method: 'POST',
    data: { topic, mode },
    timeout: 360_000,
  }),

  loadGame: (storyId: string, mode: GameMode = 'classic') => request<GameBootstrap>('/games/load', {
    method: 'POST',
    data: { story_id: storyId, mode },
  }),

  getStatus: (gameId: string) => request<GameStatus>(`/games/${gameId}`),
  getClues: (gameId: string) => request<ClueBoard>(`/games/${gameId}/clues`),
  getDiscussionHistory: (gameId: string) => request<{ history: import('@/types/game').ChatMessage[] }>(
    `/games/${gameId}/discussion-history`,
  ),
  getReveal: (gameId: string) => request<RevealInfo>(`/games/${gameId}/reveal`),

  introduce: (gameId: string, message: string) => request<IntroductionResponse>(
    `/games/${gameId}/introduce`,
    { method: 'POST', data: { message } },
  ),

  investigate: (gameId: string, leadId?: string) => request<InvestigateResponse>(`/games/${gameId}/investigate`, {
    method: 'POST',
    data: leadId ? { lead_id: leadId } : {},
  }),

  nextPhase: (gameId: string) => request<PhaseResponse>(`/games/${gameId}/next-phase`, {
    method: 'POST',
  }),

  returnToInvestigation: (gameId: string) => request<PhaseResponse>(
    `/games/${gameId}/return-to-investigation`,
    { method: 'POST' },
  ),

  returnToDiscussion: (gameId: string) => request<PhaseResponse>(
    `/games/${gameId}/return-to-discussion`,
    { method: 'POST' },
  ),

  startVoting: (gameId: string) => request<PhaseResponse>(`/games/${gameId}/start-voting`, {
    method: 'POST',
  }),

  speak: (gameId: string, message: string) => request<SpeakResponse>(`/games/${gameId}/speak`, {
    method: 'POST',
    data: { message },
    timeout: 180_000,
  }),

  vote: (gameId: string, characterName: string) => request<VoteResponse>(`/games/${gameId}/vote`, {
    method: 'POST',
    data: { character_name: characterName },
    timeout: 180_000,
  }),

  submitDeduction: (
    gameId: string,
    targetId: string,
    evidenceIds: string[],
    reason: string,
  ) => request<FinalDeduction>(`/games/${gameId}/deduction`, {
    method: 'POST',
    data: { target_id: targetId, evidence_ids: evidenceIds, reason },
  }),

  accuse: (gameId: string, characterName: string) => request<AccuseResponse>(
    `/games/${gameId}/accuse`,
    { method: 'POST', data: { character_name: characterName } },
  ),
}
