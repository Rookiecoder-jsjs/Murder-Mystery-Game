import { defineConfig, type UserConfigExport } from '@tarojs/cli'
import path from 'node:path'

const apiBaseUrl = process.env.TARO_APP_API_BASE || 'http://127.0.0.1:8000'

const config: UserConfigExport<'webpack5'> = {
  projectName: 'murder-mystery-miniprogram',
  date: '2026-08-27',
  designWidth: 750,
  deviceRatio: {
    640: 2.34 / 2,
    750: 1,
    828: 1.81 / 2,
  },
  sourceRoot: 'src',
  outputRoot: 'dist',
  framework: 'react',
  alias: {
    '@': path.resolve(__dirname, '..', 'src'),
  },
  compiler: {
    type: 'webpack5',
    prebundle: {
      enable: false,
    },
  },
  cache: {
    enable: true,
  },
  defineConstants: {
    API_BASE_URL: JSON.stringify(apiBaseUrl),
  },
  mini: {
    postcss: {
      pxtransform: {
        enable: true,
        config: {},
      },
      url: {
        enable: true,
        config: {
          limit: 1024,
        },
      },
      cssModules: {
        enable: false,
      },
    },
  },
}

export default defineConfig<'webpack5'>(async (merge) => {
  if (process.env.NODE_ENV === 'development') {
    return merge({}, config, (await import('./dev')).default)
  }
  return merge({}, config, (await import('./prod')).default)
})
