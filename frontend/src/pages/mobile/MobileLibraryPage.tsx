import { Download, Search, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import { isLibraryTaskActive, libraryTaskLabel } from '../../api/storyLibrary';
import { bookDisplay, filterLibraryBooks, hasBookUpdate, latestBookTask, LIBRARY_PAGE_SIZE } from '../../utils/mobileLibrary';
import { useMobileLobby } from './lobbyContext';
import { MobileStoryRow } from './MobileStoryRow';

export function MobileLibraryPage() {
  const { library, view, setView, scrollToTop } = useMobileLobby();
  const snapshot = library.snapshot;
  const books = filterLibraryBooks(snapshot?.books ?? [], view);
  const updates = snapshot?.books.filter(hasBookUpdate).length ?? 0;
  const downloads = snapshot?.tasks.filter(task => task.kind !== 'check' && isLibraryTaskActive(task)) ?? [];
  const change = (patch: Partial<typeof view>) => {
    setView(current => ({ ...current, ...patch, limit: LIBRARY_PAGE_SIZE, retainedIds: [] }));
    scrollToTop();
  };
  return <section className="mobile-page mobile-library-page" aria-label="故事列表">
    <div className="mobile-library-toolbar">
      <div className="mobile-search"><Search size={18} aria-hidden="true" />
        <input type="search" aria-label="搜索故事名称或简介" placeholder="搜索故事名称或简介" value={view.query}
          onChange={event => change({ query: event.target.value })} />
        {view.query && <button type="button" className="mobile-icon-button" aria-label="清除搜索" onClick={() => change({ query: '' })}><X size={17} /></button>}
      </div>
      <div className="mobile-library-filters" role="group" aria-label="故事范围">
        {([['all', '全部'], ['installed', '可开局'], ['updates', `有更新${updates ? ` · ${updates}` : ''}`]] as const).map(([filter, label]) =>
          <button type="button" key={filter} aria-pressed={view.filter === filter} onClick={() => change({ filter })}>{label}</button>)}
      </div>
      <p className="mobile-library-count" aria-live="polite">{snapshot ? `${books.length} 本故事` : '正在读取本地剧本库…'}
        {snapshot?.last_checked_at && <span>检查于 {new Date(snapshot.last_checked_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}</span>}</p>
    </div>
    {downloads.length > 0 && <Link className="mobile-activity-link" to="/my/downloads"><Download size={17} /><span>{downloads.length} 个内容任务 · {libraryTaskLabel(downloads[0])}</span><span>查看</span></Link>}
    {library.error && <p className="mobile-error" role="alert">{library.error}{library.readError && <button type="button" onClick={() => void library.refresh()}>重试读取</button>}</p>}
    {snapshot?.last_check_error && <p className="mobile-note" role="status">{snapshot.last_check_error}；已安装故事仍可开局。</p>}
    <div className="mobile-story-list">{books.slice(0, view.limit).map(book => {
      const task = latestBookTask(snapshot?.tasks ?? [], book.id);
      const active = task && isLibraryTaskActive(task);
      const status = active ? libraryTaskLabel(task)
        : book.installed_version === null ? (book.compatible ? '可下载' : '需要更新应用')
        : hasBookUpdate(book) ? (book.compatible ? '可开局 · 有更新' : '可开局 · 新版需要更新应用')
        : view.retainedIds.includes(book.id) ? '更新完成 · 可开局' : '可直接开局';
      return <MobileStoryRow key={book.id} story={bookDisplay(book)} status={status} />;
    })}</div>
    {snapshot && books.length === 0 && <div className="mobile-empty"><p>{view.filter === 'updates' ? '当前没有可更新的故事' : view.query ? '没有找到符合条件的故事' : '暂无此类故事'}</p>
      {view.query ? <button type="button" className="btn btn-secondary" onClick={() => change({ query: '' })}>清除搜索</button>
        : <p className="mobile-note">可切换“全部”，或点击右上角检查更新。</p>}</div>}
    {books.length > view.limit && <button type="button" className="btn btn-secondary mobile-wide-button" onClick={() => setView(current => ({ ...current, limit: current.limit + LIBRARY_PAGE_SIZE }))}>显示更多 · 还剩 {books.length - view.limit} 本</button>}
  </section>;
}
