from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

app = FastAPI()

# 🛡️ 允許你的前端網頁跨網域連線 (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 💡 從環境變數抓取真實 Neon 連線字串與自訂管理員密碼
DATABASE_URL = os.environ.get("DATABASE_URL")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123456") # 預設防呆密碼

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

class LogPayload(BaseModel):
    run_date: str
    dist: str
    dur: str
    pace: str
    speed: str
    tag: Optional[str] = "as usual"
    cad: Optional[str] = None
    steps: Optional[str] = None
    calories: Optional[str] = None
    nau: Optional[str] = None
    note: Optional[str] = None
    photo: Optional[List[str]] = []
    temperature: Optional[int] = None
    humidity: Optional[int] = None
    wind_speed: Optional[float] = None
    wind_dir: Optional[str] = None
    km_splits: Optional[str] = ""

# 🔑 建立一個密碼驗證的依賴函式
def verify_admin_password(x_password: Optional[str] = Header(None)):
    if not x_password or x_password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="🔒 密碼驗證失敗，拒絕連線修改！")
    return True

# 🟢 1. 撈取資料 (所有人都可以看，不鎖密碼)
@app.get("/api/logs")
def get_logs():
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("SELECT * FROM running_logs")
        rows = cursor.fetchall()
        
        db_dict = {}
        for row in rows:
            photo_list = []
            if row['photo_base64']:
                try:
                    photo_list = json.loads(row['photo_base64'])
                except:
                    photo_list = []

            db_dict[row['run_date']] = {
                "dist": row['distance_km'],
                "dur": row['duration_text'],
                "pace": row['avg_pace_text'],
                "speed": row['speed_kmh'],
                "tag": row['tag_text'],
                "cad": str(row['cadence_spm']) if row['cadence_spm'] is not None else "",
                "steps": str(row['steps_count']) if row['steps_count'] is not None else "",
                "calories": str(row['calories_burned']) if row['calories_burned'] is not None else "",
                "nau": str(row['nausea_percentage']) if row['nausea_percentage'] is not None else "0",
                "note": row['status_note'],
                "photo": photo_list,
                "temperature": row['temperature'],
                "humidity": row['humidity'],
                "wind_speed": row['wind_speed'],
                "wind_dir": row['wind_dir'],
                "km_splits": row['km_splits']
            }
        return db_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# 🟡 2. 新增或修改資料 
@app.post("/api/logs")
def save_log(payload: LogPayload, authenticated: bool = Depends(verify_admin_password)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        photo_json = json.dumps(payload.photo) if payload.photo else '[]'
        
        sql = """
            INSERT INTO running_logs 
            (run_date, distance_km, duration_text, avg_pace_text, speed_kmh, tag_text, 
             cadence_spm, steps_count, calories_burned, nausea_percentage, status_note, photo_base64,
             temperature, wind_speed, wind_dir, humidity, km_splits)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (run_date) DO UPDATE SET
                distance_km = EXCLUDED.distance_km,
                duration_text = EXCLUDED.duration_text,
                avg_pace_text = EXCLUDED.avg_pace_text,
                speed_kmh = EXCLUDED.speed_kmh,
                tag_text = EXCLUDED.tag_text,
                cadence_spm = EXCLUDED.cadence_spm,
                steps_count = EXCLUDED.steps_count,
                calories_burned = EXCLUDED.calories_burned,
                nausea_percentage = EXCLUDED.nausea_percentage,
                status_note = EXCLUDED.status_note,
                photo_base64 = EXCLUDED.photo_base64,
                temperature = EXCLUDED.temperature,
                wind_speed = EXCLUDED.wind_speed,
                wind_dir = EXCLUDED.wind_dir,
                humidity = EXCLUDED.humidity,
                km_splits = EXCLUDED.km_splits
        """
        
        val = (
            payload.run_date,
            float(payload.dist),
            payload.dur,
            payload.pace,
            float(payload.speed),
            payload.tag,
            int(payload.cad) if payload.cad else None,
            int(payload.steps) if payload.steps else None,
            int(payload.calories) if payload.calories else None,
            int(payload.nau) if payload.nau else 0,
            payload.note,
            photo_json,
            payload.temperature,
            payload.wind_speed,
            payload.wind_dir,
            payload.humidity,
            payload.km_splits
        )
        
        cursor.execute(sql, val)
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# 🔴 3. 刪除資料
@app.delete("/api/logs/{run_date}")
def delete_log(run_date: str, authenticated: bool = Depends(verify_admin_password)):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM running_logs WHERE run_date = %s", (run_date,))
        conn.commit()
        return {"status": "success"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
