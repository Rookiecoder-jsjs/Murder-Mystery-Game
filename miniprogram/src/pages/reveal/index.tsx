import Taro, { useRouter } from '@tarojs/taro'
import { Button, Text, View } from '@tarojs/components'
import { useEffect, useMemo, useState } from 'react'
import { CaseHeader, LoadingOverlay, PortraitFrame } from '@/components'
import { useGame } from '@/store/game-context'
import { showError } from '@/utils/feedback'
import './index.scss'

export default function RevealPage() {
  const router = useRouter()
  const gameId = router.params.gameId || ''
  const { state, loadReveal, resetGame } = useGame()
  const [loading, setLoading] = useState(!state.revealInfo)
  const [failed, setFailed] = useState(false)

  const fetchReveal = async () => {
    if (!gameId) {
      setFailed(true)
      setLoading(false)
      return
    }
    setLoading(true)
    setFailed(false)
    try {
      await loadReveal(gameId)
    } catch (error) {
      setFailed(true)
      showError(error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!state.revealInfo || state.gameId !== gameId) fetchReveal()
    else setLoading(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId])

  const reveal = state.revealInfo
  const characters = reveal?.characters || state.characters
  const killer = useMemo(() => {
    if (!reveal) return undefined
    return characters.find((item) => (
      item.id === reveal.case_info.true_killer || item.is_killer
    ))
  }, [characters, reveal])
  const portraits = characters.map((item) => item.portrait_url || '')
  const goodWin = reveal?.winner === 'good'

  const goHome = () => {
    resetGame()
    Taro.reLaunch({ url: '/pages/index/index' })
  }

  if (failed && !reveal) {
    return (
      <View className='page-shell reveal-page'>
        <CaseHeader title='结案报告' eyebrow='FINAL REPORT' showBack />
        <View className='paper-stage reveal-page__error'>
          <Text className='empty-state__mark'>缺</Text>
          <Text>真相页暂时无法调取，请确认后端仍保留本局会话。</Text>
          <Button className='primary-button' onClick={fetchReveal}>重新调取</Button>
          <Button className='ghost-button' onClick={goHome}>返回档案馆</Button>
        </View>
      </View>
    )
  }

  return (
    <View className='page-shell reveal-page'>
      <CaseHeader title='结案报告' eyebrow='FINAL REPORT' />
      {reveal && (
        <>
          <View className='reveal-page__curtain'>
            <Text className='reveal-page__serial'>CASE CLOSED / {gameId.slice(0, 8).toUpperCase()}</Text>
            <Text className='reveal-page__title'>真相大白</Text>
            <Text className={`reveal-page__verdict ${goodWin ? 'is-win' : 'is-lose'}`}>
              {goodWin ? '推理方获胜' : reveal.winner === 'killer' ? '凶手逃脱' : '案件终结'}
            </Text>
            <View className='reveal-page__closed-stamp'>结案</View>
          </View>

          <View className='paper-stage reveal-page__stage'>
            <View className='reveal-page__heading'>
              <Text className='section-kicker'>THE TRUTH</Text>
              <Text className='section-title'>{reveal.case_info.title}</Text>
              <Text className='section-desc'>{reveal.case_info.background}</Text>
            </View>

            <View className='reveal-page__killer paper-card'>
              {killer ? (
                <PortraitFrame
                  name={killer.name}
                  src={killer.portrait_url}
                  size='hero'
                  previewGroup={portraits}
                />
              ) : (
                <View className='reveal-page__killer-fallback'>凶</View>
              )}
              <View className='reveal-page__killer-info'>
                <Text>真正的凶手</Text>
                <Text>{reveal.case_info.true_killer_name || killer?.name || reveal.case_info.true_killer}</Text>
                <Text>{killer?.public_identity || '身份已归档'}</Text>
                <View className='reveal-page__motive'>
                  <Text>作案动机</Text>
                  <Text>{killer?.motive || reveal.case_info.motive}</Text>
                </View>
              </View>
              <View className='reveal-page__guilty-stamp'>真凶</View>
            </View>

            <View className='reveal-page__facts'>
              <View><Text>受害者</Text><Text>{reveal.case_info.victim}</Text></View>
              <View><Text>罪行</Text><Text>{reveal.case_info.crime}</Text></View>
              <View><Text>最终结果</Text><Text>{goodWin ? '真相被揭开' : '真凶逃离审判'}</Text></View>
            </View>

            <View className='reveal-page__truth paper-card'>
              <View className='reveal-page__truth-head'>
                <Text>完整真相</Text>
                <Text>CONFIDENTIAL / DECLASSIFIED</Text>
              </View>
              <Text className='reveal-page__story'>{reveal.story_content}</Text>
            </View>

            {characters.length > 0 && (
              <View className='reveal-page__aftermath'>
                <Text className='field-label'>人物档案 · 解密版</Text>
                <View className='reveal-page__character-list'>
                  {characters.map((character) => (
                    <View key={character.id} className='reveal-character paper-card'>
                      <PortraitFrame
                        name={character.name}
                        src={character.portrait_url}
                        size='card'
                        previewGroup={portraits}
                      />
                      <View className='reveal-character__body'>
                        <Text>{character.name}</Text>
                        <Text>{character.public_identity}</Text>
                        {character.relationship_with_victim && (
                          <Text>与受害者：{character.relationship_with_victim}</Text>
                        )}
                        {character.backstory && <Text>{character.backstory}</Text>}
                      </View>
                    </View>
                  ))}
                </View>
              </View>
            )}

            <Button className='primary-button reveal-page__home' onClick={goHome}>封存本案 · 返回档案馆</Button>
          </View>
        </>
      )}
      {loading && <LoadingOverlay label='正在解封最终真相…' />}
    </View>
  )
}
