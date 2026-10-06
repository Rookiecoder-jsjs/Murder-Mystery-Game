import type { Dispatch, SetStateAction } from 'react';
import { useOutletContext } from 'react-router-dom';
import type { LibraryView } from '../../utils/mobileLibrary';
import type { GameMode } from '../../api/types';
import type { useStoryLibrary } from '../../components/story-library/useStoryLibrary';
import type { useLocalLobby } from './useLocalLobby';

export interface MobileLobbyData {
  library: ReturnType<typeof useStoryLibrary>;
  local: ReturnType<typeof useLocalLobby>;
  view: LibraryView;
  setView: Dispatch<SetStateAction<LibraryView>>;
  personalView: { query: string; limit: number };
  setPersonalView: Dispatch<SetStateAction<MobileLobbyData['personalView']>>;
  mode: GameMode;
  setMode: Dispatch<SetStateAction<GameMode>>;
  scrollToTop: () => void;
}
export function useMobileLobby(): MobileLobbyData { return useOutletContext<MobileLobbyData>(); }
