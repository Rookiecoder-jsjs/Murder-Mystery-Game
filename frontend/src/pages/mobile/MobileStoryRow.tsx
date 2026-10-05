import { useState } from 'react';
import { BookOpen, ChevronRight } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';
import type { Story } from '../../api/types';

export function MobileStoryRow({ story, status }: { story: Story; status?: string }) {
  const { pathname } = useLocation();
  const [failedImage, setFailedImage] = useState('');
  return <Link to={`/library/${story.id}`} state={{ from: pathname }} className="mobile-story-row">
    <span className="mobile-story-thumb" aria-hidden="true">
      {story.cover_url && failedImage !== story.cover_url
        ? <img src={story.cover_url} alt="" loading="lazy" onError={() => setFailedImage(story.cover_url ?? '')} />
        : <BookOpen size={24} />}
    </span>
    <span className="mobile-story-copy"><strong>{story.title}</strong>
      {story.summary && <span className="mobile-story-summary">{story.summary}</span>}
      <span className="mobile-story-facts">{story.num_characters ? `${story.num_characters} 角色` : '原创故事'}{story.difficulty && ` · ${story.difficulty}`}{story.estimated_minutes && ` · 约 ${story.estimated_minutes} 分钟`}</span>
      {status && <span className="mobile-story-status">{status}</span>}
    </span><ChevronRight size={18} aria-hidden="true" />
  </Link>;
}
