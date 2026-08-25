// Game Layout — 固定视口应用壳：Header + (Sidebar | 主区)
// 高度模型：外壳占满 100dvh，主区与侧边栏各自滚动；
// 阶段组件内部禁止再计算 calc(100vh - X)。

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { ConnectionBanner } from '../common';
import { useGame } from '../../context/GameContext';
import './GameLayout.css';

interface GameLayoutProps {
  children: React.ReactNode;
}

export function GameLayout({ children }: GameLayoutProps) {
  const { state } = useGame();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // 阶段黑场：phase 变化时挂一帧 400ms 细缝转场（首帧不触发）
  const [curtainKey, setCurtainKey] = useState(0);
  const lastPhaseRef = useRef(state.phase);

  useEffect(() => {
    if (state.phase !== lastPhaseRef.current) {
      lastPhaseRef.current = state.phase;
      setCurtainKey((k) => k + 1);
    }
  }, [state.phase]);

  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  // 抽屉打开时：Escape 关闭 + 锁定 body 滚动
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setDrawerOpen(false);
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [drawerOpen]);

  return (
    <div className="game-shell">
      <Header onMenuClick={() => setDrawerOpen(true)} />
      {state.connectionLost && <ConnectionBanner />}
      <div className="game-body">
        <Sidebar drawerOpen={drawerOpen} onClose={closeDrawer} />
        <main className="game-main">{children}</main>
      </div>
      {drawerOpen && <div className="drawer-scrim" onClick={closeDrawer} />}
      {curtainKey > 0 && <div key={curtainKey} className="curtain" aria-hidden="true" />}
    </div>
  );
}
