import sqlite3
import json
import random
from datetime import datetime, timedelta

DB_PATH = 'splatoon3_battles.db'

MODES = ['バンカラマッチ (チャレンジ)', 'バンカラマッチ (オープン)', 'Xマッチ', 'レギュラーマッチ']
RULES = ['ガチエリア', 'ガチヤグラ', 'ガチホコバトル', 'ガチアサリ', 'ナワバリバトル']
STAGES = [
    'ユノハナ大渓谷', 'ゴンズイ地区', 'ヤガラ市場', 'マテガイ放水路',
    'ナメロウ金属', 'ヒラメが丘団地', 'キンメダイ美術館'
]
WEAPONS = ['スプラシューター', '52ガロン', 'シャープマーカー', 'ジムワイパー', 'リッター4K', 'スプラマニューバー']

GEAR_POWERS = [
    'インク効率アップ(メイン)', 'イカダッシュ速度アップ', 'アクション強化',
    '相手インク影響軽減', 'ステルスジャンプ', 'ラストスパート', 'スペシャル増加量アップ'
]

AWARDS_LIST = [
    'No.1 アタッカー', 'No.1 塗りバトラー', 'No.1 カウント進めた',
    '味方のジャンプ先 No.1', 'No.1 トドメ数', 'No.1 スペシャル増加',
    'No.1 アシスト', '注目度 No.1', 'No.1 潜伏キル'
]

def create_table_if_not_exists(conn):
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS battles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            play_time TEXT,
            rule TEXT,
            stage TEXT,
            weapon TEXT,
            raw_json TEXT
        )
    ''')
    conn.commit()

def generate_raw_json(judgement, mode):
    if judgement == 'WIN':
        knockout = random.choice(['WIN', 'NEITHER'])
        duration = random.randint(90, 300)
    elif judgement == 'LOSE':
        knockout = random.choice(['LOSE', 'NEITHER'])
        duration = random.randint(90, 300)
    else:
        knockout = 'NEITHER'
        duration = random.randint(30, 180)

    kill = random.randint(1, 18) if judgement == 'WIN' else random.randint(0, 12)
    assist = random.randint(0, 8)
    death = random.randint(1, 10) if judgement == 'WIN' else random.randint(3, 14)
    special = random.randint(1, 7)
    paint = random.randint(400, 1400)

    raw_data = {
        "mode": mode,
        "judgement": judgement,
        "knockout": knockout,
        "duration": duration,
        "my_result": {
            "kill": kill,
            "assist": assist,
            "death": death,
            "special": special,
            "paint": paint
        },
        "gears": {
            "head": {"main": random.choice(GEAR_POWERS)},
            "clothes": {"main": random.choice(GEAR_POWERS)},
            "shoes": {"main": random.choice(['ステルスジャンプ', 'イカダッシュ速度アップ'])}
        },
        "awards": [{'name': name} for name in random.sample(AWARDS_LIST, k=random.randint(1, 3))]
    }
    
    return json.dumps(raw_data, ensure_ascii=False)

def insert_test_data(count=500):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # テーブルを安全に初期化
    cursor.execute("DROP TABLE IF EXISTS battles;")
    create_table_if_not_exists(conn)

    now = datetime.now()
    records = []
    
    for i in range(count):
        play_time = (now - timedelta(minutes=i*30)).strftime('%Y-%m-%d %H:%M:%S')
        mode = random.choice(MODES)
        rule = random.choice(RULES)
        stage = random.choice(STAGES)
        weapon = random.choice(WEAPONS)
        judgement = random.choices(['WIN', 'LOSE', 'DRAW'], weights=[0.48, 0.47, 0.05])[0]

        raw_json_str = generate_raw_json(judgement, mode)
        records.append((play_time, rule, stage, weapon, raw_json_str))

    cursor.executemany('''
        INSERT INTO battles (play_time, rule, stage, weapon, raw_json)
        VALUES (?, ?, ?, ?, ?)
    ''', records)

    conn.commit()
    conn.close()
    print(f"✅ {count} 件のデータを挿入しました。")

if __name__ == '__main__':
    insert_test_data(500)