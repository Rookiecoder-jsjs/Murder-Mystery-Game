import { ChevronRight, Clock, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';
import { gameEngine } from '../../api/native';
import { useToast } from '../../components/common';
import { bookDisplay } from '../../utils/mobileLibrary';
import { useMobileLobby } from './lobbyContext';
import { MobileStoryRow } from './MobileStoryRow';

export function MobileHomePage() {
  const { library, local } = useMobileLobby();
  const { notify } = useToast();
  const latest = local.games.find(game => game.phase !== 'reveal') ?? local.games[0];
  const pending = local.tasks.filter(task => task.state !== 'failed' || task.can_continue);
  const books = (library.snapshot?.books ?? []).filter(book => book.installed_version !== null)
    .sort((a, b) => a.id.localeCompare(b.id)).slice(0, 2);
  const openSettings = async () => {
    try { await gameEngine.openSettings(); await local.refresh(); }
    catch (error) { notify(error instanceof Error ? error.message : '模型设置未保存', 'error'); }
  };
  return <div className="mobile-page mobile-home-page">
    <div className="mobile-home-intro"><h2>今晚，开一宗新案</h2><p>一人入戏，寻找真相</p></div>
    {local.configured === false && <button type="button" className="mobile-activity-link" onClick={() => void openSettings()}><Settings size={18} /><span>填写模型密钥，准备 AI 对话</span><ChevronRight size={17} /></button>}
    {local.error && <p className="mobile-error" role="alert">{local.error}<button type="button" onClick={() => void local.refresh()}>重试读取</button></p>}
    {pending.length > 0 && <Link className="mobile-activity-link" to="/my/tasks"><Clock size={18} /><span>{pending.length} 个待完成任务</span><ChevronRight size={17} /></Link>}
    <section className="mobile-home-continue" aria-label="最近一局"><div className="mobile-section-title"><h2>{latest?.phase === 'reveal' ? '最近复盘' : '继续游戏'}</h2><Link to="/my/games">全部存档</Link></div>
      {local.loading ? <p className="mobile-note" role="status">正在读取存档…</p> : latest ? <>
        <h3>{latest.title}</h3><p className="mobile-note">{latest.player}{latest.phase === 'reveal' ? ' · 已结案' : ` · 第 ${latest.round ?? 1} 轮`}</p>
        <Link className="btn btn-primary mobile-wide-button" to={`/game/${latest.game_id}`}>{latest.phase === 'reveal' ? '查看复盘' : '继续游玩'}</Link>
      </> : <><p className="mobile-note">选一个故事，开始你的第一宗案件。</p><Link className="btn btn-primary mobile-wide-button" to="/library">选择故事</Link></>}
    </section>
    <section aria-label="推荐故事"><div className="mobile-section-title"><h2>从这些案件开始</h2><Link to="/library">查看全部</Link></div>
      <div className="mobile-story-list">{books.map(book => <MobileStoryRow key={book.id} story={bookDisplay(book)} status="成品直接开局" />)}</div>
      {!library.snapshot && <p className="mobile-note" role="status">正在读取本地剧本库…</p>}
      {library.error && <p className="mobile-error" role="alert">{library.error}{library.readError && <button type="button" onClick={() => void library.refresh()}>重试读取</button>}</p>}
    </section>
  </div>;
}
