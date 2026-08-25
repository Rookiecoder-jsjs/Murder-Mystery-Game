// App.tsx — 根组件：Toast → Game → 路由（ErrorBoundary 兜底渲染异常）
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary, ToastProvider } from './components/common';
import { GameProvider } from './context/GameContext';
import { HomePage, GamePage } from './pages';
import './styles/index.css';

function App() {
  return (
    <ToastProvider>
      <GameProvider>
        <BrowserRouter>
          <ErrorBoundary>
            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/game/:gameId" element={<GamePage />} />
              {/* 旧的无 id 路由一律回首页 */}
              <Route path="/game" element={<Navigate to="/" replace />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ErrorBoundary>
        </BrowserRouter>
      </GameProvider>
    </ToastProvider>
  );
}

export default App;
