// Game Layout Component

import React from 'react';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import './GameLayout.css';

interface GameLayoutProps {
  children: React.ReactNode;
}

export function GameLayout({ children }: GameLayoutProps) {
  return (
    <div className="game-layout">
      <Header />
      <div className="game-layout-body">
        <Sidebar />
        <main className="game-layout-main">{children}</main>
      </div>
    </div>
  );
}
