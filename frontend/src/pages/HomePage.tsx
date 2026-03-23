// Home Page - Game selection and creation
import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Play, Clock, BookOpen, Sparkles } from 'lucide-react';
import { useGame } from '../context/GameContext';
import { api } from '../api/client';
import { Button, Card, LoadingSpinner } from '../components/common';
import './HomePage.css';

interface StorySummary {
  id: string;
  title: string;
  topic: string;
  created_at: string;
}

export function HomePage() {
  const navigate = useNavigate();
  const { createGame, loadGame } = useGame();
  const [topic, setTopic] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isLoadingStories, setIsLoadingStories] = useState(true);
  const [stories, setStories] = useState<StorySummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadStories();
  }, []);

  const loadStories = async () => {
    setIsLoadingStories(true);
    try {
      const response = await api.listStories();
      setStories(response.stories);
    } catch (err) {
      console.error('Failed to load stories:', err);
    } finally {
      setIsLoadingStories(false);
    }
  };

  const handleCreateGame = async () => {
    if (!topic.trim()) {
      setError('请输入剧本主题');
      return;
    }
    setError(null);
    setIsCreating(true);
    try {
      await createGame(topic.trim());
      navigate('/game');
    } catch (err) {
      setError(err instanceof Error ? err.message : '创建游戏失败');
    } finally {
      setIsCreating(false);
    }
  };

  const handleLoadGame = async (storyId: string) => {
    setError(null);
    try {
      await loadGame(storyId);
      navigate('/game');
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载游戏失败');
    }
  };

  const exampleTopics = [
    '豪华邮轮谋杀案',
    '古堡深夜的神秘死亡',
    '都市公寓中的毒杀',
    '密室中的摄影师之死',
  ];

  return (
    <div className="home-page">
      <div className="home-hero">
        <div className="home-hero-content">
          <div className="home-logo">
            <span className="home-logo-accent">剧本</span>杀
          </div>
          <p className="home-tagline">
            沉浸式推理体验 · 多智能体协作 · 真相只有一个
          </p>
        </div>
        <div className="home-hero-decoration"></div>
      </div>

      <div className="home-content">
        <Card className="home-create-card" variant="gold-border">
          <div className="home-create-header">
            <Sparkles size={24} className="home-create-icon" />
            <h2>创建新游戏</h2>
          </div>

          <div className="home-input-group">
            <input
              type="text"
              className="home-input"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="输入剧本主题，如：豪华邮轮谋杀案"
              onKeyPress={(e) => e.key === 'Enter' && handleCreateGame()}
            />
            <Button
              variant="primary"
              onClick={handleCreateGame}
              isLoading={isCreating}
              disabled={!topic.trim()}
              className="home-create-btn"
            >
              <Play size={18} />
              开始游戏
            </Button>
          </div>

          {error && <p className="home-error">{error}</p>}

          <div className="home-examples">
            <span className="home-examples-label">试试这些主题：</span>
            <div className="home-examples-list">
              {exampleTopics.map((t) => (
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

        <div className="home-stories-section">
          <div className="home-section-header">
            <BookOpen size={20} />
            <h3>已有剧本</h3>
          </div>

          {isLoadingStories ? (
            <div className="home-loading">
              <LoadingSpinner text="加载中..." />
            </div>
          ) : stories.length === 0 ? (
            <Card className="home-empty-stories">
              <p>暂无已有剧本</p>
              <span>创建一个新游戏开始你的推理之旅</span>
            </Card>
          ) : (
            <div className="home-stories-grid">
              {stories.map((story) => (
                <Card
                  key={story.id}
                  className="home-story-card"
                  variant="default"
                  hoverable
                  onClick={() => handleLoadGame(story.id)}
                >
                  <div className="home-story-icon">
                    <BookOpen size={24} />
                  </div>
                  <div className="home-story-info">
                    <h4 className="home-story-title">{story.title}</h4>
                    <p className="home-story-topic">{story.topic}</p>
                    <div className="home-story-meta">
                      <Clock size={12} />
                      <span>{new Date(story.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" className="home-story-play">
                    <Play size={14} />
                  </Button>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>

      <footer className="home-footer">
        <p>基于 CAMEL 框架的多智能体剧本杀系统</p>
      </footer>
    </div>
  );
}
