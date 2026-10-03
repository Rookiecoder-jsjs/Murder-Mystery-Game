import { gameEngine, isAndroid } from '../api/native';

export interface DiscussionDraft {
  version: 1;
  message: string;
  targetId: string;
  evidenceId: string;
  pendingActionId?: string;
}
export const emptyDiscussionDraft = (targetId = ''): DiscussionDraft => ({ version: 1, message: '', targetId, evidenceId: '' });

export function decodeDiscussionDraft(value: string, defaultTarget = ''): DiscussionDraft {
  if (!value) return emptyDiscussionDraft(defaultTarget);
  try {
    const parsed: unknown = JSON.parse(value);
    if (parsed && typeof parsed === 'object' && 'version' in parsed && parsed.version === 1 &&
        'message' in parsed && typeof parsed.message === 'string' &&
        'targetId' in parsed && typeof parsed.targetId === 'string' &&
        'evidenceId' in parsed && typeof parsed.evidenceId === 'string') {
      return { version: 1, message: parsed.message, targetId: parsed.targetId, evidenceId: parsed.evidenceId,
        ...('pendingActionId' in parsed && typeof parsed.pendingActionId === 'string' ? { pendingActionId: parsed.pendingActionId } : {}) };
    }
  } catch { /* Old Android drafts contain the original text directly. */ }
  return { ...emptyDiscussionDraft(), message: value };
}

const writes = new Map<string, Promise<void>>();
const key = (gameId: string) => `mystery:discussion-draft:${gameId}`;
export async function loadDiscussionDraft(gameId: string, defaultTarget = '') {
  await writes.get(gameId)?.catch(() => undefined);
  const value = isAndroid ? (await gameEngine.draft({ gameId })).value : localStorage.getItem(key(gameId)) || '';
  return decodeDiscussionDraft(value, defaultTarget);
}
export function saveDiscussionDraft(gameId: string, draft: DiscussionDraft): Promise<void> {
  const value = JSON.stringify(draft);
  const write = (writes.get(gameId) || Promise.resolve()).catch(() => undefined).then(async () => {
    if (isAndroid) await gameEngine.draft({ gameId, value });
    else localStorage.setItem(key(gameId), value);
  });
  writes.set(gameId, write);
  return write;
}
