// Home Page — 创建游戏 / 用已有剧本重新开局
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, BookOpen, Sparkles, AlertTriangle } from 'lucide-react';
import { useGame } from '../context/GameContext';
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
      <div className="home-hero">
        <div className="case-cover">
          <p className="case-cover-kicker">名案档案馆 · 卷宗登记</p>
          <h1 className="home-logo font-display">剧本杀</h1>
          <p className="home-tagline">
            沉浸式推理体验 · 多智能体协作 · 真相只有一个
          </p>
          <div className="case-cover-string" aria-hidden="true" />
        </div>
      </div>

      <div className="home-content">
        <Card className="home-create-card" variant="gold-border">
          <div className="home-create-header">
            <Sparkles size={20} className="home-create-icon" />
            <h2>新案登记</h2>
          </div>

          {isCreating ? (
            <div className="home-generating" role="status">
              <LoadingSpinner size="md" />
              <p className="home-generating-stage">
                {elapsed < 40 ? 'STAGE Ⅰ · 构思' : 'STAGE Ⅱ · 撰写'}
              </p>
              <p className="home-generating-title">
                {elapsed < 40 ? '正在构思案情…' : '正在撰写卷宗…'}
              </p>
              <p className="home-generating-hint">
                {elapsed < 40
                  ? 'AI 正在推演人物关系、动机与核心诡计，通常需要 1-2 分钟'
                  : '正在落笔人物档案与线索，即将归档开卷'}
              </p>
              <p className="timecode home-generating-timecode">
                T+{Math.floor(elapsed / 60)}分
                {String(elapsed % 60).padStart(2, '0')}秒
              </p>
            </div>
          ) : (
            <>
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
            </>
          )}
        </Card>

        <div className="home-stories-section">
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
