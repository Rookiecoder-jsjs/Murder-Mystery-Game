import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { gameEngine, type NativeTask } from '../../api/native';
import { useGame } from '../../context/useGame';
import { useMobileLobby } from './lobbyContext';
import { MobileModeSelector } from './MobileModeSelector';

export function MobileGeneratePage() {
  const { local, mode, setMode } = useMobileLobby();
  const { createGame } = useGame();
  const navigate = useNavigate();
  const [topic, setTopic] = useState('');
  const [count, setCount] = useState('');
  const [creating, setCreating] = useState(false);
  const [stage, setStage] = useState('正在准备制作任务');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const mounted = useRef(false);
  const busy = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (!creating) return;
    const began = Date.now();
    const timer = window.setInterval(() => setElapsed(Math.floor((Date.now() - began) / 1000)), 1000);
    const progress = (event: Event) => {
      const task = (event as CustomEvent<NativeTask>).detail;
      if (task.endpoint === '/games' && task.progress) setStage(task.progress.label);
    };
    window.addEventListener('mystery:task-progress', progress);
    return () => { window.clearInterval(timer); window.removeEventListener('mystery:task-progress', progress); };
  }, [creating]);
  const begin = async () => {
    if (!topic.trim() || busy.current || local.running) return;
    busy.current = true; setCreating(true); setElapsed(0); setStage('正在准备制作任务'); setError('');
    try {
      const id = await createGame(topic.trim(), undefined, mode, count ? Number(count) : undefined);
      if (mounted.current) navigate(`/game/${id}`);
    } catch (problem) { if (mounted.current) setError(problem instanceof Error ? problem.message : '制作失败，请重试'); }
    finally { busy.current = false; if (mounted.current) setCreating(false); void local.refresh(); }
  };
  return <section className="mobile-page mobile-generate-page">
    <p className="mobile-note">AI 生成适合探索自定义题材，可能出现逻辑或人物表现不稳定。首次游玩推荐成品故事。</p>
    {creating ? <div className="mobile-generation-progress" role="status"><Sparkles size={26} /><h2>{stage}</h2><p>本案主题：{topic}</p>
      <p className="mobile-note">已用时 {Math.floor(elapsed / 60)}分{String(elapsed % 60).padStart(2, '0')}秒</p>
      <p className="mobile-note">请保持应用前台。可返回首页查看任务；中断后在“待完成任务”中继续。</p><Link className="btn btn-secondary" to="/my/tasks">查看制作任务</Link></div>
      : <><label className="mobile-field">故事主题<textarea value={topic} onChange={event => setTopic(event.target.value)} placeholder="例如：雪山旅馆中的失踪钟声" maxLength={100} rows={3} /></label>
        <label className="mobile-field">角色数量（含你，不含受害者）<select value={count} onChange={event => setCount(event.target.value)}>
          <option value="">根据故事自动决定 · 3—8 人</option>{[3, 4, 5, 6, 7, 8].map(value => <option key={value} value={value}>{value} 人 · {value - 1} 位 AI</option>)}
        </select></label><p className="mobile-note">人数越多，生成篇幅和全员讨论的 API 消耗通常越高。</p>
        <MobileModeSelector value={mode} onChange={setMode} disabled={local.running} />
        {local.configured === false && <button type="button" className="btn btn-secondary mobile-wide-button" onClick={async () => {
          try { await gameEngine.openSettings(); await local.refresh(); }
          catch (problem) { setError(problem instanceof Error ? problem.message : '模型设置未保存'); }
        }}>先填写模型密钥</button>}
        {local.running && <p className="mobile-note">有模型任务正在运行，请先查看待完成任务。</p>}
        <button type="button" className="btn btn-primary mobile-wide-button" disabled={!topic.trim() || local.running || local.configured !== true} onClick={() => void begin()}><Sparkles size={17} />制作并开始游玩</button>
      </>}
    {error && <p className="mobile-error" role="alert">{error}</p>}
  </section>;
}
