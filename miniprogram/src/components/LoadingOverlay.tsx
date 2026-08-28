import { Text, View } from '@tarojs/components'
import './LoadingOverlay.scss'

export function LoadingOverlay({ label = '正在调取卷宗…' }: { label?: string }) {
  return (
    <View className='loading-overlay'>
      <View className='loading-overlay__stamp'>阅</View>
      <Text>{label}</Text>
      <View className='loading-overlay__line'><View /></View>
    </View>
  )
}
