// API client for the murder mystery game
// 依赖 Vite 开发代理（/games、/stories → 后端），生产部署需同域或配置 API_BASE。

import type {
  AccuseResponse,
  ChatMessage,
  ClueBoard,
  CreateGameResponse,
  GameStatus,
  GameMode,
  IntroductionResponse,
  InvestigateResponse,
  LoadGameResponse,
  PhaseResponse,
  RevealInfo,
  Story,
  VoteResponse,
} from './types';

const API_BASE = '';

export class ApiError extends Error {
  readonly status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** SSE 流在指定时间内没有任何数据时抛出 */
export class StreamTimeoutError extends Error {
  constructor() {
    super('响应超时，请重试');
    this.name = 'StreamTimeoutError';
  }
}

/** 取出 ApiError 的 HTTP 状态码（非 ApiError 返回 undefined） */
export function apiErrorStatus(error: unknown): number | undefined {
  return error instanceof ApiError ? error.status : undefined;
}

async function fetchApi<T>(
  endpoint: string,
  options?: RequestInit,
  timeoutMs?: number,
): Promise<T> {
  let response: Response;
  const controller = new AbortController();
  const timer = timeoutMs
    ? setTimeout(() => controller.abort(), timeoutMs)
    : undefined;
  try {
    response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
  } catch (err) {
    if (timer !== undefined) clearTimeout(timer);
    // 主动超时中断 → 提示用户重试，而不是永远转圈
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError('生成超时，请点击提交重新尝试');
    }
    throw new ApiError('无法连接服务器，请检查后端是否启动');
  }
  if (timer !== undefined) clearTimeout(timer);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: '未知错误' }));
    throw new ApiError(error.detail || `请求失败（${response.status}）`, response.status);
  }

  return response.json();
}

/** 流式无活动超时：每个数据块到达都会重置计时 */
const STREAM_INACTIVITY_MS = 120_000;

export const api = {
  // Stories
  listStories: () =>
    fetchApi<{ stories: Story[] }>('/stories'),

  // Games
  // 生成上限：后端内部有 1 次重试，5 分钟只兜"静默挂起"，不误杀慢但正常的生成
  createGame: (topic: string, playerName?: string, mode: GameMode = 'classic') =>
    fetchApi<CreateGameResponse>(
      '/games',
      {
        method: 'POST',
        body: JSON.stringify({ topic, player_name: playerName, mode }),
      },
      300_000,
    ),

  loadGame: (storyId: string, mode: GameMode = 'classic') =>
    fetchApi<LoadGameResponse>('/games/load', {
      method: 'POST',
      body: JSON.stringify({ story_id: storyId, mode }),
    }),

  getGameStatus: (gameId: string) =>
    fetchApi<GameStatus>(`/games/${gameId}`),

  getClues: (gameId: string) =>
    fetchApi<ClueBoard>(`/games/${gameId}/clues`),

  introduce: (gameId: string, message?: string) =>
    fetchApi<IntroductionResponse>(`/games/${gameId}/introduce`, {
      method: 'POST',
      body: JSON.stringify({ message: message ?? '' }),
    }),

  investigate: (gameId: string, leadId?: string) =>
    fetchApi<InvestigateResponse>(`/games/${gameId}/investigate`, {
      method: 'POST',
      body: JSON.stringify(leadId ? { lead_id: leadId } : {}),
    }),

  nextPhase: (gameId: string) =>
    fetchApi<PhaseResponse>(`/games/${gameId}/next-phase`, {
      method: 'POST',
    }),

  returnToInvestigation: (gameId: string) =>
    fetchApi<PhaseResponse>(`/games/${gameId}/return-to-investigation`, {
      method: 'POST',
    }),

  returnToDiscussion: (gameId: string) =>
    fetchApi<PhaseResponse>(`/games/${gameId}/return-to-discussion`, {
      method: 'POST',
    }),

  startVoting: (gameId: string) =>
    fetchApi<PhaseResponse>(`/games/${gameId}/start-voting`, {
      method: 'POST',
    }),

  /**
   * AI 发言流。服务端在开流前已把玩家消息写入讨论历史，
   * 因此失败时调用方应改用 discussion-history 重新同步，
   * 而不是重试批量发言接口（会导致消息重复入库）。
   */
  speakStream: async function* (
    gameId: string,
    message: string,
    externalSignal?: AbortSignal,
  ): AsyncGenerator<ChatMessage, string, void> {
    const controller = new AbortController();
    const onExternalAbort = () => controller.abort();
    externalSignal?.addEventListener('abort', onExternalAbort);

    let timer: number | undefined;
    const armInactivityTimer = () => {
      if (timer !== undefined) window.clearTimeout(timer);
      timer = window.setTimeout(() => controller.abort(), STREAM_INACTIVITY_MS);
    };
    armInactivityTimer();

    let finalPhase = '';
    try {
      const response = await fetch(`${API_BASE}/games/${gameId}/speak/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        throw new ApiError(`流连接失败（${response.status}）`, response.status);
      }
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        armInactivityTimer();
        buffer += decoder.decode(value, { stream: true });
        let sep;
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const rawEvent = buffer.slice(0, sep);
          buffer = buffer.slice(sep + 2);
          const lines = rawEvent.split('\n');
          let event = 'message';
          let data = '';
          for (const line of lines) {
            if (line.startsWith('event:')) event = line.slice(6).trim();
            else if (line.startsWith('data:')) data += line.slice(5).trim();
          }
          if (!data) continue;
          if (event === 'error') {
            throw new ApiError(JSON.parse(data).detail ?? '流式响应出错');
          }
          if (event === 'done') {
            finalPhase = JSON.parse(data).phase ?? '';
            continue;
          }
          yield JSON.parse(data);
        }
      }
      return finalPhase;
    } catch (err) {
      // 内部超时（外部未中止）→ 转成可读的超时错误
      if (controller.signal.aborted && !externalSignal?.aborted) {
        throw new StreamTimeoutError();
      }
      throw err;
    } finally {
      if (timer !== undefined) window.clearTimeout(timer);
      externalSignal?.removeEventListener('abort', onExternalAbort);
    }
  },

  vote: (gameId: string, characterName: string) =>
    fetchApi<VoteResponse>(`/games/${gameId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ character_name: characterName }),
    }),

  accuse: (gameId: string, characterName: string) =>
    fetchApi<AccuseResponse>(`/games/${gameId}/accuse`, {
      method: 'POST',
      body: JSON.stringify({ character_name: characterName }),
    }),

  getReveal: (gameId: string) =>
    fetchApi<RevealInfo>(`/games/${gameId}/reveal`),

  getDiscussionHistory: (gameId: string) =>
    fetchApi<{ history: ChatMessage[] }>(`/games/${gameId}/discussion-history`),
};

export { API_BASE };
