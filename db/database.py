import aiosqlite
import uuid
from datetime import datetime

async def init_db():
    async with aiosqlite.connect('prompt_battle.db') as db:
        # Таблица для пользователей
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT
            )
        ''')
        # Таблица для игр
        await db.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE,
                prompt TEXT,
                photo_id TEXT,
                status TEXT DEFAULT 'pending' 
            )
        ''')
        # Таблица для результатов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                user_id INTEGER,
                username TEXT,
                prompt_text TEXT,
                score INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        ''')
        # Новая таблица для участников
        await db.execute('''
            CREATE TABLE IF NOT EXISTS participants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                user_id INTEGER,
                UNIQUE(game_id, user_id),
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        ''')
        await db.commit()

async def add_game(prompt, photo_id):
    game_id = str(uuid.uuid4())
    async with aiosqlite.connect('prompt_battle.db') as db:
        # Завершаем все предыдущие активные игры
        await db.execute("UPDATE games SET status = 'finished' WHERE status = 'active'")
        await db.execute(
            "INSERT INTO games (game_id, prompt, photo_id, status) VALUES (?, ?, ?, 'active')",
            (game_id, prompt, photo_id)
        )
        await db.commit()
    return game_id

async def activate_game(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        await db.execute("UPDATE games SET status = 'active' WHERE game_id = ?", (game_id,))
        await db.commit()

async def stop_game(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        await db.execute("UPDATE games SET status = 'finished' WHERE game_id = ?", (game_id,))
        await db.commit()

async def get_game(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute('SELECT prompt, photo_id FROM games WHERE game_id = ?', (game_id,))
        return await cursor.fetchone()

async def get_game_status(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute('SELECT status FROM games WHERE game_id = ?', (game_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_game_prompt(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute("SELECT prompt FROM games WHERE game_id = ? AND status = 'active'", (game_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def add_participant(game_id, user_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        await db.execute("INSERT OR IGNORE INTO participants (game_id, user_id) VALUES (?, ?)", (game_id, user_id))
        await db.commit()

async def get_participants(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute("SELECT user_id FROM participants WHERE game_id = ?", (game_id,))
        return [row[0] for row in await cursor.fetchall()]

async def get_user_active_game(user_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute("""
            SELECT p.game_id FROM participants p
            JOIN games g ON p.game_id = g.game_id
            WHERE p.user_id = ? AND g.status = 'active'
        """, (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def add_or_update_user(user_id, username, first_name, last_name):
    async with aiosqlite.connect('prompt_battle.db') as db:
        await db.execute(
            '''
            INSERT INTO users (user_id, username, first_name, last_name) 
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            username=excluded.username, first_name=excluded.first_name, last_name=excluded.last_name
            ''',
            (user_id, username, first_name, last_name)
        )
        await db.commit()

async def get_all_user_ids():
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute("SELECT user_id FROM users")
        return [row[0] for row in await cursor.fetchall()]

async def add_result(game_id, user_id, username, prompt_text, score):
    async with aiosqlite.connect('prompt_battle.db') as db:
        await db.execute(
            'INSERT INTO results (game_id, user_id, username, prompt_text, score, timestamp) VALUES (?, ?, ?, ?, ?, ?)',
            (game_id, user_id, username, prompt_text, score, datetime.now())
        )
        await db.commit()

async def get_user_attempts(game_id, user_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM results WHERE game_id = ? AND user_id = ?', (game_id, user_id))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_all_results(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute(
            'SELECT user_id, username, prompt_text, score, timestamp FROM results WHERE game_id = ? ORDER BY score DESC',
            (game_id,)
        )
        return await cursor.fetchall()

async def get_best_results(game_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute('''
            SELECT r.user_id, r.username, r.prompt_text, r.score, r.timestamp
            FROM results r
            INNER JOIN (
                SELECT user_id, MAX(score) as max_score
                FROM results
                WHERE game_id = ?
                GROUP BY user_id
            ) AS best_scores ON r.user_id = best_scores.user_id AND r.score = best_scores.max_score
            WHERE r.game_id = ?
            ORDER BY r.score DESC
        ''', (game_id, game_id))
        return await cursor.fetchall()

async def get_current_active_game():
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute(
            "SELECT game_id FROM games WHERE status = 'active' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None

async def get_last_finished_game():
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute(
            "SELECT game_id FROM games WHERE status = 'finished' ORDER BY id DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None

async def has_user_won(game_id, user_id):
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute(
            'SELECT 1 FROM results WHERE game_id = ? AND user_id = ? AND score = 100',
            (game_id, user_id)
        )
        row = await cursor.fetchone()
        return row is not None

async def get_finished_games():
    async with aiosqlite.connect('prompt_battle.db') as db:
        cursor = await db.execute(
            "SELECT game_id, prompt FROM games WHERE status = 'finished' ORDER BY id DESC"
        )
        return await cursor.fetchall()
