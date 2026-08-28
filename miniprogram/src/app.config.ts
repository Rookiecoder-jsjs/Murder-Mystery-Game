export default defineAppConfig({
  pages: [
    'pages/index/index',
    'pages/create/index',
    'pages/game/index',
    'pages/reveal/index',
  ],
  window: {
    navigationStyle: 'custom',
    backgroundTextStyle: 'dark',
    backgroundColor: '#17130f',
    navigationBarBackgroundColor: '#17130f',
    navigationBarTitleText: '剧本杀',
    navigationBarTextStyle: 'white',
  },
  lazyCodeLoading: 'requiredComponents',
})
