import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { engineCommand, gameEngine, waitForTask, type NativeTask } from '../../api/native';

interface SavedGame { game_id: string; title: string; phase: string; round?: number; player?: string; last_activity?: number }

export function NativeHome({ hideTasks = false }: { hideTasks?: boolean }) {
  const navigate = useNavigate();
  const [configured, setConfigured] = useState(false);
  const [games, setGames] = useState<SavedGame[]>([]);
  const [tasks, setTasks] = useState<NativeTask[]>([]);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [showAllGames, setShowAllGames] = useState(false);
  const [showFailed, setShowFailed] = useState(false);
  const mounted = useRef(false);
  const refresh = useCallback(async () => {
    try {
      const settings = await gameEngine.settings(); setConfigured(settings.configured);
      const [saved, unfinished] = await Promise.all([
        engineCommand<{ games: SavedGame[] }>({ kind: 'games' }),
        engineCommand<{ tasks: NativeTask[] }>({ kind: 'tasks' }),
      ]);
      setGames(saved.games.reverse().sort((a, b) => (b.last_activity || 0) - (a.last_activity || 0))); setTasks(unfinished.tasks);
    } catch (error) { setMessage(error instanceof Error ? error.message : '本地存档读取失败'); }
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const onResume = () => { void refresh(); };
    const onProgress = (event: Event) => {
      const task = (event as CustomEvent<NativeTask>).detail;
      setTasks(current => current.map(value => value.id === task.id ? task : value));
    };
    window.addEventListener('mystery:resume', onResume);
    window.addEventListener('mystery:tasks', onResume);
    window.addEventListener('mystery:task-progress', onProgress);
    return () => {
      mounted.current = false;
      window.removeEventListener('mystery:resume', onResume);
      window.removeEventListener('mystery:tasks', onResume);
      window.removeEventListener('mystery:task-progress', onProgress);
    };
  }, [refresh]);

  const continueTask = async (task: NativeTask) => {
    setBusy(true); setMessage('正在继续任务，已完成的回复会保留…');
    try {
      if (task.state === 'interrupted' || task.state === 'failed') {
        await engineCommand({ kind: 'continue', id: task.id });
        await refresh();
      }
      const result = await waitForTask<{ game_id?: string }>(task.id);
      const gameId = result.game_id ?? task.endpoint.match(/^\/games\/([^/]+)\//)?.[1];
      if (gameId && mounted.current) navigate(`/game/${gameId}`);
      setMessage('任务已完成');
    } catch (error) { setMessage(error instanceof Error ? error.message : '任务未完成'); }
    finally { setBusy(false); void refresh(); }
  };

  const failedTasks = tasks.filter(task => task.state === 'failed' && !task.can_continue);
  const currentTasks = tasks.filter(task => task.state !== 'failed' || task.can_continue);
  return <section className="native-home" aria-label="手机游戏">
    <div className="native-home-top"><span>{configured ? '模型已配置 · 手机独立运行' : '填写模型密钥，即可开始游玩'}</span>
      <button className="btn btn-secondary" onClick={async () => {
        try { await gameEngine.openSettings(); await refresh(); }
        catch { setMessage('模型设置未保存'); }
      }}>模型设置</button></div>
    {message && <p role="status">{message}</p>}
    {!hideTasks && tasks.length > 0 && <div className="native-tasks"><strong>{currentTasks.length ? '待完成任务' : '历史任务'}</strong>
      {!!currentTasks.length && <p>中断后可继续原任务，已完成内容会保留。</p>}
      {[...currentTasks, ...(showFailed ? failedTasks : [])].map(task => <div key={task.id} className="native-saved-row">
        <span>{task.title && `${task.title} · `}{task.label}<small>{task.error || task.progress?.label || '等待完成'}</small></span>
        {(task.state !== 'failed' || task.can_continue) && <button className="btn btn-secondary" disabled={busy} onClick={() => void continueTask(task)}>
          {task.state === 'running' || task.state === 'queued' ? '查看结果' : '继续任务'}
        </button>}
        {task.state === 'failed' && !task.can_continue && <button className="btn btn-ghost" disabled={busy} onClick={async () => {
          try { await engineCommand({ kind: 'dismiss', id: task.id }); await refresh(); }
          catch (error) { setMessage(error instanceof Error ? error.message : '移除失败'); }
        }}>移除</button>}</div>)}
      {!!failedTasks.length && <button className="btn btn-ghost" onClick={() => setShowFailed(value => !value)}>{showFailed ? '收起失败记录' : `查看失败记录（${failedTasks.length}）`}</button>}
    </div>}
    {games.length > 0 && <div className="native-saves"><strong>我的游戏</strong>
      {games.slice(0, showAllGames ? games.length : 2).map(game => <button className="native-saved-row" key={game.game_id}
        onClick={() => navigate(`/game/${game.game_id}`)}><span>{game.title}<small>{game.player}{game.last_activity ? ` · ${new Date(game.last_activity * 1000).toLocaleString('zh-CN')}` : ''}</small></span><span>{game.phase === 'reveal' ? '查看复盘' : `继续第 ${game.round || 1} 轮`} →</span></button>)}
      {games.length > 2 && <button className="btn btn-ghost native-saves-toggle" onClick={() => setShowAllGames(value => !value)}>
        {showAllGames ? '收起存档' : `全部存档（${games.length}）`}
      </button>}
    </div>}
  </section>;
}
