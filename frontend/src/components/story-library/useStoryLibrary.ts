import { useCallback, useEffect, useRef, useState } from 'react';
import { isLibraryTaskActive, libraryApi, type LibrarySnapshot } from '../../api/storyLibrary';

// Public catalogue state remains available while a game screen is open.
let cachedSnapshot: LibrarySnapshot | null = null;
let lastAutomaticCheck = 0;

export function useStoryLibrary() {
  const [snapshot, setSnapshot] = useState(cachedSnapshot);
  const [readError, setReadError] = useState('');
  const [operationError, setOperationError] = useState('');
  const [issuing, setIssuing] = useState(false);
  const mounted = useRef(false);
  const revision = useRef(cachedSnapshot?.library_revision);
  const pendingRead = useRef<Promise<LibrarySnapshot | null> | null>(null);
  const issuingRef = useRef(false);
  const refresh = useCallback((): Promise<LibrarySnapshot | null> => {
    if (pendingRead.current) return pendingRead.current;
    const request = libraryApi.read().then(value => {
      cachedSnapshot = value;
      if (mounted.current) {
        if (revision.current !== undefined && revision.current !== value.library_revision) {
          window.dispatchEvent(new Event('mystery:library-updated'));
        }
        revision.current = value.library_revision;
        setSnapshot(value);
        setReadError('');
      }
      return value;
    }).catch(problem => {
      if (mounted.current) setReadError(problem instanceof Error ? problem.message : '剧本库读取失败');
      return null;
    }).finally(() => { pendingRead.current = null; });
    pendingRead.current = request;
    return request;
  }, []);
  useEffect(() => {
    mounted.current = true;
    const refreshAndCheck = async () => {
      const value = await refresh();
      const now = Date.now();
      if (!value || !mounted.current || now - lastAutomaticCheck < 60_000
        || (value.last_checked_at && now - value.last_checked_at < 24 * 60 * 60_000)) return;
      lastAutomaticCheck = now;
      try { await libraryApi.check(); await refresh(); }
      catch { /* Local play remains available when the official catalogue is offline. */ }
    };
    void refreshAndCheck();
    window.addEventListener('mystery:resume', refreshAndCheck);
    return () => { mounted.current = false; window.removeEventListener('mystery:resume', refreshAndCheck); };
  }, [refresh]);
  const active = snapshot?.tasks.some(isLibraryTaskActive) ?? false;
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => { if (!document.hidden) void refresh(); }, 750);
    return () => window.clearInterval(timer);
  }, [active, refresh]);
  const issue = useCallback(async (operation: () => Promise<unknown>): Promise<boolean> => {
    if (issuingRef.current) return false;
    issuingRef.current = true;
    setIssuing(true); setOperationError('');
    try { await operation(); await refresh(); return true; }
    catch (problem) {
      if (mounted.current) setOperationError(problem instanceof Error ? problem.message : '内容操作失败');
      return false;
    } finally {
      issuingRef.current = false;
      if (mounted.current) setIssuing(false);
    }
  }, [refresh]);
  return { snapshot, error: operationError || readError, readError, issuing, refresh, issue };
}
