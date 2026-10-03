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
    return () => {
      mounted.current = false;
      cancelled = true;
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
    if (!topic.trim() || isCreating || isLoadingGame) return;
    setError(null);
    setGenerationStage('正在准备生成任务');
    setIsCreating(true);
    try {
      const gameId = await createGame(topic.trim(), undefined, mode);
      if (mounted.current) navigate(`/game/${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建游戏失败');
      setIsCreating(false);
    }
  };

  const handleLoadGame = async (storyId: string) => {
    if (isLoadingGame || isCreating) return;
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
          <h1>剧本杀</h1><p>一人入戏，寻找真相</p>
        </header> : <header className="case-masthead">
          <div className="masthead-dateline">
            <span>深夜第 1024 期 · 号外</span>
            <span>{DATELINE}</span>
            <span>全城独家 · 每夜发售</span>
          </div>
          <div className="masthead-row">
            <h1 className="home-logo font-display">剧本杀</h1>
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
        <div className="home-columns">
          <section className="home-col">
            <div className="home-section-head">
              <span className="giant-no" aria-hidden="true">
                01
              </span>
              <h2 className="home-section-title">
                <Sparkles size={18} className="home-create-icon" />
                今夜新剧
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
            <div className="home-mode-picker" role="group" aria-label="选择游戏模式">
              <button
                type="button"
                className={`home-mode-option${mode === 'quick' ? ' is-selected' : ''}`}
                onClick={() => setMode('quick')}
              >
                <span>速推模式</span>
                <small>三轮推进 · 三轮调查与讨论</small>
              </button>
              <button
                type="button"
                className={`home-mode-option${mode === 'classic' ? ' is-selected' : ''}`}
                onClick={() => setMode('classic')}
              >
                <span>经典模式</span>
                <small>自由调查 · 完整流程</small>
              </button>
            </div>

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
            className={`home-col home-stories-section${isCreating ? ' home-stories-section--dim' : ''}`}
          >
            <div className="home-section-head">
              <span className="giant-no" aria-hidden="true">
                02
              </span>
              <h3 className="home-section-title">
                <BookOpen size={18} />
                保留剧目
              </h3>
              <span className="head-fill" aria-hidden="true" />
            </div>

          {isLoadingGame && <LoadingSpinner size="sm" text="正在打开剧本…" />}
          {isLoadingStories ? (
            <div className="home-loading">
              <LoadingSpinner size="sm" text="加载中…" />
            </div>
          ) : storiesError ? (
            <Card className="home-empty-stories">
              <p>剧本列表加载失败</p>
              <span>{isAndroid ? '本地引擎未就绪，请重新打开应用' : '请确认后端服务已启动后刷新页面'}</span>
            </Card>
          ) : stories.length === 0 ? (
            <Card className="home-empty-stories">
              <p>暂无已有剧本</p>
              <span>创建一个新游戏开始你的推理之旅</span>
            </Card>
          ) : (
            <div className="shelf">
              {stories.map((story, i) => (
                <button
                  key={story.id}
                  className="shelf-book"
                  disabled={isLoadingGame || isCreating}
                  onClick={() => handleLoadGame(story.id)}
                >
                  <span className="shelf-book-idx" aria-hidden="true">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="shelf-book-main">
                    <span className="shelf-book-topic">{story.topic}</span>
                    <span className="shelf-book-title">{story.title}</span>
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
