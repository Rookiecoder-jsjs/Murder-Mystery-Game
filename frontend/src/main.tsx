import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { isAndroid } from './api/native';

if (isAndroid) document.documentElement.classList.add('native-app');

// 预热书法体常用字的 unicode 分片（Ma Shan Zheng 按需懒加载 92 片，
// 提前拉取页面高频字，避免大标题首帧从宋体"跳"成书法体）
if (!isAndroid && 'fonts' in document && 'load' in document.fonts) {
  document.fonts.load('400 32px "Ma Shan Zheng"', '剧本杀真相结案报案');
  document.fonts.load('400 48px "Ma Shan Zheng"', '自我表决');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
