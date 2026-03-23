// API client for the murder mystery game

const API_BASE = 'http://localhost:8000';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API Error: ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Stories
  listStories: () => fetchApi<{ stories: Array<{ id: string; title: string; topic: string; created_at: string }> }>('/stories'),

  // Games
  createGame: (topic: string, playerName?: string) =>
    fetchApi<{
      game_id: string;
      story_id: string;
      topic: string;
      phase: string;
      player: any;
      characters: any[];
    }>('/games', {
      method: 'POST',
      body: JSON.stringify({ topic, player_name: playerName }),
    }),

  loadGame: (storyId: string) =>
    fetchApi<{
      game_id: string;
      story_id: string;
      phase: string;
      player: any;
      characters: any[];
    }>('/games/load', {
      method: 'POST',
      body: JSON.stringify({ story_id: storyId }),
    }),

  getGameStatus: (gameId: string) =>
    fetchApi<any>(`/games/${gameId}`),

  // Game actions
  getClues: (gameId: string) =>
    fetchApi<{
      clues: any[];
      accusation_points: number;
      scene_public_clues: any[];
    }>(`/games/${gameId}/clues`),

  introduce: (gameId: string, message?: string) =>
    fetchApi<any>(`/games/${gameId}/introduce`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  nextPhase: (gameId: string) =>
    fetchApi<{ phase: string; round?: number }>(`/games/${gameId}/next-phase`, {
      method: 'POST',
    }),

  returnToInvestigation: (gameId: string) =>
    fetchApi<{ phase: string; round?: number }>(`/games/${gameId}/return-to-investigation`, {
      method: 'POST',
    }),

  startVoting: (gameId: string) =>
    fetchApi<{ phase: string; round?: number }>(`/games/${gameId}/start-voting`, {
      method: 'POST',
    }),

  speak: (gameId: string, message: string) =>
    fetchApi<{
      messages: Array<{ speaker: string; message: string }>;
      phase: string;
    }>(`/games/${gameId}/speak`, {
      method: 'POST',
      body: JSON.stringify({ message }),
    }),

  vote: (gameId: string, characterName: string) =>
    fetchApi<any>(`/games/${gameId}/vote`, {
      method: 'POST',
      body: JSON.stringify({ character_name: characterName }),
    }),

  accuse: (gameId: string, characterName: string) =>
    fetchApi<any>(`/games/${gameId}/accuse`, {
      method: 'POST',
      body: JSON.stringify({ character_name: characterName }),
    }),

  getReveal: (gameId: string) =>
    fetchApi<any>(`/games/${gameId}/reveal`),

  getDiscussionHistory: (gameId: string) =>
    fetchApi<{ history: string[] }>(`/games/${gameId}/discussion-history`),
};

export { API_BASE };
