"""Private, transactional mobile snapshots and operation checkpoints."""
import json
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path


class MobileStore:
    def __init__(self, directory: str) -> None:
        self.path = str(Path(directory) / 'game.sqlite')
        self.lock = threading.RLock()
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.execute('PRAGMA journal_mode=WAL')
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, table: str, key: str) -> dict | None:
        assert table in ('sessions', 'tasks', 'calls')
        with self.lock, self.connection() as db:
            row = db.execute(f'SELECT body FROM {table} WHERE id=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def put(self, table: str, key: str, body: dict) -> None:
        assert table in ('sessions', 'tasks', 'calls')
        with self.lock, self.connection() as db:
            db.execute(f'INSERT OR REPLACE INTO {table} VALUES (?,?)', (key, json.dumps(body, ensure_ascii=False)))

    def all(self, table: str) -> list[dict]:
        assert table in ('sessions', 'tasks', 'calls')
        with self.lock, self.connection() as db:
            return [json.loads(row[0]) for row in db.execute(f'SELECT body FROM {table}')]

    def commit_task(self, task: dict, snapshots: list[dict]) -> None:
        """Publish the task result and final state in the same SQLite transaction."""
        with self.lock, self.connection() as db:
            for snapshot in snapshots:
                db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?)',
                           (snapshot['game_id'], json.dumps(snapshot, ensure_ascii=False)))
            db.execute('INSERT OR REPLACE INTO tasks VALUES (?,?)',
                       (task['id'], json.dumps(task, ensure_ascii=False)))

    def save(self, snapshot: dict) -> None:
        self.put('sessions', snapshot['game_id'], snapshot)

    def load_all(self) -> list[dict]:
        return self.all('sessions')

    def delete(self, game_id: str) -> None:
        with self.lock, self.connection() as db:
            db.execute('DELETE FROM sessions WHERE id=?', (game_id,))
