import type { LibraryBook, LibraryTask } from '../api/storyLibrary';
import type { Story } from '../api/types';

export type LibraryFilter = 'all' | 'installed' | 'updates';
export interface LibraryView {
  query: string;
  filter: LibraryFilter;
  limit: number;
  retainedIds: string[];
}
export const LIBRARY_PAGE_SIZE = 20;

/** Installation changes a row's status, never its place in the catalogue. */
export function filterLibraryBooks(books: LibraryBook[], view: LibraryView): LibraryBook[] {
  const query = view.query.trim().toLocaleLowerCase('zh-CN');
  return books.filter(book => {
    const inScope = view.filter === 'all'
      || (view.filter === 'installed' && book.installed_version !== null)
      || (view.filter === 'updates' && (hasBookUpdate(book) || view.retainedIds.includes(book.id)));
    return inScope && (!query || [book.title, book.summary, book.available?.title, book.available?.summary]
      .some(value => value?.toLocaleLowerCase('zh-CN').includes(query)));
  }).sort((a, b) => a.id.localeCompare(b.id));
}

export function hasBookUpdate(book: LibraryBook): boolean {
  return book.installed_version !== null && book.latest_version > book.installed_version && !!book.available;
}

/** Show the installed case when playable; catalogue metadata cannot replace it. */
export function bookDisplay(book: LibraryBook): Story {
  return book.installed_version === null && book.available ? book.available : book;
}

export function latestBookTask(tasks: LibraryTask[], storyId: string): LibraryTask | undefined {
  return tasks.filter(task => task.story_id === storyId && task.kind !== 'check')
    .reduce<LibraryTask | undefined>((latest, task) => !latest || task.created > latest.created ? task : latest, undefined);
}

/** Deep links have a safe parent even when there is no browser history. */
export function mobileBackTarget(pathname: string, state?: unknown): string {
  if (pathname.startsWith('/library/')) {
    const from = state && typeof state === 'object' && 'from' in state ? state.from : undefined;
    if (from === '/' || from === '/library' || from === '/my/stories') return from;
    return '/library';
  }
  if (pathname.startsWith('/my/')) return '/my';
  return '/';
}
