import { gameEngine } from './native';
import type { Story } from './types';

export interface LibraryTask {
  id: string;
  kind: 'check' | 'install' | 'file';
  state: 'queued' | 'checking' | 'downloading' | 'verifying' | 'installing' | 'complete' | 'failed' | 'cancelled' | 'interrupted';
  created: number;
  story_id: string;
  content_version: number;
  sha256: string;
  downloaded_bytes: number;
  total_bytes: number;
  error: string;
  error_code: string;
  can_cancel: boolean;
  cancel_requested?: boolean;
}
export interface LibraryBook extends Story {
  installed_version: number | null;
  latest_version: number;
  compatible: boolean;
  can_download: boolean;
  available?: Story;
  sha256?: string;
  download_bytes?: number;
  release_notes?: string;
}
export interface LibrarySnapshot {
  books: LibraryBook[];
  tasks: LibraryTask[];
  library_revision: number;
  catalog_revision: number;
  last_checked_at: number | null;
  last_check_error: string;
  source_url: string;
}
export const libraryApi = {
  read: () => gameEngine.libraryRead(),
  check: () => gameEngine.libraryCommand({ kind: 'check' }),
  install: (book: LibraryBook) => gameEngine.libraryCommand({ kind: 'install', body: {
    story_id: book.id, content_version: book.latest_version, expected_sha256: book.sha256,
  } }),
  cancel: (id: string) => gameEngine.libraryCommand({ kind: 'cancel', id }),
  remove: (storyId: string) => gameEngine.libraryCommand({ kind: 'remove', storyId }),
  importFile: () => gameEngine.libraryImport(),
};
export function isLibraryTaskActive(task: LibraryTask): boolean {
  return ['queued', 'checking', 'downloading', 'verifying', 'installing'].includes(task.state);
}
export function libraryTaskLabel(task: LibraryTask): string {
  if (task.cancel_requested && isLibraryTaskActive(task)) return '正在取消下载';
  if (task.error) return task.error;
  if (task.kind === 'file' && task.state === 'downloading') return '正在读取内容包';
  const labels: Record<LibraryTask['state'], string> = {
    queued: '等待下载', checking: '正在检查官方目录', downloading: '正在下载',
    verifying: '正在校验正文与配图', installing: '正在安装', complete: '已完成',
    failed: '下载失败，请重试', cancelled: '已取消', interrupted: '下载中断，请重试',
  };
  return labels[task.state];
}
export function contentSize(bytes: number): string {
  return bytes < 1024 * 1024 ? Math.ceil(bytes / 1024) + ' KB' : (bytes / 1024 / 1024).toFixed(1) + ' MB';
}
