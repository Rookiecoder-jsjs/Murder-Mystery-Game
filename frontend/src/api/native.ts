import { Capacitor, registerPlugin } from '@capacitor/core';
import type { ClueBoard, GameStatus, ChatMessage } from './types';
import type { LibrarySnapshot, LibraryTask } from './storyLibrary';

export const isAndroid = Capacitor.getPlatform() === 'android';

export interface SavedGame {
  game_id: string;
  title: string;
  phase: string;
  round?: number;
  player?: string;
  last_activity?: number;
}

export interface NativeTask {
  id: string;
  state: 'queued' | 'running' | 'done' | 'interrupted' | 'failed' | 'dismissed';
  error?: string;
  endpoint: string;
  result?: unknown;
  status?: number;
  progress?: { stage: string; label: string };
  game_id?: string;
  title?: string;
  label?: string;
  can_continue?: boolean;
}
interface ModelSettings {
  configured: boolean;
  baseUrl: string;
  storyModel: string;
  roleModel: string;
  reviewModel: string;
}
interface NativeBridge {
  command(options: { command: Record<string, unknown> }): Promise<{ data?: unknown; error?: string; status?: number }>;
  settings(): Promise<ModelSettings>;
  openSettings(): Promise<void>;
  draft(options: { gameId: string; value?: string }): Promise<{ value: string }>;
  libraryRead(): Promise<LibrarySnapshot>;
  libraryCommand(options: { kind: string; body?: Record<string, unknown>; id?: string; storyId?: string }): Promise<LibraryTask>;
  libraryImport(): Promise<LibraryTask | { cancelled: true }>;
}
export const gameEngine = registerPlugin<NativeBridge>('GameEngine');

export class NativeError extends Error {
  readonly status?: number;
  constructor(message: string, status?: number) { super(message); this.status = status; }
}

export async function engineCommand<T>(command: Record<string, unknown>): Promise<T> {
  const result = await gameEngine.command({ command });
  if (result.error) throw new NativeError(result.error, result.status);
  return result.data as T;
}

export async function waitForTask<T>(id: string, signal?: AbortSignal): Promise<T> {
  let previousProgress = '';
  for (;;) {
    if (signal?.aborted) throw new DOMException('接收已停止', 'AbortError');
    const task = await engineCommand<NativeTask>({ kind: 'task', id });
    const progressKey = JSON.stringify(task.progress);
    if (task.progress && progressKey !== previousProgress) {
      window.dispatchEvent(new CustomEvent('mystery:task-progress', { detail: task }));
      previousProgress = progressKey;
    }
    if (task.state === 'dismissed') throw new NativeError('任务已移除');
    if (task.state === 'done') {
      window.dispatchEvent(new Event('mystery:tasks'));
      return task.result as T;
    }
    if (task.state === 'failed' || task.state === 'interrupted') {
      window.dispatchEvent(new Event('mystery:tasks'));
      throw new NativeError(task.error || '任务中断，可在首页继续', task.status);
    }
    await new Promise(resolve => window.setTimeout(resolve, document.hidden ? 5000 : 800));
  }
}

export async function nativeRequest<T>(endpoint: string, options?: RequestInit): Promise<T> {
  if (!options?.method || options.method === 'GET') return engineCommand<T>({ kind: 'read', endpoint });
  const id = crypto.randomUUID();
  const body: unknown = typeof options.body === 'string' ? JSON.parse(options.body) : {};
  await engineCommand({ kind: 'start', id, endpoint, body });
  return waitForTask<T>(id);
}

export function nativeSnapshot(gameId: string) {
  return engineCommand<{ status: GameStatus; clues: ClueBoard; history: ChatMessage[]; revision: number }>({
    kind: 'read', endpoint: `/games/${gameId}/snapshot`,
  });
}

export async function* nativeSpeak(gameId: string, body: Record<string, unknown>, signal?: AbortSignal): AsyncGenerator<ChatMessage, string, void> {
  const id = typeof body.action_id === 'string' ? body.action_id : crypto.randomUUID();
  const original = await engineCommand<{ history: ChatMessage[] }>({ kind: 'read', endpoint: `/games/${gameId}/discussion-history` });
  let seen = original.history.length;
  await engineCommand({ kind: 'start', id, endpoint: `/games/${gameId}/speak`, body });
  for (;;) {
    if (signal?.aborted) throw new DOMException('接收已停止', 'AbortError');
    const task = await engineCommand<NativeTask>({ kind: 'task', id });
    if (task.state === 'dismissed') throw new NativeError('任务已移除');
    const { history } = await engineCommand<{ history: ChatMessage[] }>({ kind: 'read', endpoint: `/games/${gameId}/discussion-history` });
    for (const message of history.slice(seen)) yield message;
    seen = Math.max(seen, history.length);
    if (task.state === 'done') {
      window.dispatchEvent(new Event('mystery:tasks'));
      return (task.result as { phase: string }).phase;
    }
    if (task.state === 'interrupted' || task.state === 'failed') {
      window.dispatchEvent(new Event('mystery:tasks'));
      throw new NativeError(task.error || '任务中断，可在首页继续');
    }
    await new Promise(resolve => window.setTimeout(resolve, document.hidden ? 5000 : 800));
  }
}
