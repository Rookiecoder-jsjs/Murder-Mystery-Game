import { useCallback, useEffect, useRef, useState } from 'react';
import { BookOpen, Download, RefreshCw } from 'lucide-react';
import { contentSize, isLibraryTaskActive, libraryApi, libraryTaskLabel, type LibrarySnapshot, type LibraryTask } from '../../api/storyLibrary';
import './StoryLibrary.css';

function TaskProgress({ task, onCancel }: { task: LibraryTask; onCancel: (id: string) => void }) {
  const downloading = task.state === 'downloading';
  const percent = task.total_bytes > 0 ? Math.min(100, Math.floor(task.downloaded_bytes * 100 / task.total_bytes)) : undefined;
  return <div className="content-task" role="status">
    <p>{libraryTaskLabel(task)}{downloading && (' · ' + contentSize(task.downloaded_bytes) + (task.total_bytes > 0 ? ' / ' + contentSize(task.total_bytes) : ''))}</p>
    {downloading && <progress value={percent} max={100} aria-label="内容下载进度" />}
    {task.can_cancel && <button type="button" className="btn btn-ghost" onClick={() => onCancel(task.id)}>取消下载</button>}
  </div>;
}

export function StoryLibrary({ disabled, openingStory, loadError, onOpen }: {
  disabled: boolean; openingStory: string; loadError: { storyId: string; message: string } | null;
  onOpen: (id: string) => void;
}) {
  const [snapshot, setSnapshot] = useState<LibrarySnapshot | null>(null);
  const [tab, setTab] = useState<'installed' | 'discover'>('installed');
  const [error, setError] = useState('');
  const [issuing, setIssuing] = useState(false);
  const mounted = useRef(false);
  const revision = useRef<number | null>(null);
  const refreshing = useRef(false);
  const lastAutomaticCheck = useRef(0);
  const refresh = useCallback(async () => {
    if (refreshing.current) return;
    refreshing.current = true;
    try {
      const value = await libraryApi.read();
      if (!mounted.current) return;
      if (revision.current !== null && revision.current !== value.library_revision) {
        window.dispatchEvent(new Event('mystery:library-updated'));
      }
      revision.current = value.library_revision;
      setSnapshot(value);
    } catch (problem) {
      if (mounted.current) setError(problem instanceof Error ? problem.message : '剧本库读取失败');
    } finally { refreshing.current = false; }
  }, []);
  useEffect(() => {
    mounted.current = true;
    const refreshAndCheck = async () => {
      await refresh();
      try {
        const value = await libraryApi.read();
        const now = Date.now();
        if (mounted.current && now - lastAutomaticCheck.current > 60 * 1000
          && (!value.last_checked_at || now - value.last_checked_at > 24 * 60 * 60 * 1000)) {
          lastAutomaticCheck.current = now;
          await libraryApi.check();
          await refresh();
        }
      } catch { /* A failed check cannot block local play. */ }
    };
    void refreshAndCheck();
    const onResume = () => { void refreshAndCheck(); };
    window.addEventListener('mystery:resume', onResume);
    return () => { mounted.current = false; window.removeEventListener('mystery:resume', onResume); };
  }, [refresh]);
  const hasActive = snapshot?.tasks.some(isLibraryTaskActive) ?? false;
  useEffect(() => {
    if (!hasActive) return;
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 750);
    return () => window.clearInterval(timer);
  }, [hasActive, refresh]);

  const issue = async (operation: () => Promise<unknown>) => {
    setIssuing(true); setError('');
    try { await operation(); await refresh(); }
    catch (problem) { if (mounted.current) setError(problem instanceof Error ? problem.message : '内容操作失败'); }
    finally { if (mounted.current) setIssuing(false); }
  };
  const onCancel = (id: string) => { void issue(() => libraryApi.cancel(id)); };
  const books = snapshot?.books.filter(book => tab === 'installed' ? book.installed_version !== null : !!book.available) ?? [];
  const checkTask = snapshot?.tasks.find(task => task.kind === 'check' && isLibraryTaskActive(task));
  const fileTask = snapshot?.tasks.find(task => task.kind === 'file');
  const updateCount = snapshot?.books.filter(book => book.installed_version !== null && book.can_download).length ?? 0;
  return <section className="story-library" aria-label="可更新的精选剧本库">
    <div className="content-toolbar">
      <div className="content-tabs" role="group" aria-label="精选剧本范围">
        <button type="button" aria-pressed={tab === 'installed'} onClick={() => setTab('installed')}>已下载</button>
        <button type="button" aria-pressed={tab === 'discover'} onClick={() => setTab('discover')}>发现新本{updateCount > 0 && (' · ' + updateCount + ' 个更新')}</button>
      </div>
      <button type="button" className="btn btn-secondary" disabled={issuing || !!checkTask} onClick={() => void issue(() => libraryApi.check())}>
        <RefreshCw size={16} />{checkTask ? '正在检查' : '检查更新'}
      </button>
    </div>
    <p className="content-check-note">{snapshot?.last_checked_at ? '上次成功检查：' + new Date(snapshot.last_checked_at).toLocaleString('zh-CN') : '基础剧本可直接玩，联网可发现更多故事。'}</p>
    {snapshot?.last_check_error && <p className="content-warning" role="status">{snapshot.last_check_error}；已下载故事仍可使用。</p>}
    {error && <p className="home-error" role="alert">{error}</p>}
    {!snapshot && <p role="status">正在读取本地剧本库…</p>}
    {snapshot && !books.length && <p className="library-note">{tab === 'discover' ? '暂无可信的在线目录，请点“检查更新”。也可安装已下载的官方内容包。' : '暂无下载内容，请切换“发现新本”。'}</p>}
    <div className="content-books">
      {books.map(book => {
        const display = tab === 'discover' && book.available ? book.available : book;
        const task = snapshot?.tasks.find(value => value.story_id === book.id && value.kind !== 'check');
        const active = task && isLibraryTaskActive(task);
        const retry = task && ['failed', 'interrupted', 'cancelled'].includes(task.state);
        const canOpen = book.installed_version !== null;
        const showCover = tab === 'installed' || book.latest_version === book.installed_version;
        return <article className="content-book" key={book.id}>
          <div className="content-cover">
            {book.cover_url && showCover && <img src={book.cover_url} alt="" loading="lazy" onError={event => { event.currentTarget.hidden = true; }} />}
            <span><BookOpen size={30} />原创案卷</span>
          </div>
          <div className="content-book-body">
            <h4>{display.title}</h4>
            <p>{display.summary}</p>
            <p className="library-facts">{display.num_characters} 人 · {display.difficulty} · 约 {display.estimated_minutes} 分钟</p>
            <p className="library-credit">{book.installed_version !== null ? '已装 v' + book.installed_version : '尚未下载'}
              {book.latest_version > (book.installed_version ?? 0) && (' · 可用 v' + book.latest_version)}
              {book.delivery === 'bundled' && ' · 应用内置'}</p>
            {book.release_notes && book.can_download && <p className="content-release-note">{book.release_notes}</p>}
            {book.available && !book.compatible && <p className="content-warning">此版本需要更新应用{canOpen ? '；已安装版本仍可游玩。' : '后才能下载。'}</p>}
            {active && <TaskProgress task={task} onCancel={onCancel} />}
            {retry && <p className="content-warning" role="status">{libraryTaskLabel(task)}</p>}
            <div className="content-book-actions">
              {canOpen && <button type="button" className="btn btn-primary" disabled={disabled} onClick={() => onOpen(book.id)}>
                {disabled && openingStory === book.id ? '正在开局…' : '开始游玩'}
              </button>}
              {book.can_download && <button type="button" className="btn btn-secondary" disabled={issuing || !!active} onClick={() => void issue(() => libraryApi.install(book))}>
                <Download size={16} />{retry ? '重试下载' : canOpen ? '更新' : '下载剧本'}{book.download_bytes ? ' · ' + contentSize(book.download_bytes) : ''}
              </button>}
            </div>
            {loadError?.storyId === book.id && <p className="home-error" role="alert">{loadError.message}</p>}
            <details className="content-details"><summary>作者与内容管理</summary>
              <p>{display.author}</p><p>{display.license}</p>
              {book.delivery === 'downloaded' && <><p>移除后保留旧局及其配图，历史版本仍占用空间；有应用基础版则恢复基础版。</p>
                <button type="button" className="btn btn-ghost" disabled={issuing || !!active || disabled} onClick={() => void issue(() => libraryApi.remove(book.id))}>移除下载</button></>}
            </details>
          </div>
        </article>;
      })}
    </div>
    <div className="content-offline">
      <button type="button" className="btn btn-secondary" disabled={issuing || disabled} onClick={() => void issue(() => libraryApi.importFile())}>安装官方内容包（.mmstory）</button>
      <p>可在文件选择器安装已下载的官方包。下载与安装不需要模型密钥；开局不重新审稿或生图。</p>
      {fileTask && (isLibraryTaskActive(fileTask) || fileTask.state !== 'complete') && <TaskProgress task={fileTask} onCancel={onCancel} />}
      {snapshot?.source_url && <a href={snapshot.source_url} target="_blank" rel="noreferrer">本版本对应源码 · AGPL-3.0-only</a>}
    </div>
  </section>;
}
