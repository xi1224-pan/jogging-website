from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2 # 💡 業界標準：改用 PostgreSQL 雲端驅動
from psycopg2.extras import RealDictCursor
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🚀 智慧連線設定：直接讀取雲端平台給的資料庫網址 (DATABASE_URL)
# 如果在本機找不到，就留空（方便偵錯）
DATABASE_URL = os.getenv("DATABASE_URL", "你的本機測試憑證或留空")

def get_db_connection():
    # 直接用雲端資料庫提供的超強 URL 一鍵連線
    return psycopg2.connect(DATABASE_URL, sslmode='require')

# 💡 初始化雲端資料表
def init_db():
    if not DATABASE_URL or DATABASE_URL == "你的本機測試憑證或留空":
        return
    conn = get_db_connection()
    cursor = conn.cursor()
    # 建立 PostgreSQL 語法的資料表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS running_logs (
            id SERIAL PRIMARY KEY,
            run_date TEXT UNIQUE NOT NULL,              
            distance_km REAL NOT NULL,
            duration_text VARCHAR(10) NOT NULL,
            avg_pace_text VARCHAR(10) NOT NULL,
            speed_kmh REAL NOT NULL,            
            tag_text VARCHAR(50) DEFAULT 'as usual',     
            cadence_spm INTEGER,
            steps_count INTEGER,               
            calories_burned INTEGER,           
            nausea_percentage INTEGER DEFAULT 0,
            status_note TEXT,
            photo_base64 TEXT,                      
            temperature INTEGER,
            wind_speed REAL,
            wind_dir VARCHAR(10),
            humidity INTEGER,
            km_splits TEXT
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

try:
    init_db()
except Exception as e:
    print("資料表初始化失敗，請檢查 DATABASE_URL:", e)

class RunLog(BaseModel):
    run_date: str
    dist: str
    dur: str
    pace: str
    speed: str
    tag: Optional[str] = "as usual"
    cad: Optional[str] = ""
    steps: Optional[str] = ""     
    calories: Optional[str] = ""  
    nau: Optional[str] = "0"
    note: Optional[str] = ""
    photo: Optional[List[str]] = []
    temperature: Optional[int] = None
    wind_speed: Optional[float] = None
    wind_dir: Optional[str] = None
    humidity: Optional[int] = None
    km_splits: Optional[str] = ""

@app.get("/api/logs")
def get_all_logs():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM running_logs ORDER BY run_date ASC")
        rows = cursor.fetchall()
        
        result = {}
        for row in rows:
            d_str = row['run_date']
            photo_list = json.loads(row['photo_base64']) if row['photo_base64'] else []
            
            result[d_str] = {
                "dist": str(row['distance_km']),
                "dur": row['duration_text'],
                "pace": row['avg_pace_text'],
                "speed": str(row['speed_kmh']),
                "tag": row['tag_text'],
                "cad": str(row['cadence_spm']) if row['cadence_spm'] else "",
                "steps": str(row['steps_count']) if row['steps_count'] else "",      
                "calories": str(row['calories_burned']) if row['calories_burned'] else "",  
                "nau": str(row['nausea_percentage']),
                "note": row['status_note'],
                "photo": photo_list,
                "temperature": row['temperature'],
                "wind_speed": row['wind_speed'],
                "wind_dir": row['wind_dir'],
                "humidity": row['humidity'],
                "km_splits": row['km_splits'] if row['km_splits'] else ""
            }
        cursor.close()
        conn.close()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/logs")
def save_log(log: RunLog):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # PostgreSQL 的 💥 ON CONFLICT 覆蓋語法 (等於 MySQL 的 ON DUPLICATE KEY)
        sql = """
            INSERT INTO running_logs 
            (run_date, distance_km, duration_text, avg_pace_text, speed_kmh, tag_text, 
             cadence_spm, steps_count, calories_burned, nausea_percentage, status_note, photo_base64,
             temperature, wind_speed, wind_dir, humidity, km_splits)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_date) DO UPDATE SET
            distance_km=EXCLUDED.distance_km, duration_text=EXCLUDED.duration_text, 
            avg_pace_text=EXCLUDED.avg_pace_text, speed_kmh=EXCLUDED.speed_kmh, 
            tag_text=EXCLUDED.tag_text, cadence_spm=EXCLUDED.cadence_spm, 
            steps_count=EXCLUDED.steps_count, calories_burned=EXCLUDED.calories_burned,
            nausea_percentage=EXCLUDED.nausea_percentage, status_note=EXCLUDED.status_note,
            photo_base64=CASE WHEN EXCLUDED.photo_base64 = '[]' THEN running_logs.photo_base64 ELSE EXCLUDED.photo_base64 END,
            temperature=EXCLUDED.temperature, wind_speed=EXCLUDED.wind_speed,
            wind_dir=EXCLUDED.wind_dir, humidity=EXCLUDED.humidity,
            km_splits=EXCLUDED.km_splits
        """
        
        cadence = int(log.cad) if log.cad and log.cad.isdigit() else None
        steps = int(log.steps) if log.steps and log.steps.isdigit() else None      
        calories = int(log.calories) if log.calories and log.calories.isdigit() else None  
        nausea = int(log.nau) if log.nau and log.nau.isdigit() else 0
        photo_json = json.dumps(log.photo)
        
        val = (log.run_date, float(log.dist), log.dur, log.pace, float(log.speed), log.tag, 
               cadence, steps, calories, nausea, log.note, photo_json,
               log.temperature, log.wind_speed, log.wind_dir, log.humidity, log.km_splits)
        
        cursor.execute(sql, val)
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "雲端資料庫永久儲存成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/logs/{run_date}")
def delete_log(run_date: str):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM running_logs WHERE run_date = %s", (run_date,))
        conn.commit()
        cursor.close()
        conn.close()
        return {"status": "success", "message": "已自雲端資料庫刪除"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
