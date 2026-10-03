// Chat Message — 玩家右对齐暗金边，AI 左对齐
import { Avatar } from '../common';
import type {
  ChatMessage as ChatMessageType,
  CharacterInfo,
  Clue,
} from '../../api/types';
import { presentPlayerMessage } from '../../utils/playerText';
import './ChatMessage.css';

interface ChatMessageProps {
  message: ChatMessageType;
  isPlayer: boolean;
  character?: CharacterInfo;
  clues?: Clue[];
}

export function ChatMessage({ message, isPlayer, character, clues = [] }: ChatMessageProps) {
  const display = isPlayer ? presentPlayerMessage(message.message, clues) : { text: message.message, target: '', evidence: [] };
  return (
    <div
      className={`chat-message ${
        isPlayer ? 'chat-message-player' : 'chat-message-other'
      }`}
    >
      {!isPlayer && (
        <Avatar
          name={character?.name || message.speaker}
          imageUrl={character?.portrait_url}
          size="lg"
        />
      )}
      <div className="chat-message-content">
        <div className="chat-message-header">
          <span className="chat-message-sender">
            {isPlayer ? `${message.speaker}（你）` : message.speaker}
          </span>
          {!isPlayer && character && (
            <span className="chat-message-identity">
              {character.public_identity}
            </span>
          )}
        </div>
        {(display.target || display.evidence.length > 0) && <div className="chat-message-context">
          {display.target && <span>询问 · {display.target}</span>}
          {display.evidence.map((name, i) => <span key={i}>出示 · {name}</span>)}
        </div>}
        <p className="chat-message-text">{display.text}</p>
      </div>
      {isPlayer && (
        <Avatar
          name={message.speaker}
          imageUrl={character?.portrait_url}
          size="lg"
          showBorder
        />
      )}
    </div>
  );
}
