// Voting Phase Component
import { useState } from 'react';
import { Vote, AlertTriangle, Check, ArrowLeft } from 'lucide-react';
import { useGame } from '../../context/GameContext';
import { Button, Card, Avatar, Modal } from '../common';
import './VotingPhase.css';

interface VoteResult {
  votes: Record<string, string>;
  result: string;
  game_ended: boolean;
  winner: string | null;
  phase?: string;
  reveal?: any;
}

export function VotingPhase() {
  const { state, vote, refreshStatus, returnToInvestigation, nextPhase } = useGame();
  const [selectedCharacter, setSelectedCharacter] = useState<string | null>(null);
  const [isVoting, setIsVoting] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [voteResult, setVoteResult] = useState<VoteResult | null>(null);

  const handleVote = async () => {
    if (!selectedCharacter) {
      setError('请先选择一个角色');
      return;
    }
    setError(null);
    setIsVoting(true);
    setShowConfirmModal(false);
    try {
      const result = await vote(selectedCharacter);
      setVoteResult(result);
      if (!result.game_ended) {
        await refreshStatus();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '投票失败');
    } finally {
      setIsVoting(false);
    }
  };

  // 平票时返回讨论阶段：通过返回搜证再进入讨论
  const handleReturnToDiscussion = async () => {
    try {
      await returnToInvestigation();
      await nextPhase();
    } catch (err) {
      setError('返回讨论阶段失败');
    }
  };

  return (
    <div className="voting-phase">
      <div className="voting-header">
        <div className="voting-icon">
          <Vote size={32} />
        </div>
        <h2 className="voting-title">投票阶段</h2>
        <p className="voting-subtitle">
          选择你认为的凶手
        </p>
      </div>

      <Card className="voting-instructions">
        <div className="voting-instructions-content">
          <AlertTriangle size={20} className="voting-warning-icon" />
          <div>
            <h4>投票规则</h4>
            <p>
              每位玩家投票一次，选择你认为的凶手。得票最多的角色将被淘汰。
              如果平局，将随机选择一人淘汰。
            </p>
          </div>
        </div>
      </Card>

      {/* 角色选择区域 - 投票后隐藏 */}
      {!voteResult && (
        <>
          <div className="voting-characters">
            <h3 className="voting-section-title">选择凶手</h3>
            <div className="voting-character-grid">
              {state.characters
                .filter((c) => c.id !== state.player?.id)
                .map((char) => (
                  <Card
                    key={char.id}
                    variant={selectedCharacter === char.name ? 'gold-border' : 'default'}
                    className={`voting-character-card ${
                      selectedCharacter === char.name ? 'selected' : ''
                    }`}
                    onClick={() => setSelectedCharacter(char.name)}
                    hoverable
                  >
                    <Avatar
                      name={char.name}
                      size="xl"
                      showBorder={selectedCharacter === char.name}
                    />
                    <div className="voting-character-info">
                      <span className="voting-character-name">{char.name}</span>
                      <span className="voting-character-identity">{char.public_identity}</span>
                    </div>
                    {selectedCharacter === char.name && (
                      <div className="voting-selected-badge">
                        <Check size={16} />
                      </div>
                    )}
                  </Card>
                ))}
            </div>
          </div>

          <div className="voting-actions">
            <Button
              variant="primary"
              size="lg"
              onClick={() => setShowConfirmModal(true)}
              disabled={!selectedCharacter || isVoting}
              isLoading={isVoting}
            >
              <Vote size={18} />
              确认投票
            </Button>
          </div>
        </>
      )}

      {/* 投票结果展示 */}
      {voteResult && (
        <Card className={`voting-result-card ${voteResult.game_ended ? 'result-ended' : 'result-tie'}`}>
          <h3>{voteResult.game_ended ? '投票结束' : '投票未达成结果'}</h3>
          <p className="voting-result-message">{voteResult.result}</p>

          {voteResult.game_ended ? (
            <p className="voting-result-next">
              即将进入真相揭晓阶段...
            </p>
          ) : (
            <div className="voting-tie-actions">
              <p className="voting-tie-hint">需要继续讨论后再投票</p>
              <Button variant="secondary" onClick={handleReturnToDiscussion}>
                <ArrowLeft size={16} />
                返回讨论阶段
              </Button>
            </div>
          )}
        </Card>
      )}

      {error && (
        <Card className="voting-error">
          <AlertTriangle size={16} />
          <span>{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </Card>
      )}

      <Modal
        isOpen={showConfirmModal}
        onClose={() => setShowConfirmModal(false)}
        title="确认投票"
        size="sm"
      >
        <div className="voting-confirm-content">
          <p>你确定要投票给 <strong>{selectedCharacter}</strong> 吗？</p>
          <p className="voting-confirm-hint">此操作无法撤销</p>
          <div className="voting-confirm-actions">
            <Button variant="ghost" onClick={() => setShowConfirmModal(false)}>
              取消
            </Button>
            <Button variant="danger" onClick={handleVote}>
              确认投票
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
