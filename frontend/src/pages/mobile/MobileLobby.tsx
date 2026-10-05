import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowLeft, BookOpen, House, RefreshCw, UserRound } from 'lucide-react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { libraryApi, isLibraryTaskActive } from '../../api/storyLibrary';
import type { GameMode } from '../../api/types';
import { useStoryLibrary } from '../../components/story-library/useStoryLibrary';
import { LIBRARY_PAGE_SIZE, mobileBackTarget, type LibraryView } from '../../utils/mobileLibrary';
import { useLocalLobby } from './useLocalLobby';
import type { MobileLobbyData } from './lobbyContext';
import './MobileLobby.css';

let savedView: LibraryView = { query: '', filter: 'all', limit: LIBRARY_PAGE_SIZE, retainedIds: [] };
let savedMode: GameMode = 'quick';
const scrollPositions = new Map<string, number>();
const titles: Record<string, string> = {
  '/': '剧本杀', '/library': '剧本库', '/my': '我的', '/my/games': '存档与复盘',
  '/my/stories': '我的剧本', '/my/create': '生成新故事', '/my/tasks': '待完成任务', '/my/downloads': '内容下载',
};

export function MobileLobby() {
  const location = useLocation();
  const library = useStoryLibrary();
  const local = useLocalLobby();
  const [view, setView] = useState(savedView);
  const [mode, setMode] = useState<GameMode>(savedMode);
  const reading = useRef<HTMLDivElement>(null);
  const pathname = location.pathname;
  const detail = pathname.startsWith('/library/');
  const topLevel = ['/', '/library', '/my'].includes(pathname);
  const ready = pathname === '/library' ? !!library.snapshot : !local.loading;
  const checking = library.snapshot?.tasks.some(task => task.kind === 'check' && isLibraryTaskActive(task));
  useEffect(() => { savedView = view; }, [view]);
  useEffect(() => { savedMode = mode; }, [mode]);
  useLayoutEffect(() => {
    if (reading.current && ready) reading.current.scrollTop = scrollPositions.get(pathname) ?? 0;
  }, [pathname, ready]);
  const scrollToTop = useCallback(() => {
    if (reading.current) reading.current.scrollTop = 0;
  }, []);
  const context: MobileLobbyData = { library, local, view, setView, mode, setMode, scrollToTop };
  return <div className="mobile-lobby">
    <header className="mobile-lobby-header">
      {!topLevel && <Link className="mobile-icon-button" to={mobileBackTarget(pathname, location.state)} replace aria-label="返回上一页"><ArrowLeft size={21} /></Link>}
      <h1>{pathname === '/' && <img src="/brand/logo-casefile-v2.png" width="32" height="32" alt="" />}{detail ? '案件详情' : titles[pathname] ?? '剧本杀'}</h1>
      {pathname === '/library' && <button type="button" className="mobile-check-button" disabled={library.issuing || checking}
        onClick={() => void library.issue(() => libraryApi.check())}><RefreshCw size={17} />{checking ? '检查中' : '检查更新'}</button>}
    </header>
    <div ref={reading} className={`mobile-lobby-main${detail ? ' mobile-lobby-main--detail' : ''}`}
      onScroll={event => { if (ready) scrollPositions.set(pathname, event.currentTarget.scrollTop); }}>
      <Outlet context={context} />
    </div>
    {topLevel && <nav className="mobile-lobby-nav" aria-label="主要页面">
      <NavLink to="/" end><House size={21} /><span>首页</span></NavLink>
      <NavLink to="/library"><BookOpen size={21} /><span>剧本库</span></NavLink>
      <NavLink to="/my"><UserRound size={21} /><span>我的</span></NavLink>
    </nav>}
  </div>;
}
