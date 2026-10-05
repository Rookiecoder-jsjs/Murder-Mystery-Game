import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import { useToast } from '../../components/common';
import { useMobileLobby } from './lobbyContext';
import { MobileStoryRow } from './MobileStoryRow';

export function MobilePersonalPage() {
  const { local } = useMobileLobby();
  const { notify } = useToast();
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(20);
  const [importing, setImporting] = useState(false);
  const [error, setError] = useState('');
  const stories = local.stories.filter(story => `${story.title} ${story.summary ?? story.topic}`.includes(query.trim()));
  return <section className="mobile-page">
    <p className="mobile-note">自行生成、导入与旧版故事保存在这里，质量受来源与模型影响。</p>
    <div className="mobile-personal-tools"><Link className="btn btn-secondary" to="/my/create">生成新故事</Link>
      <label className="btn btn-secondary mobile-import-label">{importing ? '正在导入…' : '导入 JSON'}
        <input type="file" accept=".json,application/json" aria-label="导入个人剧本 JSON" disabled={importing || local.running} onChange={async event => {
          const file = event.currentTarget.files?.[0]; event.currentTarget.value = '';
          if (!file) return;
          setImporting(true); setError('');
          try {
            if (file.size > 2 * 1024 * 1024) throw new Error('剧本包不能超过 2 MB');
            const packageData: unknown = JSON.parse(await file.text());
            await api.importStory(packageData); await local.refresh();
            notify('个人剧本已导入，旧局保留原版本', 'success');
          } catch (problem) { setError(problem instanceof Error ? problem.message : '导入失败'); }
          finally { setImporting(false); }
        }} />
      </label></div>
    <input type="search" className="mobile-personal-search" aria-label="搜索我的剧本" placeholder="搜索我的剧本" value={query} onChange={event => { setQuery(event.target.value); setLimit(20); }} />
    {error && <p className="mobile-error" role="alert">{error}</p>}
    <div className="mobile-story-list">{stories.slice(0, limit).map(story => <MobileStoryRow key={story.id} story={story} status={story.origin === 'generated' ? '自行生成' : story.origin === 'imported' ? '个人导入' : '旧版故事'} />)}</div>
    {local.loading && <p className="mobile-note" role="status">正在读取个人故事…</p>}
    {!local.loading && !stories.length && <p className="mobile-empty">{query ? '没有找到符合条件的故事' : '暂无个人故事'}</p>}
    {local.error && <p className="mobile-error" role="alert">{local.error}</p>}
    {stories.length > limit && <button type="button" className="btn btn-secondary mobile-wide-button" onClick={() => setLimit(value => value + 20)}>显示更多故事</button>}
  </section>;
}
