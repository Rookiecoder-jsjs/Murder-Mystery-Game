import type { PropsWithChildren } from 'react'
import { GameProvider } from './store/game-context'
import './app.scss'

export default function App({ children }: PropsWithChildren) {
  return <GameProvider>{children}</GameProvider>
}
