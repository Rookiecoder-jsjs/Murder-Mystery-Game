import Taro, { useRouter } from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import { useEffect, useRef, useState } from 'react'
import { CaseHeader, LoadingOverlay, PhaseTimeline } from '@/components'
import {
  DiscussionPanel,
  IntroductionPanel,
  InvestigationPanel,
  VotingPanel,
} from '@/features/game'
import { useGame } from '@/store/game-context'
import { showError } from '@/utils/feedback'
import './index.scss'

export default function GamePage() {
  const router = useRouter()
  const gameId = router.params.gameId || ''
  const { state, resumeGame } = useGame()
  const [initializing, setInitializing] = useState(false)
  const [loadFailed, setLoadFailed] = useState(false)
  const redirectedRef = useRef(false)

  const initialize = async () => {
    if (!gameId) {
      setLoadFailed(true)
      return
    }
    if (state.gameId === gameId && state.player) return
    setInitializing(true)
    setLoadFailed(false)
    try {
      await resumeGame(gameId)
    } catch (error) {
      setLoadFailed(true)
      showError(error)
    } finally {
      setInitializing(false)
    }
  }

  useEffect(() => {
    initialize()
    // 仅在路由卷宗号变化时重新调取，避免每个状态更新都触发请求。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  useEffect(() => {
    if (state.phase === 'reveal' && gameId && !redirectedRef.current) {
      redirectedRef.current = true
      Taro.redirectTo({ url: `/pages/reveal/index?gameId=${gameId}` })
    }
  }, [state.phase, gameId])

  const renderPhase = () => {
    switch (state.phase) {
      case 'introduction':
        return <IntroductionPanel />
      case 'investigation':
        return <InvestigationPanel />
      case 'discussion':
        return <DiscussionPanel />
      case 'voting':
        return <VotingPanel />
      default:
        return null
    }
  }

  if (loadFailed && !state.player) {
    return (
      <View className='page-shell game-page'>
        <CaseHeader title='卷宗中断' eyebrow='ARCHIVE ERROR' showBack />
        <View className='paper-stage game-page__error'>
          <Text className='empty-state__mark'>断</Text>
          <Text>这份游戏卷宗无法恢复，可能是本地后端已经重启且没有开启会话持久化。</Text>
          <Button className='primary-button' onClick={initialize}>重新调取</Button>
          <Button className='ghost-button' onClick={() => Taro.reLaunch({ url: '/pages/index/index' })}>返回档案馆</Button>
        </View>
      </View>
    )
  }

  return (
    <View className='page-shell game-page'>
      <CaseHeader
        title='未结案卷'
        eyebrow={gameId ? `CASE ${gameId.slice(0, 8).toUpperCase()}` : 'LIVE CASE'}
        role={state.player?.name}
        showBack
      />
      <PhaseTimeline phase={state.phase} />
      <View className='paper-stage game-page__stage'>
        {renderPhase()}
      </View>
      {(initializing || state.isLoading) && (
        <LoadingOverlay label={initializing ? '正在恢复调查现场…' : '正在更新案件卷宗…'} />
      )}
    </View>
  )
}
