"""Device proof: actual game rules and SQLite persistence, no server or SDK."""
import json
import sqlite3
from pathlib import Path
from app.domain.game_manager import GameManager, majority_vote
from app.domain.models import StoryArchive, CaseData, ScriptCharacter


def run(directory):
    archive = StoryArchive(id='probe', created_at='', topic='probe', title='probe',
        case=CaseData(title='probe', background='', victim='', crime='', true_killer='a', motive=''),
        characters=[ScriptCharacter(id='a', name='甲', public_identity='甲', secret='', is_killer=True),
                    ScriptCharacter(id='b', name='乙', public_identity='乙', secret='')],
        clues=[], story_content='')
    game = GameManager(archive, mode='quick')
    assert game.state.max_rounds == 3
    assert game.next_phase().value == 'investigation'
    assert majority_vote(['a', 'a', 'b'])[0] == 'a'
    db = sqlite3.connect(str(Path(directory) / 'embedding-probe.sqlite'))
    with db:
        db.execute('CREATE TABLE IF NOT EXISTS probe (id INTEGER PRIMARY KEY, phase TEXT)')
        db.execute('INSERT OR REPLACE INTO probe VALUES (1, ?)', (game.state.phase,))
    assert db.execute('SELECT phase FROM probe WHERE id=1').fetchone()[0] == 'investigation'
    db.close()
    return json.dumps({'ok': True, 'rules': 'quick/phase/vote', 'storage': 'sqlite', 'python': __import__('sys').version.split()[0]})
