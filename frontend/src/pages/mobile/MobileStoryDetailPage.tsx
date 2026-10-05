import { useEffect, useRef, useState } from 'react';
import { BookOpen, Download, Play } from 'lucide-react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { contentSize, isLibraryTaskActive, libraryApi } from '../../api/storyLibrary';
import { useGame } from '../../context/useGame';
import { useToast } from '../../components/common';
import { bookDisplay, hasBookUpdate, latestBookTask } from '../../utils/mobileLibrary';
import { useMobileLobby } from './lobbyContext';
import { MobileModeSelector } from './MobileModeSelector';
import { MobileLibraryTask } from './MobileLibraryTask';

export function MobileStoryDetailPage() {
  const { storyId } = useParams();
  const { library, local, setView, mode, setMode } = useMobileLobby();
  const { loadGame } = useGame();
  const { notify } = useToast();
  const navigate = useNavigate();
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState('');
  const [failedImage, setFailedImage] = useState('');
  const openingRef = useRef(false);
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const book = library.snapshot?.books.find(value => value.id === storyId);
  const story = book ? bookDisplay(book) : local.stories.find(value => value.id === storyId);
  const task = storyId ? latestBookTask(library.snapshot?.tasks ?? [], storyId) : undefined;
  const installing = task && isLibraryTaskActive(task);
  const playable = book ? book.installed_version !== null : !!story;
  const begin = async () => {
    if (!story || openingRef.current || local.running || installing || library.issuing) return;
    openingRef.current = true; setOpening(true); setError('');
    try {
      const id = await loadGame(story.id, mode);
      if (mounted.current) navigate(`/game/${id}`);
    } catch (problem) {
      if (mounted.current) setError(problem instanceof Error ? problem.message : '开局失败，请重试');
    } finally { openingRef.current = false; if (mounted.current) setOpening(false); }
  };
  const install = async () => {
    if (!book) return;
    setView(current => current.filter === 'updates' ? { ...current, retainedIds: [...new Set([...current.retainedIds, book.id])] } : current);
    await library.issue(() => libraryApi.install(book));
  };
  if (!story) return <div className="mobile-page mobile-empty"><p>{!library.snapshot || local.loading ? '正在读取故事…' : '此故事尚未安装或已移除'}</p>
    {library.error && <p className="mobile-error" role="alert">{library.error}</p>}
    <Link className="btn btn-secondary" to="/library" replace>返回剧本库</Link></div>;
  return <div className="mobile-detail-page">
    <div className="mobile-detail-reading">
      <div className="mobile-detail-cover">{story.cover_url && failedImage !== story.cover_url
        ? <img src={story.cover_url} alt="" onError={() => setFailedImage(story.cover_url ?? '')} />
        : <span><BookOpen size={40} />原创案卷{!playable && <small>下载后可查看完整配图</small>}</span>}</div>
      <div className="mobile-page mobile-detail-copy"><h2>{story.title}</h2>
        <p className="mobile-note">{story.num_characters ? `${story.num_characters} 角色 · 你 + ${story.num_characters - 1} 位 AI` : '原创故事'}{story.difficulty && ` · ${story.difficulty}`}{story.estimated_minutes && ` · 约 ${story.estimated_minutes} 分钟`}</p>
        <p className="mobile-detail-summary">{story.summary || story.topic}</p>
        {book && hasBookUpdate(book) && <div className="mobile-update-note"><strong>可用新版 v{book.latest_version}</strong>
          <p>{book.release_notes || '正文或配图有更新。'}</p>
          {book.available?.title !== story.title && <p>新版标题：{book.available?.title}</p>}
          <p className="mobile-note">当前可开局版本为 v{book.installed_version}；已开始的游戏保留原版本。</p></div>}
        {book?.available && !book.compatible && <p className="mobile-note">新版需要升级应用。{playable ? '已安装版本仍可游玩。' : ''}</p>}
        {task && <MobileLibraryTask task={task} onCancel={id => void library.issue(() => libraryApi.cancel(id))} disabled={library.issuing} />}
        {library.error && <p className="mobile-error" role="alert">{library.error}</p>}
        {error && <p className="mobile-error" role="alert">{error}</p>}
        <details className="mobile-content-details"><summary>版本、作者与内容管理</summary>
          <p>{story.author || '个人故事'}</p>{story.license && <p>{story.license}</p>}
          <p>{book ? `已安装：${book.installed_version === null ? '尚未下载' : `v${book.installed_version}`} · 最新：v${book.latest_version}` : `个人剧本 · v${story.version ?? 1}`}</p>
          {book?.delivery === 'bundled' && <p>应用内置故事</p>}
          {book?.delivery === 'downloaded' && <><p>移除后保留旧局和配图，历史版本仍占用空间；有内置基础版时恢复基础版。</p>
            <button type="button" className="btn btn-ghost" disabled={library.issuing || !!installing || opening} onClick={async () => {
              if (await library.issue(() => libraryApi.remove(book.id))) {
                notify('已移除下载内容，旧局保留', 'success');
                if (mounted.current) navigate('/library', { replace: true });
              }
            }}>移除下载</button></>}
          {!book && <p>个人生成或导入的剧本，质量受来源与模型影响。</p>}
        </details>
      </div>
    </div>
    <div className="mobile-detail-actions">
      {playable && <MobileModeSelector value={mode} onChange={setMode} disabled={opening || local.running || !!installing || library.issuing} />}
      <p className="mobile-note">{local.running ? '有模型任务正在运行，请先在“我的”中查看。' : playable ? '成品直接开局；AI 对话需要模型密钥和网络。' : '下载包含正文和配图，不需要模型密钥。'}</p>
      <div className="mobile-detail-buttons">
        {playable && <button type="button" className="btn btn-primary" disabled={opening || local.running || !!installing || library.issuing} onClick={() => void begin()}><Play size={17} />{opening ? '正在开局…' : '开始游玩'}</button>}
        {book?.can_download && <button type="button" className={`btn ${playable ? 'btn-secondary' : 'btn-primary'}`} disabled={library.issuing || !!installing || opening} onClick={() => void install()}><Download size={17} />{playable ? '更新' : '下载剧本'}{book.download_bytes ? ` · ${contentSize(book.download_bytes)}` : ''}</button>}
        {!playable && !book?.can_download && !installing && <Link className="btn btn-secondary" to="/library" replace>返回剧本库</Link>}
      </div>
    </div>
  </div>;
}
