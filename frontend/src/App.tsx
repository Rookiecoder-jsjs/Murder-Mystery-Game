// App.tsx — 根组件：Toast → Game → 路由（ErrorBoundary 兜底渲染异常）
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ErrorBoundary, ToastProvider } from './components/common';
import { GameProvider } from './context/GameContext';
import { HomePage, GamePage } from './pages';
import './styles/index.css';
import './styles/mobile.css';
import { MobileLifecycle } from './components/common/MobileLifecycle';
import { isAndroid } from './api/native';
import { MobileLobby } from './pages/mobile/MobileLobby';
import { MobileHomePage } from './pages/mobile/MobileHomePage';
import { MobileLibraryPage } from './pages/mobile/MobileLibraryPage';
import { MobileStoryDetailPage } from './pages/mobile/MobileStoryDetailPage';
import { MobileMyPage } from './pages/mobile/MobileMyPage';
import { MobileGamesPage } from './pages/mobile/MobileGamesPage';
import { MobilePersonalPage } from './pages/mobile/MobilePersonalPage';
import { MobileGeneratePage } from './pages/mobile/MobileGeneratePage';
import { MobileDownloadsPage, MobileTasksPage } from './pages/mobile/MobileTasksPage';

function App() {
  return (
    <ToastProvider>
      <GameProvider>
        <BrowserRouter>
          <MobileLifecycle />
          <ErrorBoundary>
            <Routes>
              {isAndroid ? <Route element={<MobileLobby />}>
                <Route path="/" element={<MobileHomePage />} />
                <Route path="/library" element={<MobileLibraryPage />} />
                <Route path="/library/:storyId" element={<MobileStoryDetailPage />} />
                <Route path="/my" element={<MobileMyPage />} />
                <Route path="/my/games" element={<MobileGamesPage />} />
                <Route path="/my/stories" element={<MobilePersonalPage />} />
                <Route path="/my/create" element={<MobileGeneratePage />} />
                <Route path="/my/tasks" element={<MobileTasksPage />} />
                <Route path="/my/downloads" element={<MobileDownloadsPage />} />
              </Route> : <Route path="/" element={<HomePage />} />}
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
