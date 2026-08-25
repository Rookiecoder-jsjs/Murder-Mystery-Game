// Discussion Phase — 聊天布局由外壳决定高度，列表内部滚动
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { MessageSquare, Send, Vote, ArrowRight, Search, AlertTriangle } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, AccuseModal, TypingIndicator, useToast } from '../common';
import { ChatMessage } from './ChatMessage';
import './DiscussionPhase.css';

export function DiscussionPhase() {
  const {
    state,
    speak,
    startVoting,
    accuse,
    returnToInvestigation,
    refreshDiscussionHistory,
  } = useGame();
  const { notify } = useToast();
  const [message, setMessage] = useState('');
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [showAccuseModal, setShowAccuseModal] = useState(false);
  const [isAccusing, setIsAccusing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const isSpeaking = state.isSpeaking;
  const playerName = state.player?.name;

  // 角色名 → 角色信息（避免每条消息都 find 一遍）
  const characterByName = useMemo(
    () => new Map(state.characters.map((c) => [c.name, c])),
    [state.characters],
  );

  // 进入阶段时若本地无消息，拉取持久化的讨论记录
  useEffect(() => {
    if (state.currentDiscussionMessages.length === 0) {
      refreshDiscussionHistory();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.currentDiscussionMessages.length, isSpeaking]);

  const handleSend = async () => {
    const text = message.trim();
    if (!text || isSpeaking) return;
    setMessage('');
    await speak(text);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // isComposing：中文输入法组词期间的回车不发送
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTransitionToVoting = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try {
      await startVoting();
    } catch (err) {
      notify(err instanceof Error ? err.message : '进入投票失败', 'error');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleReturnToInvestigation = async () => {
    if (isTransitioning) return;
    setIsTransitioning(true);
    try {
      await returnToInvestigation();
    } catch (err) {
      notify(err instanceof Error ? err.message : '返回搜证失败', 'error');
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleAccuse = async (characterName: string) => {
    if (isAccusing) return;
    setIsAccusing(true);
    try {
      const result = await accuse(characterName);
      setShowAccuseModal(false);
      notify(result.message, result.correct ? 'success' : 'error');
    } catch (err) {
      notify(err instanceof Error ? err.message : '指认失败', 'error');
    } finally {
      setIsAccusing(false);
    }
  };

  return (
    <div className="discussion-phase">
      <div className="discussion-topbar">
        <div className="discussion-topbar-title">
          <MessageSquare size={18} />
          <h2>讨论阶段</h2>
          <span className="discussion-round">
            回合 {state.round} / {state.maxRounds}
          </span>
        </div>
        <div className="discussion-actions">
          {state.accusationPoints > 0 && (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setShowAccuseModal(true)}
              className="discussion-action"
            >
              <AlertTriangle size={14} />
              指认凶手（{state.accusationPoints}）
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleReturnToInvestigation}
            isLoading={isTransitioning}
            className="discussion-action"
          >
            <Search size={14} />
            返回搜证
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleTransitionToVoting}
            isLoading={isTransitioning}
            className="discussion-action"
          >
            <Vote size={14} />
            进入投票
            <ArrowRight size={14} />
          </Button>
        </div>
      </div>

      <div className="discussion-messages">
        {state.currentDiscussionMessages.length === 0 ? (
          <div className="discussion-empty">
            <MessageSquare size={40} />
            <p>还没有发言</p>
            <span>开始讨论，发表你的看法</span>
          </div>
        ) : (
          state.currentDiscussionMessages.map((msg, index) => (
            <ChatMessage
              key={`${msg.speaker}-${index}`}
              message={msg}
              isPlayer={msg.speaker === playerName}
              character={characterByName.get(msg.speaker)}
            />
          ))
        )}
        {isSpeaking && <TypingIndicator label="角色们正在思考回应" />}
        <div ref={messagesEndRef} />
      </div>

      <div className="discussion-input-area">
        <div className="discussion-input-wrapper">
          <textarea
            className="discussion-input"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入你的发言…"
            rows={2}
            maxLength={500}
            disabled={isSpeaking}
          />
          <Button
            variant="primary"
            onClick={handleSend}
            isLoading={isSpeaking}
            disabled={!message.trim()}
            className="discussion-send-btn"
            aria-label="发送"
          >
            <Send size={16} />
          </Button>
        </div>
        <p className="discussion-hint">Enter 发送 · Shift+Enter 换行</p>
      </div>

      <AccuseModal
        isOpen={showAccuseModal}
        onClose={() => setShowAccuseModal(false)}
        characters={state.characters}
        playerId={state.player?.id}
        accusationPoints={state.accusationPoints}
        isAccusing={isAccusing}
        onConfirm={handleAccuse}
      />
    </div>
  );
}
