import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMobileLobby } from './lobbyContext';

export function MobileGamesPage() {
  const { local } = useMobileLobby();
  const [filter, setFilter] = useState<'ongoing' | 'ended' | 'all'>('ongoing');
  const [limit, setLimit] = useState(20);
  const games = local.games.filter(game => filter === 'all' || (filter === 'ended') === (game.phase === 'reveal'));
  return <section className="mobile-page">
    <div className="mobile-library-filters" role="group" aria-label="存档范围">
      {([['ongoing', '进行中'], ['ended', '已结案'], ['all', '全部']] as const).map(([value, label]) => <button key={value} type="button" aria-pressed={filter === value} onClick={() => { setFilter(value); setLimit(20); }}>{label}</button>)}
    </div>
    <div className="mobile-save-list">{games.slice(0, limit).map(game => <Link key={game.game_id} to={`/game/${game.game_id}`} className="mobile-save-row">
      <strong>{game.title}</strong><span>{game.player}{game.phase === 'reveal' ? ' · 已结案' : ` · 第 ${game.round ?? 1} 轮`}</span>
      <small>{game.last_activity ? new Date(game.last_activity * 1000).toLocaleString('zh-CN') : '本地存档'}</small>
      <em>{game.phase === 'reveal' ? '查看复盘' : '继续游玩'} →</em>
    </Link>)}</div>
    {local.loading && <p className="mobile-note" role="status">正在读取存档…</p>}
    {!local.loading && !games.length && <p className="mobile-empty">暂无此类存档</p>}
    {local.error && <p className="mobile-error" role="alert">{local.error}<button type="button" onClick={() => void local.refresh()}>重试读取</button></p>}
    {games.length > limit && <button type="button" className="btn btn-secondary mobile-wide-button" onClick={() => setLimit(value => value + 20)}>显示更多存档</button>}
  </section>;
}
