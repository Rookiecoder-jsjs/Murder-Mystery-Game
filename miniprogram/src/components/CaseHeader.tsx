import Taro from '@tarojs/taro'
import { Text, View } from '@tarojs/components'
import './CaseHeader.scss'

interface CaseHeaderProps {
  title?: string
  eyebrow?: string
  role?: string
  showBack?: boolean
}

export function CaseHeader({
  title = '剧本杀',
  eyebrow = '名案档案馆',
  role,
  showBack = false,
}: CaseHeaderProps) {
  const handleBack = () => {
    const pages = Taro.getCurrentPages()
    if (pages.length > 1) Taro.navigateBack()
    else Taro.reLaunch({ url: '/pages/index/index' })
  }

  return (
    <View className='case-header'>
      <View className='case-header__safe' />
      <View className='case-header__bar'>
        <View className='case-header__left'>
          {showBack ? (
            <View className='case-header__back' onClick={handleBack}>‹</View>
          ) : (
            <View className='case-header__menu'>☰</View>
          )}
          <View>
            <Text className='case-header__eyebrow'>{eyebrow}</Text>
            <Text className='case-header__title'>{title}</Text>
          </View>
        </View>
        {role ? (
          <View className='case-header__role'>
            <Text>你的角色</Text>
            <Text>{role}</Text>
          </View>
        ) : (
          <View className='case-header__seal'>案</View>
        )}
      </View>
    </View>
  )
}
