import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// 预热书法体常用字的 unicode 分片（Ma Shan Zheng 按需懒加载 92 片，
// 提前拉取页面高频字，避免大标题首帧从宋体"跳"成书法体）
if ('fonts' in document && 'load' in document.fonts) {
  document.fonts.load('400 32px "Ma Shan Zheng"', '剧本杀真相结案报案');
  document.fonts.load('400 48px "Ma Shan Zheng"', '自我表决');
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
