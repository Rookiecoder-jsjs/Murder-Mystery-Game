import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../api/client';
import { engineCommand, gameEngine, type NativeTask, type SavedGame } from '../../api/native';
import type { Story } from '../../api/types';

export function useLocalLobby() {
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [games, setGames] = useState<SavedGame[]>([]);
  const [tasks, setTasks] = useState<NativeTask[]>([]);
  const [stories, setStories] = useState<Story[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const mounted = useRef(false);
  const pending = useRef<Promise<void> | null>(null);
  const refresh = useCallback((): Promise<void> => {
    if (pending.current) return pending.current;
    const request = Promise.allSettled([
      gameEngine.settings(), engineCommand<{ games: SavedGame[] }>({ kind: 'games' }),
      engineCommand<{ tasks: NativeTask[] }>({ kind: 'tasks' }), api.listStories(),
    ]).then(([settings, saved, unfinished, personal]) => {
      if (!mounted.current) return;
      if (settings.status === 'fulfilled') setConfigured(settings.value.configured);
      if (saved.status === 'fulfilled') setGames(saved.value.games.slice().reverse()
        .sort((a, b) => (b.last_activity ?? 0) - (a.last_activity ?? 0)));
      if (unfinished.status === 'fulfilled') setTasks(unfinished.value.tasks);
      if (personal.status === 'fulfilled') setStories(personal.value.stories.filter(story => story.origin !== 'builtin'));
      const failure = [settings, saved, unfinished, personal].find(value => value.status === 'rejected');
      setError(failure?.status === 'rejected'
        ? (failure.reason instanceof Error ? failure.reason.message : '本地资料读取失败，请重试') : '');
      setLoading(false);
    }).finally(() => { pending.current = null; });
    pending.current = request;
    return request;
  }, []);
  useEffect(() => {
    mounted.current = true;
    void refresh();
    const onResume = () => { void refresh(); };
    const onProgress = (event: Event) => {
      const task = (event as CustomEvent<NativeTask>).detail;
      setTasks(current => current.some(value => value.id === task.id)
        ? current.map(value => value.id === task.id ? task : value) : [...current, task]);
    };
    window.addEventListener('mystery:resume', onResume);
    window.addEventListener('mystery:tasks', onResume);
    window.addEventListener('mystery:library-updated', onResume);
    window.addEventListener('mystery:task-progress', onProgress);
    return () => {
      mounted.current = false;
      window.removeEventListener('mystery:resume', onResume);
      window.removeEventListener('mystery:tasks', onResume);
      window.removeEventListener('mystery:library-updated', onResume);
      window.removeEventListener('mystery:task-progress', onProgress);
    };
  }, [refresh]);
  const running = tasks.some(task => task.state === 'running' || task.state === 'queued');
  useEffect(() => {
    if (!running) return;
    let reading = false;
    const timer = window.setInterval(() => {
      if (document.hidden || reading) return;
      reading = true;
      void engineCommand<{ tasks: NativeTask[] }>({ kind: 'tasks' }).then(value => {
        if (mounted.current) setTasks(value.tasks);
        if (!value.tasks.some(task => task.state === 'running' || task.state === 'queued')) void refresh();
      }).catch(() => { /* Manual refresh and resume retain the last usable state. */ })
        .finally(() => { reading = false; });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [running, refresh]);
  return { configured, games, tasks, stories, loading, error, refresh, running };
}
