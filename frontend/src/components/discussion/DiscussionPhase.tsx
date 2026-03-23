// Discussion Phase Component
import { useState, useRef, useEffect, type KeyboardEvent } from 'react';
import { MessageSquare, Send, Vote, ArrowRight, Search, AlertTriangle, Check } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Avatar, Modal, Badge } from '../common';
import { ChatMessage } from './ChatMessage';
import './DiscussionPhase.css';

export function DiscussionPhase() {
  const { state, speak, startVoting, accuse, returnToInvestigation } = useGame();
  const [message, setMessage] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [showAccuseModal, setShowAccuseModal] = useState(false);
  const [selectedSuspect, setSelectedSuspect] = useState<string | null>(null);
  const [isAccusing, setIsAccusing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [state.currentDiscussionMessages]);

  const handleSend = async () => {
    if (!message.trim() || isSending) return;
    setIsSending(true);
    try {
      await speak(message.trim());
      setMessage('');
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyPress = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleTransitionToVoting = async () => {
    setIsTransitioning(true);
    try {
      await startVoting();
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleReturnToInvestigation = async () => {
    setIsTransitioning(true);
    try {
      await returnToInvestigation();
    } catch (err) {
      console.error('Failed to return to investigation:', err);
    } finally {
      setIsTransitioning(false);
    }
  };

  const handleAccuse = async () => {
    if (!selectedSuspect) return;
    setIsAccusing(true);
    try {
      await accuse(selectedSuspect);
      setShowAccuseModal(false);
    } catch (err) {
      console.error('Accuse failed:', err);
    } finally {
      setIsAccusing(false);
    }
  };

  // Get all characters including player for accusation display
  const allCharactersForDisplay = state.characters;

  return (
    <div className="discussion-phase">
      <div className="discussion-header">
        <div className="discussion-icon">
          <MessageSquare size={32} />
        </div>
        <h2 className="discussion-title">讨论阶段</h2>
        <p className="discussion-subtitle">
          回合 {state.round} / {state.maxRounds} - 与其他角色交流
        </p>
      </div>

      <Card className="discussion-chat-card">
        <div className="discussion-messages">
          {state.currentDiscussionMessages.length === 0 ? (
            <div className="discussion-empty">
              <MessageSquare size={48} />
              <p>还没有发言</p>
              <span>开始讨论，发表你的看法</span>
            </div>
          ) : (
            <>
              {state.currentDiscussionMessages.map((msg, index) => (
                <ChatMessage
                  key={index}
                  message={msg}
                  isPlayer={msg.speaker === state.player?.name}
                  character={state.characters.find((c) => c.name === msg.speaker)}
                />
              ))}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        <div className="discussion-input-area">
          <div className="discussion-input-wrapper">
            <textarea
              className="discussion-input"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="输入你的发言..."
              rows={2}
              disabled={isSending}
            />
            <Button
              variant="primary"
              onClick={handleSend}
              isLoading={isSending}
              disabled={!message.trim()}
              className="discussion-send-btn"
            >
              <Send size={18} />
            </Button>
          </div>
          <p className="discussion-hint">
            按 Enter 发送，Shift + Enter 换行
          </p>
        </div>
      </Card>

      <div className="discussion-actions">
        {state.accusationPoints > 0 && (
          <Button
            variant="danger"
            onClick={() => setShowAccuseModal(true)}
            className="discussion-action"
          >
            <AlertTriangle size={16} />
            指认凶手 ({state.accusationPoints}次)
          </Button>
        )}
        <Button
          variant="secondary"
          onClick={handleReturnToInvestigation}
          isLoading={isTransitioning}
          className="discussion-action"
        >
          <Search size={16} />
          返回搜证
        </Button>
        <Button
          variant="primary"
          onClick={handleTransitionToVoting}
          isLoading={isTransitioning}
          className="discussion-action"
        >
          <Vote size={16} />
          进入投票
          <ArrowRight size={16} />
        </Button>
      </div>

      {/* Accuse Modal */}
      <Modal
        isOpen={showAccuseModal}
        onClose={() => {
          setShowAccuseModal(false);
          setSelectedSuspect(null);
        }}
        title="指认凶手"
        size="md"
      >
        <div className="accuse-modal">
          <div className="accuse-warning">
            <AlertTriangle size={20} />
            <p>
              你只有 <strong>1 次</strong> 指认机会！<br />
              指认正确则好人胜利，错误则凶手逃脱。
            </p>
          </div>

          <div className="accuse-suspects">
            <h4>选择你要指认的角色：</h4>
            <div className="accuse-suspect-grid">
              {allCharactersForDisplay.map((char) => (
                <Card
                  key={char.id}
                  variant={selectedSuspect === char.name ? 'gold-border' : 'default'}
                  className={`accuse-suspect-card ${
                    selectedSuspect === char.name ? 'selected' : ''
                  } ${char.id === state.player?.id ? 'is-player-character' : ''}`}
                  onClick={() => setSelectedSuspect(char.name)}
                  hoverable
                >
                  {char.id === state.player?.id && (
                    <Badge variant="default" className="accuse-player-badge">
                      当前角色
                    </Badge>
                  )}
                  <Avatar
                    name={char.name}
                    size="lg"
                    showBorder={selectedSuspect === char.name}
                  />
                  <div className="accuse-suspect-info">
                    <span className="accuse-suspect-name">{char.name}</span>
                    <span className="accuse-suspect-identity">{char.public_identity}</span>
                  </div>
                  {selectedSuspect === char.name && (
                    <div className="accuse-selected-badge">
                      <Check size={14} />
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>

          <div className="accuse-actions">
            <Button
              variant="ghost"
              onClick={() => {
                setShowAccuseModal(false);
                setSelectedSuspect(null);
              }}
            >
              取消
            </Button>
            <Button
              variant="danger"
              onClick={handleAccuse}
              disabled={!selectedSuspect}
              isLoading={isAccusing}
            >
              确认指认
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
