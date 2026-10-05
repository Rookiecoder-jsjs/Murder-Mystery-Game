import { ChevronRight, Download, FolderInput, History, NotebookPen, Settings, Sparkles, Clock } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { gameEngine } from '../../api/native';
import { libraryApi } from '../../api/storyLibrary';
import { useToast } from '../../components/common';
import { useMobileLobby } from './lobbyContext';

export function MobileMyPage() {
  const { local, library } = useMobileLobby();
  const { notify } = useToast();
  const navigate = useNavigate();
  const pending = local.tasks.filter(task => task.state !== 'failed' || task.can_continue).length;
  return <section className="mobile-page mobile-my-page">
    <p className="mobile-note">{local.configured === null ? '正在读取模型设置…' : local.configured ? '模型已配置 · 手机独立运行' : '尚未配置模型；下载故事不需要密钥。'}</p>
    <div className="mobile-my-menu">
      <Link to="/my/games"><History size={21} /><span>存档与复盘</span><small>{local.games.length}</small><ChevronRight size={18} /></Link>
      <Link to="/my/stories"><NotebookPen size={21} /><span>我的剧本</span><small>{local.stories.length}</small><ChevronRight size={18} /></Link>
      <Link to="/my/create"><Sparkles size={21} /><span>生成新故事</span><ChevronRight size={18} /></Link>
      <Link to="/my/tasks"><Clock size={21} /><span>待完成任务</span><small>{pending || '无'}</small><ChevronRight size={18} /></Link>
      <button type="button" onClick={async () => {
        try { await gameEngine.openSettings(); await local.refresh(); }
        catch (problem) { notify(problem instanceof Error ? problem.message : '模型设置未保存', 'error'); }
      }}><Settings size={21} /><span>模型设置</span><ChevronRight size={18} /></button>
      <Link to="/my/downloads"><Download size={21} /><span>内容下载与记录</span><ChevronRight size={18} /></Link>
      <button type="button" disabled={library.issuing} onClick={() => void library.issue(async () => {
        const result = await libraryApi.importFile();
        if (!('cancelled' in result)) navigate('/my/downloads');
      })}><FolderInput size={21} /><span>安装官方内容包</span><small>.mmstory</small><ChevronRight size={18} /></button>
    </div>
    {library.error && <p className="mobile-error" role="alert">{library.error}</p>}
    {local.error && <p className="mobile-error" role="alert">{local.error}<button type="button" onClick={() => void local.refresh()}>重试读取</button></p>}
    {library.snapshot?.source_url && <a className="mobile-source-link" href={library.snapshot.source_url} target="_blank" rel="noreferrer">本版本对应源码 · AGPL-3.0-only</a>}
  </section>;
}
