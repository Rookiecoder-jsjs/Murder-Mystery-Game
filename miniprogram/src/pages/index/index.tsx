import Taro, { useDidShow, usePullDownRefresh } from '@tarojs/taro'
import { Button, ScrollView, Text, View } from '@tarojs/components'
import { useCallback, useState } from 'react'
import { CaseHeader, LoadingOverlay } from '@/components'
import { gameApi } from '@/services/game-api'
import { getLastGameId, useGame } from '@/store/game-context'
import type { Story } from '@/types/game'
import { showError } from '@/utils/feedback'
import './index.scss'

function displayDate(value: string): string {
  return value.split(' ')[0].replace(/-/g, '.')
}

export default function IndexPage() {
  const { loadGame } = useGame()
  const [stories, setStories] = useState<Story[]>([])
  const [loading, setLoading] = useState(true)
  const [storiesError, setStoriesError] = useState(false)
  const [busyLabel, setBusyLabel] = useState('')
  const [lastGameId, setLastGameId] = useState('')

  const refreshStories = useCallback(async () => {
    setLoading(true)
    setStoriesError(false)
    try {
      const result = await gameApi.listStories()
      setStories(result.stories)
    } catch {
      setStoriesError(true)
    } finally {
      setLoading(false)
      Taro.stopPullDownRefresh()
    }
  }, [])

  useDidShow(() => {
    setLastGameId(getLastGameId())
    refreshStories()
  })

  usePullDownRefresh(refreshStories)

  const openNewCase = () => Taro.navigateTo({ url: '/pages/create/index' })

  const openStory = async (story: Story) => {
    setBusyLabel(`正在启封《${story.title}》`)
    try {
      const gameId = await loadGame(story.id)
      Taro.navigateTo({ url: `/pages/game/index?gameId=${gameId}` })
    } catch (error) {
      showError(error)
    } finally {
      setBusyLabel('')
    }
  }

  const resumeLastGame = () => {
    if (!lastGameId) return
    Taro.navigateTo({ url: `/pages/game/index?gameId=${lastGameId}` })
  }

  return (
    <View className='page-shell archive-home'>
      <CaseHeader />
      <View className='archive-home__hero'>
        <Text className='archive-home__serial'>ARCHIVE / 1930</Text>
        <Text className='archive-home__title'>一案一生，{`\n`}入局即是证人</Text>
        <Text className='archive-home__subtitle'>AI 即时构筑案件与人物，每一位嫌疑人都有自己的秘密。</Text>
        <View className='archive-home__red-thread' />
        <View className='archive-home__stamp'>待{`\n`}立案</View>
        <Button className='archive-home__create' onClick={openNewCase}>
          <Text>＋</Text>
          <View>
            <Text>创建新案件</Text>
            <Text>生成剧情、角色与人物肖像</Text>
          </View>
          <Text>›</Text>
        </Button>
        {lastGameId && (
          <Button className='archive-home__resume' onClick={resumeLastGame}>
            <Text>继续上次调查</Text>
            <Text>卷宗号 {lastGameId.slice(0, 8).toUpperCase()} · 未结</Text>
          </Button>
        )}
      </View>

      <View className='paper-stage archive-home__stage'>
        <View className='archive-home__section-head'>
          <View>
            <Text className='section-kicker'>CASE LIBRARY</Text>
            <Text className='section-title'>旧案卷宗</Text>
          </View>
          <Text className='archive-home__count'>{String(stories.length).padStart(2, '0')} 卷</Text>
        </View>

        {loading ? (
          <View className='archive-home__skeletons'>
            {[0, 1, 2].map((item) => <View key={item} className='archive-home__skeleton' />)}
          </View>
        ) : storiesError ? (
          <View className='paper-card empty-state'>
            <Text className='empty-state__mark'>断</Text>
            <Text>档案馆暂时无法连接后端</Text>
            <Button className='ghost-button archive-home__retry' onClick={refreshStories}>重新调取</Button>
          </View>
        ) : stories.length === 0 ? (
          <View className='paper-card empty-state'>
            <Text className='empty-state__mark'>空</Text>
            <Text>尚无旧案，创建第一卷案件吧</Text>
          </View>
        ) : (
          <ScrollView className='archive-home__cases' scrollX enhanced showScrollbar={false}>
            <View className='archive-home__case-row'>
              {stories.map((story, index) => (
                <View key={story.id} className='case-file' onClick={() => openStory(story)}>
                  <View className='case-file__tab'>卷 {String(index + 1).padStart(2, '0')}</View>
                  <View className='case-file__pin' />
                  <Text className='case-file__topic'>{story.topic}</Text>
                  <Text className='case-file__title'>{story.title}</Text>
                  <View className='case-file__rule' />
                  <View className='case-file__meta'>
                    <Text>{story.num_characters || '—'} 位涉案人</Text>
                    <Text>{displayDate(story.created_at)}</Text>
                  </View>
                  <View className='case-file__status'>可重开</View>
                  <Text className='case-file__open'>启封调查 →</Text>
                </View>
              ))}
            </View>
          </ScrollView>
        )}

        <View className='archive-home__footnote'>
          <Text>＊ 所有案件均由 AI 即时生成</Text>
          <Text>人物肖像为剧情设定的视觉演绎</Text>
        </View>
      </View>
      {busyLabel && <LoadingOverlay label={busyLabel} />}
    </View>
  )
}
