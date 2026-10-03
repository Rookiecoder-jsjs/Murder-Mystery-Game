import type { CharacterInfo } from '../../api/types';
import './RoleScript.css';

export function RoleScript({ player, expanded = false }: { player: CharacterInfo | null; expanded?: boolean }) {
  if (!player?.role_script) return null;
  return (
    <details className="role-script" open={expanded || undefined}>
      <summary>我的角色剧本 · {player.name}</summary>
      <p className="role-script-note">仅你本人知道的经历，可在讨论时选择透露。</p>
      <p className="role-script-text">{player.role_script}</p>
      <h4>你的任务</h4>
      <ul>{player.objectives?.map((goal) => <li key={goal}>{goal}</li>)}</ul>
    </details>
  );
}
