import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { engineCommand, waitForTask, type NativeTask } from '../../api/native';
import { isLibraryTaskActive, libraryApi } from '../../api/storyLibrary';
import { useMobileLobby } from './lobbyContext';
import { MobileLibraryTask } from './MobileLibraryTask';

export function MobileTasksPage() {
  const { local } = useMobileLobby();
  const navigate = useNavigate();
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [showFailed, setShowFailed] = useState(false);
  const running = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const current = local.tasks.filter(task => task.state !== 'failed' || task.can_continue);
  const failed = local.tasks.filter(task => task.state === 'failed' && !task.can_continue);
  const resume = async (task: NativeTask) => {
    if (running.current) return;
    running.current = true; setBusy(task.id); setError('');
    try {
      if (task.state === 'failed' || task.state === 'interrupted') await engineCommand({ kind: 'continue', id: task.id });
      const result = await waitForTask<{ game_id?: string }>(task.id);
      const id = result.game_id ?? task.game_id ?? task.endpoint.match(/^\/games\/([^/]+)\//)?.[1];
      if (id && mounted.current) navigate(`/game/${id}`);
    } catch (problem) { if (mounted.current) setError(problem instanceof Error ? problem.message : '任务未完成'); }
    finally { running.current = false; if (mounted.current) setBusy(''); void local.refresh(); }
  };
  return <section className="mobile-page"><p className="mobile-note">中断后可继续原任务，已经完成的回复和内容会保留。</p>
    {error && <p className="mobile-error" role="alert">{error}</p>}
    {[...current, ...(showFailed ? failed : [])].map(task => <article className="mobile-task-record" key={task.id}><h2>{task.title || task.label}</h2>
      <p className="mobile-note">{task.progress?.label || task.label}</p>{task.error && <p className="mobile-error">{task.error}</p>}
      {task.state !== 'failed' || task.can_continue ? <button type="button" className="btn btn-secondary" disabled={!!busy || (local.running && task.state !== 'running' && task.state !== 'queued')} onClick={() => void resume(task)}>{busy === task.id ? '正在等待结果…' : task.state === 'running' || task.state === 'queued' ? '查看结果' : '继续任务'}</button>
        : <button type="button" className="btn btn-ghost" disabled={!!busy} onClick={async () => {
          try { await engineCommand({ kind: 'dismiss', id: task.id }); await local.refresh(); }
          catch (problem) { setError(problem instanceof Error ? problem.message : '移除失败'); }
        }}>移除失败记录</button>}
    </article>)}
    {!!failed.length && <button type="button" className="btn btn-ghost mobile-wide-button" onClick={() => setShowFailed(value => !value)}>{showFailed ? '收起失败记录' : `查看失败记录（${failed.length}）`}</button>}
    {!local.loading && !current.length && <p className="mobile-empty">当前没有待完成任务</p>}
    {local.error && <p className="mobile-error" role="alert">{local.error}</p>}
  </section>;
}

export function MobileDownloadsPage() {
  const { library } = useMobileLobby();
  const tasks = library.snapshot?.tasks ?? [];
  const active = tasks.filter(isLibraryTaskActive);
  const recent = tasks.filter(task => !isLibraryTaskActive(task));
  const display = (task: typeof tasks[number]) => <article className="mobile-task-record" key={task.id}>
    <h2>{task.kind === 'check' ? '检查官方目录' : library.snapshot?.books.find(book => book.id === task.story_id)?.title ?? '官方内容包'}</h2>
    <MobileLibraryTask task={task} onCancel={id => void library.issue(() => libraryApi.cancel(id))} disabled={library.issuing} />
  </article>;
  return <section className="mobile-page"><p className="mobile-note">下载失败或中断时，可回到故事详情重试。进程退出后，未完成下载不会继续在后台运行。</p>
    {active.map(display)}{library.error && <p className="mobile-error" role="alert">{library.error}</p>}
    {!active.length && <p className="mobile-empty">当前没有正在下载的内容</p>}
    {recent.length > 0 && <details className="mobile-content-details"><summary>最近记录（{recent.length}）</summary>{recent.map(display)}</details>}
  </section>;
}
