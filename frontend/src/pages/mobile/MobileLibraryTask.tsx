import { contentSize, isLibraryTaskActive, libraryTaskLabel, type LibraryTask } from '../../api/storyLibrary';

export function MobileLibraryTask({ task, onCancel, disabled }: {
  task: LibraryTask; onCancel: (id: string) => void; disabled: boolean;
}) {
  const downloading = task.state === 'downloading' && !task.cancel_requested;
  const percent = task.total_bytes > 0 ? Math.min(100, Math.floor(task.downloaded_bytes * 100 / task.total_bytes)) : undefined;
  return <div className="mobile-library-task" role="status">
    <p>{libraryTaskLabel(task)}</p>
    {downloading && <><p className="mobile-note">{contentSize(task.downloaded_bytes)}{task.total_bytes > 0 && ` / ${contentSize(task.total_bytes)}`}</p>
      <progress value={percent} max={100} aria-label="内容下载进度" /></>}
    {task.can_cancel && isLibraryTaskActive(task) && <button type="button" className="btn btn-secondary" disabled={disabled || task.cancel_requested} onClick={() => onCancel(task.id)}>{task.cancel_requested ? '正在取消' : '取消下载'}</button>}
  </div>;
}
