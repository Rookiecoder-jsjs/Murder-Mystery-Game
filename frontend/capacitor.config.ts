import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.murdermystery.game',
  appName: '剧本杀',
  webDir: 'dist',
  server: { androidScheme: 'https' },
  plugins: { SystemBars: { insetsHandling: 'css' } },
};

export default config;
