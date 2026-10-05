// Home Page — 创建游戏 / 用已有剧本重新开局
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, BookOpen, Sparkles, AlertTriangle } from 'lucide-react';
import { useGame } from '../context/useGame';
import { api } from '../api/client';
import type { GameMode, Story } from '../api/types';
import { Button, Card, LoadingSpinner, useToast } from '../components/common';
import './HomePage.css';
import { isAndroid, type NativeTask } from '../api/native';
import { NativeHome } from '../components/common/NativeHome';
import { StoryLibrary } from '../components/story-library/StoryLibrary';

const EXAMPLE_TOPICS = [
  '豪华邮轮谋杀案',
  '古堡深夜的神秘死亡',
  '都市公寓中的毒杀',
  '密室中的摄影师之死',
];

/** 报头日期栏：今日日期 · 星期（报纸刊印惯例） */
const DATE_DATE = new Date().toLocaleDateString('zh-CN', {
  year: 'numeric',
  month: 'long',
  day: 'numeric',
});
const DATE_WEEKDAY = new Date().toLocaleDateString('zh-CN', { weekday: 'long' });
const DATELINE = `${DATE_DATE} ${DATE_WEEKDAY}`;

/** 誊录台工序清单 —— 卷Ⅰ 构思 / 卷Ⅱ 撰写（纯叙事，无真实进度语义） */
const STORY_WORKFLOW_STEPS = [
  '撰写案情与人物资料',
  '检查角色和线索结构',
  '审查真相与证据链',
  '必要时修补剧本',
  '保存成品并准备开场',
];

export function HomePage() {
  const navigate = useNavigate();
  const { createGame, loadGame } = useGame();
  const { notify } = useToast();
  const [libraryTab, setLibraryTab] = useState<'builtin' | 'personal' | 'generate'>('builtin');
  const [characterCount, setCharacterCount] = useState('');
  const [isImporting, setIsImporting] = useState(false);
  const [importError, setImportError] = useState('');
  const [topic, setTopic] = useState('');
  const [mode, setMode] = useState<GameMode>('quick');
  const [isLoadingGame, setIsLoadingGame] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [generationStage, setGenerationStage] = useState('正在准备生成任务');
  const [isLoadingStories, setIsLoadingStories] = useState(true);
  const [storiesError, setStoriesError] = useState(false);
  const [stories, setStories] = useState<Story[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [openingStory, setOpeningStory] = useState('');
  const [loadError, setLoadError] = useState<{ storyId: string; message: string } | null>(null);
  const timerRef = useRef<number | null>(null);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    (async () => {
      setIsLoadingStories(true);
      setStoriesError(false);
      try {
        const response = await api.listStories();
        if (!cancelled) setStories(response.stories);
      } catch {
        if (!cancelled) setStoriesError(true);
      } finally {
        if (!cancelled) setIsLoadingStories(false);
      }
    })();
    const onLibraryUpdate = () => {
      void api.listStories().then(response => { if (!cancelled) setStories(response.stories); }).catch(() => {
        if (!cancelled) setStoriesError(true);
      });
    };
    window.addEventListener('mystery:library-updated', onLibraryUpdate);
    return () => {
      mounted.current = false;
      cancelled = true;
      window.removeEventListener('mystery:library-updated', onLibraryUpdate);
    };
  }, []);

  // 生成剧本的等待计时
  useEffect(() => {
    if (!isCreating) return;
    setElapsed(0);
    timerRef.current = window.setInterval(() => {
      setElapsed((s) => s + 1);
    }, 1000);
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current);
    };
  }, [isCreating]);

  useEffect(() => {
    if (!isAndroid || !isCreating) return;
    const onProgress = (event: Event) => {
      const task = (event as CustomEvent<NativeTask>).detail;
      if (task.endpoint === '/games' && task.progress) setGenerationStage(task.progress.label);
    };
    window.addEventListener('mystery:task-progress', onProgress);
    return () => window.removeEventListener('mystery:task-progress', onProgress);
  }, [isCreating]);

  const handleCreateGame = async () => {
    if (!topic.trim() || isCreating || isLoadingGame || isImporting) return;
    setError(null);
    setGenerationStage('正在准备生成任务');
    setIsCreating(true);
    try {
      const gameId = await createGame(topic.trim(), undefined, mode, characterCount ? Number(characterCount) : undefined);
      if (mounted.current) navigate(`/game/${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建游戏失败');
      setIsCreating(false);
    }
  };

  const handleLoadGame = async (storyId: string) => {
    if (isLoadingGame || isCreating || isImporting) return;
    setIsLoadingGame(true);
    setOpeningStory(storyId);
    setLoadError(null);
    try {
      const gameId = await loadGame(storyId, mode);
      if (mounted.current) navigate(`/game/${gameId}`);
    } catch (err) {
      const message = err instanceof Error ? err.message : '开局失败';
      setLoadError({ storyId, message });
      notify(message, 'error');
    } finally { setIsLoadingGame(false); }
  };

  return (
    <div className="home-page">
      <div className="home-content stage-paper">
        {isAndroid ? <header className="mobile-home-header">
          <h1 className="home-brand-title"><img className="brand-icon" src="/brand/logo-casefile-v2.png" width="40" height="40" alt="" />剧本杀</h1><p>一人入戏，寻找真相</p>
        </header> : <header className="case-masthead">
          <div className="masthead-dateline">
            <span>深夜第 1024 期 · 号外</span>
            <span>{DATELINE}</span>
            <span>全城独家 · 每夜发售</span>
          </div>
          <div className="masthead-row">
            <h1 className="home-logo home-brand-title font-display"><img className="brand-icon" src="/brand/logo-casefile-v2.png" width="40" height="40" alt="" />剧本杀</h1>
            <span className="extra-stamp" aria-hidden="true">
              号外 EXTRA
            </span>
          </div>
          <div className="masthead-sub">
            <span>MURDER MYSTERY GAME</span>
            <span>今夜开演 · 全 AI 班底</span>
          </div>
          <p className="home-tagline">
            一人入戏 · 众 AI 同台 · <em>真相只有一个</em>
          </p>
        </header>}

        {isAndroid && <NativeHome hideTasks={isCreating} />}
        <div className="home-mode-picker" role="group" aria-label="选择游戏模式">
              <button
                type="button"
                className={`home-mode-option${mode === 'quick' ? ' is-selected' : ''}`}
                disabled={isCreating || isLoadingGame || isImporting}
                onClick={() => setMode('quick')}
              >
                <span>速推模式</span>
                <small>三轮推进 · 三轮调查与讨论</small>
              </button>
              <button
                type="button"
                className={`home-mode-option${mode === 'classic' ? ' is-selected' : ''}`}
                disabled={isCreating || isLoadingGame || isImporting}
                onClick={() => setMode('classic')}
              >
                <span>经典模式</span>
                <small>自由调查 · 完整流程</small>
              </button>
            </div>
        <nav className="library-tabs" aria-label="选择剧本来源">
          {([['builtin', '精选剧本'], ['personal', '我的剧本'], ['generate', '自行生成']] as const).map(([value, label]) =>
            <button key={value} type="button" aria-pressed={libraryTab === value} disabled={isCreating || isLoadingGame || isImporting}
              onClick={() => setLibraryTab(value)}>{label}</button>)}
        </nav>
        <div className="home-columns home-columns--library">
          <section className="home-col" hidden={libraryTab !== 'generate'}>
            <div className="home-section-head">
              <span className="giant-no" aria-hidden="true">
                01
              </span>
              <h2 className="home-section-title">
                <Sparkles size={18} className="home-create-icon" />
                自行生成
              </h2>
              <span className="head-fill" aria-hidden="true" />
            </div>

        {isCreating ? (
            <div className="home-gendesk" role="status">
              <div className="home-gendesk-kicker">
                <span className="home-gendesk-lamp" aria-hidden="true" />
                午夜剧场 · 正在装台
              </div>

              <p className="home-gendesk-stage">
                {isAndroid ? '任务已保存 · 正在制作' : '正在制作新案件'}
              </p>
              <h2 className="home-gendesk-title">
                {isAndroid ? generationStage : '正在生成并检查剧本'}
                <span className="home-gendesk-caret" aria-hidden="true" />
              </h2>
              <p className="home-gendesk-topic">本案主题 ·{topic}</p>

              <div
                className="home-gendesk-ledger"
                aria-hidden="true"
              >
                {STORY_WORKFLOW_STEPS.map(
                  (step, i) => (
                    <div className="ledger-row" key={step}>
                      <span className="ledger-row-num">
                        {String(i + 1).padStart(2, '0')}
                      </span>
                      <span className="ledger-row-text">{step}</span>
                      <span className="ledger-row-dot" aria-hidden="true" />
                    </div>
                  ),
                )}
              </div>

              <div className="home-gendesk-foot">
                <span className="home-gendesk-note">
                  {isAndroid ? '请保持前台；中断后可在首页继续任务' : '正在等待制作结果，完成后自动进入游戏'}
                </span>
                <span className="timecode home-gendesk-timecode">
                  {isAndroid ? '已用时 ' : 'T+'}{Math.floor(elapsed / 60)}分
                  {String(elapsed % 60).padStart(2, '0')}秒
                </span>
              </div>
            </div>
          ) : (
          <Card className="home-create-card" variant="gold-border">


            <p className="library-note">AI 生成适合探索自定义题材，质量受模型影响，可能出现逻辑或人物表现不稳定。首次游玩推荐精选剧本。</p>
            <label className="library-count">角色数量（含你扮演的 1 人，不含受害者）
              <select value={characterCount} onChange={e => setCharacterCount(e.target.value)}>
                <option value="">根据故事自动决定 · 3—8 人</option>
                {[3, 4, 5, 6, 7, 8].map(count => <option key={count} value={count}>{count} 人 · {count - 1} 位 AI</option>)}
              </select>
            </label>
            <p className="library-note">人数更多会增加生成篇幅和全员讨论的 API 消耗；游玩时可以定向询问。</p>
            <div className="home-input-group">
                <input
                  type="text"
                  className="home-input"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  placeholder="输入剧本主题，如：豪华邮轮谋杀案"
                  maxLength={100}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.nativeEvent.isComposing) {
                      handleCreateGame();
                    }
                  }}
                />
                <Button
                  variant="primary"
                  onClick={handleCreateGame}
                  disabled={!topic.trim() || isLoadingGame}
                  className="home-create-btn"
                >
                  <Play size={16} />
                  揭幕开演
                </Button>
              </div>

              {error && (
                <p className="home-error" role="alert">
                  <AlertTriangle size={14} />
                  {error}
                </p>
              )}

              <div className="home-examples">
                <span className="home-examples-label">备选剧目：</span>
                <div className="home-examples-list">
                  {EXAMPLE_TOPICS.map((t) => (
                    <button
                      key={t}
                      className="home-example-btn"
                      onClick={() => setTopic(t)}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </Card>
        )}
          </section>

          <section
            hidden={libraryTab === 'generate'}
            className={`home-col home-stories-section${isCreating ? ' home-stories-section--dim' : ''}`}
          >
            <div className="home-section-head">
              <span className="giant-no" aria-hidden="true">
                02
              </span>
              <h3 className="home-section-title">
                <BookOpen size={18} />
                {libraryTab === 'builtin' ? '精选剧本' : '我的剧本'}
              </h3>
              <span className="head-fill" aria-hidden="true" />
            </div>

          <p className="library-note">{libraryTab === 'builtin' ? '原创成品 · 无需等待生成或再次审稿。AI 对话仍需联网及 API key。' : '这里保留自行生成、导入与旧版剧本。导入包仅做本地结构检查，不代表通过精选内容验收。'}</p>
          {isLoadingGame && <LoadingSpinner size="sm" text="正在打开剧本…" />}
          {isAndroid && libraryTab === 'builtin' ? <StoryLibrary disabled={isLoadingGame || isCreating || isImporting}
            openingStory={openingStory} loadError={loadError} onOpen={id => { void handleLoadGame(id); }} /> : isLoadingStories ? (
            <div className="home-loading">
              <LoadingSpinner size="sm" text="加载中…" />
            </div>
          ) : storiesError ? (
            <Card className="home-empty-stories">
              <p>剧本列表加载失败</p>
              <span>{isAndroid ? '本地引擎未就绪，请重新打开应用' : '请确认后端服务已启动后刷新页面'}</span>
            </Card>
          ) : stories.filter(story => (story.origin === 'builtin') === (libraryTab === 'builtin')).length === 0 ? (
            <Card className="home-empty-stories">
              <p>暂无此类剧本</p>
              <span>可切换精选剧本，或生成、导入新故事</span>
            </Card>
          ) : (
            <div className="shelf">
              {stories.filter(story => (story.origin === 'builtin') === (libraryTab === 'builtin')).map((story, i) => (
                <button
                  key={story.id}
                  className={`shelf-book${story.cover_url ? ' shelf-book--illustrated' : ''}`}
                  disabled={isLoadingGame || isCreating || isImporting}
                  onClick={() => handleLoadGame(story.id)}
                >
                  {story.cover_url && <img className="shelf-book-cover" src={story.cover_url} alt="" loading="lazy" />}
                  <span className="shelf-book-idx" aria-hidden="true">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="shelf-book-main">
                    <span className="shelf-book-topic">{story.topic}</span>
                    <span className="shelf-book-title">{story.title}</span>
                    {story.summary && <span className="library-summary">{story.summary}</span>}
                    <span className="library-facts">{story.num_characters ?? '—'} 角色 · 你 + {(story.num_characters ?? 1) - 1} 位 AI
                      {story.difficulty && ` · ${story.difficulty}`}{story.estimated_minutes && ` · 约 ${story.estimated_minutes} 分钟`}</span>
                    {story.author && <span className="library-credit">{story.author} · 版本 {story.version ?? 1}</span>}
                    <span>{isLoadingGame && openingStory === story.id ? '正在开局…' : '新开一局 →'}</span>
                    {loadError?.storyId === story.id && <span className="home-error" role="alert">{loadError.message}</span>}
                  </span>
                  <span className="shelf-book-meta">
                    <Clock size={11} />
                    {new Date(story.created_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          )}

          <div className="library-import">
            <label>导入剧本包（JSON，最多 2 MB）
              <input type="file" accept=".json,application/json" disabled={isCreating || isLoadingGame || isImporting} onChange={async e => {
                const file = e.currentTarget.files?.[0];
                e.currentTarget.value = '';
                if (!file) return;
                setImportError('');
                setIsImporting(true);
                try {
                  if (file.size > 2 * 1024 * 1024) throw new Error('剧本包不能超过 2 MB');
                  const packageData: unknown = JSON.parse(await file.text());
                  await api.importStory(packageData);
                  const response = await api.listStories();
                  if (mounted.current) { setStories(response.stories); setLibraryTab('personal'); }
                  notify('剧本包已安装；正在进行的游戏保留原版本', 'success');
                } catch (err) {
                  setImportError(err instanceof Error ? err.message : '导入失败');
                } finally { setIsImporting(false); }
              }} />
            </label>
            {isImporting && <LoadingSpinner size="sm" text="正在检查并安装剧本包…" />}
            {importError && <p className="home-error" role="alert">{importError}</p>}
          </div>
          <aside className="home-editorial">
            <p>
              真相
              <br />
              <em>只有一个</em>
            </p>
            <small>本报评论 · 头版社论</small>
          </aside>
        </section>
        </div>
      </div>

      <footer className="home-footer">
        <p>多智能体剧本杀系统 · AI 扮演所有 NPC</p>
      </footer>
    </div>
  );
}
