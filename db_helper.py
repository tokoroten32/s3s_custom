import sqlite3
import json

DB_PATH = 'splatoon3_battles.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS battles (
            id TEXT PRIMARY KEY,
            play_time TEXT,
            rule TEXT,
            stage TEXT,
            weapon TEXT,
            raw_json TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_result(result_id, payload):
    try:
        # stat.ink用ペイロードから元のSplatNet3のJSON文字列を取得
        raw_json_str = payload.get('splatnet_json')
        if not raw_json_str:
            return
            
        raw_data = json.loads(raw_json_str)

        # サーモンランのデータ（vsRuleが存在しない）の場合はスキップ
        if 'vsRule' not in raw_data:
            return

        b_id = result_id or raw_data.get('id')
        play_time = raw_data.get('playedTime')
        rule = raw_data.get('vsRule', {}).get('name')
        stage = raw_data.get('vsStage', {}).get('name')
        
        # 自分のブキ情報を取得（myTeamのplayers配列からisMyselfがTrueのものを抽出）
        weapon = None
        my_team = raw_data.get('myTeam', {})
        for player in my_team.get('players', []):
            if player.get('isMyself'):
                weapon = player.get('weapon', {}).get('name')
                break
        
        # DBにはstat.inkフォーマットではなく、SplatNet3の生JSONをそのまま保存
        save_json = raw_json_str

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT OR IGNORE INTO battles (id, play_time, rule, stage, weapon, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (b_id, play_time, rule, stage, weapon, save_json))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB Helper] Error: {e}")

init_db()