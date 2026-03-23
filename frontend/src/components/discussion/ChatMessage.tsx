// Chat Message Component
import { Avatar } from '../common';
import type { ChatMessage as ChatMessageType, CharacterInfo } from '../../api/types';
import './ChatMessage.css';

interface ChatMessageProps {
  message: ChatMessageType;
  isPlayer: boolean;
  character?: CharacterInfo;
}

export function ChatMessage({ message, isPlayer, character }: ChatMessageProps) {
  return (
    <div className={`chat-message ${isPlayer ? 'chat-message-player' : 'chat-message-other'}`}>
      {!isPlayer && (
        <Avatar name={character?.name || message.speaker} size="md" />
      )}
      <div className="chat-message-content">
        <div className="chat-message-header">
          <span className="chat-message-sender">
            {isPlayer ? 'You' : message.speaker}
          </span>
          {!isPlayer && character && (
            <span className="chat-message-identity">{character.public_identity}</span>
          )}
        </div>
        <p className="chat-message-text">{message.message}</p>
      </div>
      {isPlayer && (
        <Avatar name="Player" size="md" showBorder />
      )}
    </div>
  );
}
