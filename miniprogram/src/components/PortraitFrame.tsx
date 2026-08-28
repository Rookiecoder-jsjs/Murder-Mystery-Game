import Taro from '@tarojs/taro'
import { Image, Text, View } from '@tarojs/components'
import { useEffect, useState } from 'react'
import { resolveAssetUrl } from '@/config/env'
import './PortraitFrame.scss'

interface PortraitFrameProps {
  name: string
  src?: string
  size?: 'hero' | 'card' | 'thumb' | 'poster'
  label?: string
  previewGroup?: string[]
  className?: string
}

export function PortraitFrame({
  name,
  src,
  size = 'card',
  label,
  previewGroup,
  className = '',
}: PortraitFrameProps) {
  const [failed, setFailed] = useState(false)
  const imageUrl = resolveAssetUrl(src)

  useEffect(() => setFailed(false), [imageUrl])

  const preview = () => {
    if (!imageUrl || failed) return
    const urls = (previewGroup || [src || ''])
      .map(resolveAssetUrl)
      .filter(Boolean)
    Taro.previewImage({ current: imageUrl, urls })
  }

  return (
    <View className={`portrait-frame portrait-frame--${size} ${className}`} onClick={preview}>
      <View className='portrait-frame__tape' />
      <View className='portrait-frame__photo'>
        {imageUrl && !failed ? (
          <Image
            className='portrait-frame__image'
            src={imageUrl}
            mode='aspectFill'
            lazyLoad
            onError={() => setFailed(true)}
          />
        ) : (
          <View className='portrait-frame__fallback'>
            <Text>{name.slice(0, 1)}</Text>
            <Text>人物档案</Text>
          </View>
        )}
        <View className='portrait-frame__focus' />
      </View>
      {label !== '' && (
        <View className='portrait-frame__caption'>
          <Text>{label || name}</Text>
          <Text>点击查看全貌</Text>
        </View>
      )}
    </View>
  )
}
