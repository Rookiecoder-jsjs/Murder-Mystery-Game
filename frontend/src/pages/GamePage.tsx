// Game Page — 从 /game/:gameId 续局 + 单一轮询持有者
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../context/GameContext';
import { apiErrorStatus } from '../api/client';
import { GameLayout } from '../components/layout';
import { IntroductionPhase } from '../components/introduction';
import { InvestigationPhase } from '../components/investigation';
import { DiscussionPhase } from '../components/discussion';
import { VotingPhase } from '../components/voting';
import { RevealPhase } from '../components/reveal';
import { Button, LoadingSpinner, useToast } from '../components/common';
import './GamePage.css';

const POLL_FAST_MS = 3000; // 讨论阶段
const POLL_SLOW_MS = 5000;
const FAILURES_BEFORE_BANNER = 3;

export function GamePage() {
  const navigate = useNavigate();
  const { gameId: routeGameId } = useParams<{ gameId: string }>();
  const { notify } = useToast();
  const {
    state,
    resumeGame,
    refreshStatus,
    refreshClues,
    setConnectionLost,
  } = useGame();

  const failuresRef = useRef(0);
  const [resumeError, setResumeError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);
  const isSameGame = Boolean(routeGameId) && state.gameId === routeGameId;

  // 进入页面时若 URL 的 id 与内存不一致则续局（刷新/分享链接）
  useEffect(() => {
    if (!routeGameId) {
      navigate('/', { replace: true });
      return;
    }
    if (state.gameId === routeGameId) return; // 已在本局
    let cancelled = false;
    setResumeError(null);
    resumeGame(routeGameId).catch((err: unknown) => {
      if (cancelled) return;
      if (apiErrorStatus(err) === 404) {
        notify('找不到这局游戏，可能已随后端重启丢失', 'error');
        navigate('/', { replace: true });
      } else {
        setResumeError(err instanceof Error ? err.message : '加载失败');
      }
    });
    return () => {
      cancelled = true;
    };
  }, [routeGameId, state.gameId, resumeGame, navigate, notify, retryTick]);

  // 单一轮询：揭晓/结束后停止；连续失败达到阈值提示断连
  useEffect(() => {
    if (!isSameGame || state.gameEnded || state.phase === 'reveal') {
      return;
    }
    const intervalId = window.setInterval(async () => {
      const ok = await refreshStatus();
      if (ok) {
        failuresRef.current = 0;
        setConnectionLost(false);
        if (state.phase === 'investigation') {
          refreshClues();
        }
      } else {
        failuresRef.current += 1;
        if (failuresRef.current >= FAILURES_BEFORE_BANNER) {
          setConnectionLost(true);
        }
      }
    }, state.phase === 'discussion' ? POLL_FAST_MS : POLL_SLOW_MS);

    return () => window.clearInterval(intervalId);
  }, [
    isSameGame,
    state.gameEnded,
    state.phase,
    refreshStatus,
    refreshClues,
    setConnectionLost,
  ]);

  if (!isSameGame) {
    if (resumeError) {
      return (
        <div className="game-loading">
          <div className="game-resume-error" role="alert">
            <p>{resumeError}</p>
            <div className="game-resume-error-actions">
              <Button variant="primary" onClick={() => setRetryTick((t) => t + 1)}>
                重试
              </Button>
              <Button variant="ghost" onClick={() => navigate('/', { replace: true })}>
                返回首页
              </Button>
            </div>
          </div>
        </div>
      );
    }
    return (
      <div className="game-loading">
        <LoadingSpinner size="lg" text="加载游戏中…" />
      </div>
    );
  }

  const renderPhase = () => {
    switch (state.phase) {
      case 'introduction':
        return <IntroductionPhase />;
      case 'investigation':
        return <InvestigationPhase />;
      case 'discussion':
        return <DiscussionPhase />;
      case 'voting':
        return <VotingPhase />;
      case 'reveal':
        return <RevealPhase />;
      default:
        return <IntroductionPhase />;
    }
  };

  return (
    <GameLayout>
      <div className="game-page">{renderPhase()}</div>
    </GameLayout>
  );
}
