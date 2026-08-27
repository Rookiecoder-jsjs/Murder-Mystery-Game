// Home Page — 创建游戏 / 用已有剧本重新开局
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, BookOpen, Sparkles, AlertTriangle } from 'lucide-react';
import { useGame } from '../context/useGame';
import { api } from '../api/client';
import type { Story } from '../api/types';
import { Button, Card, LoadingSpinner } from '../components/common';
import './HomePage.css';

const EXAMPLE_TOPICS = [
  '豪华邮轮谋杀案',
  '古堡深夜的神秘死亡',
  '都市公寓中的毒杀',
  '密室中的摄影师之死',
];

/** 誊录台工序清单 —— 卷Ⅰ 构思 / 卷Ⅱ 撰写（纯叙事，无真实进度语义） */
const STAGE_ONE_STEPS = [
  '人物立案 · 身份与容貌',
  '关系推演 · 受害者的人际网',
  '动机暗线 · 深层心理',
  '核心诡计 · 时差 / 密室 / 身份替换',
  '审判席核验 · 谁最可疑',
];

const STAGE_TWO_STEPS = [
  '人物档案誊录',
  '线索归档 · 物证 / 人证 / 旁证',
  '时间线复原 · 真相串联',
  '证据链核验 · 逐一指向',
  '密封归档 · 等待朱印落款',
];

export function HomePage() {
  const navigate = useNavigate();
  const { createGame, loadGame } = useGame();
  const [topic, setTopic] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [isLoadingStories, setIsLoadingStories] = useState(true);
  const [storiesError, setStoriesError] = useState(false);
  const [stories, setStories] = useState<Story[]>([]);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
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

  const handleCreateGame = async () => {
    if (!topic.trim() || isCreating) return;
    setError(null);
    setIsCreating(true);
    try {
      const gameId = await createGame(topic.trim());
      navigate(`/game/${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建游戏失败');
      setIsCreating(false);
    }
  };

  const handleLoadGame = async (storyId: string) => {
    setError(null);
    try {
      const gameId = await loadGame(storyId);
      navigate(`/game/${gameId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载游戏失败');
    }
  };

  return (
    <div className="home-page">
      <div className="home-content stage-paper">
        <div className="case-cover">
          <p className="case-cover-kicker">名案档案馆 · 卷宗登记</p>
          <h1 className="home-logo font-display">剧本杀</h1>
          <p className="home-tagline">
            沉浸式推理体验 · 多智能体协作 · 真相只有一个
          </p>
          <div className="case-cover-string" aria-hidden="true" />
          <span className="seal case-cover-seal" aria-hidden="true">
            壹
          </span>
        </div>

        {isCreating ? (
            <div className="home-gendesk" role="status">
              <div className="home-gendesk-kicker">
                <span className="home-gendesk-lamp" aria-hidden="true" />
                名案档案馆 · 卷宗调取
              </div>

              <p className="home-gendesk-stage">
                {elapsed < 40 ? '卷壹 · 构思案情' : '卷贰 · 撰写卷宗'}
              </p>
              <h2 className="home-gendesk-title">
                {elapsed < 40 ? '正在推演人物与诡计' : '正在誊录本案卷宗'}
                <span className="home-gendesk-caret" aria-hidden="true" />
              </h2>
              <p className="home-gendesk-topic">本案主题 ·{topic}</p>

              <div
                className="home-gendesk-ledger"
                key={elapsed < 40 ? 'gen-stage-1' : 'gen-stage-2'}
                aria-hidden="true"
              >
                {(elapsed < 40 ? STAGE_ONE_STEPS : STAGE_TWO_STEPS).map(
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
                  AI 正在逐本誊录，通常 1–2 分钟
                </span>
                <span className="timecode home-gendesk-timecode">
                  T+{Math.floor(elapsed / 60)}分
                  {String(elapsed % 60).padStart(2, '0')}秒
                </span>
              </div>
            </div>
          ) : (
          <Card className="home-create-card" variant="gold-border">
            <div className="home-create-header">
              <Sparkles size={20} className="home-create-icon" />
              <h2>新案登记</h2>
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
                  disabled={!topic.trim()}
                  className="home-create-btn"
                >
                  <Play size={16} />
                  提交登记
                </Button>
              </div>

              {error && (
                <p className="home-error" role="alert">
                  <AlertTriangle size={14} />
                  {error}
                </p>
              )}

              <div className="home-examples">
                <span className="home-examples-label">试试这些主题：</span>
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

        <div
          className={`home-stories-section${isCreating ? ' home-stories-section--dim' : ''}`}
        >
          <div className="home-section-header">
            <BookOpen size={18} />
            <h3>旧案卷宗</h3>
          </div>

          {isLoadingStories ? (
            <div className="home-loading">
              <LoadingSpinner size="sm" text="加载中…" />
            </div>
          ) : storiesError ? (
            <Card className="home-empty-stories">
              <p>剧本列表加载失败</p>
              <span>请确认后端服务已启动后刷新页面</span>
            </Card>
          ) : stories.length === 0 ? (
            <Card className="home-empty-stories">
              <p>暂无已有剧本</p>
              <span>创建一个新游戏开始你的推理之旅</span>
            </Card>
          ) : (
            <div className="shelf">
              {stories.map((story) => (
                <button
                  key={story.id}
                  className="shelf-book"
                  onClick={() => handleLoadGame(story.id)}
                >
                  <span className="shelf-book-topic">{story.topic}</span>
                  <span className="shelf-book-title">{story.title}</span>
                  <span className="shelf-book-meta">
                    <Clock size={11} />
                    {new Date(story.created_at).toLocaleDateString()}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      <footer className="home-footer">
        <p>多智能体剧本杀系统 · AI 扮演所有 NPC</p>
      </footer>
    </div>
  );
}
