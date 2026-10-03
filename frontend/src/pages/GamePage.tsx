// Game Page — 从 /game/:gameId 续局 + 单一轮询持有者
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../context/useGame';
import { apiErrorStatus } from '../api/client';
import { GameLayout } from '../components/layout';
import { IntroductionPhase } from '../components/introduction';
import { InvestigationPhase } from '../components/investigation';
import { DiscussionPhase } from '../components/discussion';
import { VotingPhase } from '../components/voting';
import { RevealPhase } from '../components/reveal';
import { Button, LoadingSpinner, useToast } from '../components/common';
import './GamePage.css';
import { GameTaskPanel } from '../components/common/GameTaskPanel';

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
  const [resumeError, setResumeError] = useState<{
    gameId: string;
    message: string;
  } | null>(null);
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
    resumeGame(routeGameId).catch((err: unknown) => {
      if (cancelled) return;
      if (apiErrorStatus(err) === 404) {
        notify('找不到这局游戏，请从首页选择已有存档', 'error');
        navigate('/', { replace: true });
      } else {
        setResumeError({
          gameId: routeGameId,
          message: err instanceof Error ? err.message : '加载失败',
        });
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
    let cancelled = false;
    let running = false;
    let timer: number | undefined;
    const delay = state.phase === 'discussion' ? POLL_FAST_MS : POLL_SLOW_MS;
    const poll = async () => {
      if (cancelled || running || document.hidden) return;
      window.clearTimeout(timer);
      running = true;
      try {
        const ok = await refreshStatus();
        if (cancelled) return;
        if (ok) {
          failuresRef.current = 0;
          setConnectionLost(false);
          if (state.phase === 'investigation') await refreshClues();
        } else if (++failuresRef.current >= FAILURES_BEFORE_BANNER) {
          setConnectionLost(true);
        }
      } finally {
        running = false;
        if (!cancelled && !document.hidden) timer = window.setTimeout(() => void poll(), delay);
      }
    };
    const resume = () => { if (!document.hidden) void poll(); };
    timer = window.setTimeout(() => void poll(), delay);
    window.addEventListener('mystery:resume', resume);
    document.addEventListener('visibilitychange', resume);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      window.removeEventListener('mystery:resume', resume);
      document.removeEventListener('visibilitychange', resume);
    };
  }, [
    isSameGame,
    state.gameEnded,
    state.phase,
    refreshStatus,
    refreshClues,
    setConnectionLost,
  ]);

  if (!isSameGame) {
    const currentResumeError =
      resumeError && resumeError.gameId === routeGameId
        ? resumeError.message
        : null;
    if (currentResumeError) {
      return (
        <div className="game-loading">
          <div className="game-resume-error" role="alert">
            <p>{currentResumeError}</p>
            <div className="game-resume-error-actions">
              <Button
                variant="primary"
                onClick={() => {
                  setResumeError(null);
                  setRetryTick((t) => t + 1);
                }}
              >
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
      <GameTaskPanel />
      <div className="game-page">{renderPhase()}</div>
    </GameLayout>
  );
}
