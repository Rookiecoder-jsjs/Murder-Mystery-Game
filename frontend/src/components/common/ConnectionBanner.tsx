// ConnectionBanner — 轮询连续失败时的常驻断连提示
import { WifiOff } from 'lucide-react';
import './ConnectionBanner.css';

export function ConnectionBanner() {
  return (
    <div className="connection-banner" role="status">
      <WifiOff size={14} />
      <span>连接已断开，正在重试…</span>
    </div>
  );
}
