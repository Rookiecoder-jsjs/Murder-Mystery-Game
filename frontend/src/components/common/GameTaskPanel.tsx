import { useCallback, useEffect, useRef, useState } from 'react';
import { engineCommand, isAndroid, waitForTask, type NativeTask } from '../../api/native';
import { useGame } from '../../context/useGame';
import { Button } from './Button';
import { useToast } from './useToast';

/** Resume the existing native action in its game, preserving its task ID. */
export function GameTaskPanel() {
  const { state, refreshStatus, refreshClues, refreshDiscussionHistory, loadReveal } = useGame();
  const { notify } = useToast();
  const [task, setTask] = useState<NativeTask | null>(null);
  const [busy, setBusy] = useState(false);
  const readGeneration = useRef(0);
  const refresh = useCallback(async () => {
    if (!isAndroid || !state.gameId) return;
    const generation = ++readGeneration.current;
    const result = await engineCommand<{ tasks: NativeTask[] }>({ kind: 'tasks' });
    if (generation !== readGeneration.current) return;
    setTask(result.tasks.find(t => t.endpoint.startsWith(`/games/${state.gameId}/`) &&
      (t.state === 'interrupted' || (t.state === 'failed' && t.can_continue))) || null);
  }, [state.gameId]);
  useEffect(() => {
    if (!isAndroid) return;
    let stopped = false;
    const read = () => { if (!stopped) void refresh().catch(() => undefined); };
    read();
    const timer = !state.gameEnded ? window.setInterval(read, 3000) : undefined;
    window.addEventListener('mystery:tasks', read);
    window.addEventListener('mystery:resume', read);
    return () => { stopped = true; readGeneration.current += 1; window.clearInterval(timer); window.removeEventListener('mystery:tasks', read); window.removeEventListener('mystery:resume', read); };
  }, [refresh, state.gameEnded]);
  const resume = async () => {
    if (!task || busy) return;
    setBusy(true);
    try {
      await engineCommand({ kind: 'continue', id: task.id });
      await waitForTask(task.id);
      await refreshStatus();
      await refreshClues();
      await refreshDiscussionHistory();
      if (task.endpoint.endsWith('/ballot-advice') || state.gameEnded) await loadReveal();
    } catch (error) { notify(error instanceof Error ? error.message : '任务未完成', 'error'); }
    finally { setBusy(false); void refresh().catch(() => undefined); }
  };
  if (!task || !task.endpoint.startsWith(`/games/${state.gameId}/`)) return null;
  return <div className="game-task-panel" role="status"><span>{task.label || '本次操作'}已中断，已完成内容保留。</span>
    <Button size="sm" onClick={resume} isLoading={busy}>继续原任务</Button></div>;
}
