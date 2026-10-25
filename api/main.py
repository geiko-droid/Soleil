from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import uuid
import cv2
import numpy as np

# Optional YOLO support
try:
    from ultralytics import YOLO
    USE_YOLO = True
except ImportError:
    USE_YOLO = False

app = FastAPI(title="EFSB Monitoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "efsb.db"
IMAGE_DIR = BASE_DIR / "captured_images"
IMAGE_DIR.mkdir(exist_ok=True)

MODEL_PATH = BASE_DIR.parent / "models" / "best.pt"
r = YOLO(str(MODEL_PATH)) if (USE_YOLO and MODEL_PATH.exists()) else None

def conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    c = conn()
    c.execute("""
    CREATE TABLE IF NOT EXISTS captures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trap_id TEXT NOT NULL,
        captured_at TEXT NOT NULL,
        image_path TEXT NOT NULL,
        moth_count INTEGER DEFAULT 0,
        confidence REAL DEFAULT 0.0,
        processing_mode TEXT DEFAULT 'fallback',
        infestation_level TEXT DEFAULT 'Low'
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trap_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        message TEXT NOT NULL,
        severity TEXT DEFAULT 'warning',
        acknowledged INTEGER DEFAULT 0
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY CHECK (id=1),
        threshold INTEGER DEFAULT 50,
        high_multiplier REAL DEFAULT 1.5,
        critical_multiplier REAL DEFAULT 2.0
    )
    """)
    c.execute("""
    INSERT OR IGNORE INTO settings (id, threshold, high_multiplier, critical_multiplier) 
    VALUES (1, 50, 1.5, 2.0)
    """)
    c.commit()
    c.close()

init_db()

def get_settings():
    c = conn()
    row = c.execute("SELECT threshold, high_multiplier, critical_multiplier FROM settings WHERE id=1").fetchone()
    c.close()
    if row:
        return {"threshold": row[0], "high_multiplier": row[1], "critical_multiplier": row[2]}
    return {"threshold": 50, "high_multiplier": 1.5, "critical_multiplier": 2.0}

def level(count: int):
    s = get_settings()
    if count >= s["threshold"] * s["critical_multiplier"]:
        return "Critical"
    if count >= s["threshold"] * s["high_multiplier"]:
        return "High"
    if count >= s["threshold"]:
        return "Moderate"
    return "Low"

def fallback_count(data: bytes):
    arr = np.frombuffer(data, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0, 0.0
    blur = cv2.GaussianBlur(img, (5, 5), 0)
    _, mask = cv2.threshold(blur, 75, 255, cv2.THRESH_BINARY_INV)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_cnts = [c for c in cnts if 128 < cv2.contourArea(c) < 20000]
    count = min(len(valid_cnts), 99)
    return count, 0.25

def yolo_count(path: Path):
    if not r:
        return 0, 0.0
    results = r.predict(source=str(path), verbose=False)[0]
    boxes = results.boxes
    if boxes is None or len(boxes) == 0:
        return 0, 0.0
    confs = boxes.conf.detach().cpu().numpy().tolist()
    return len(confs), float(np.mean(confs)) if confs else 0.0

@app.get("/")
def root():
    return {"status": "running", "service": "EFSB Monitoring API"}

@app.post("/api/capture")
async def capture(request: Request):
    try:
        data = await request.body()
        if not data:
            raise HTTPException(400, "Empty image data received")
            
        trap_id = request.headers.get("X-Trap-Id", "TRAP-001")
        try:
            battery = float(request.headers.get("X-Battery", "0.0"))
        except ValueError:
            battery = 0.0
            
        now = datetime.now(timezone.utc)
        filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        path = IMAGE_DIR / filename
        path.write_bytes(data)
        
        if USE_YOLO and MODEL_PATH.exists():
            count, conf = yolo_count(path)
            mode = "YOLO"
        else:
            count, conf = fallback_count(data)
            mode = "fallback"
            
        lev = level(count)
        c = conn()
        
        c.execute("""
            INSERT INTO captures (trap_id, captured_at, image_path, moth_count, confidence, processing_mode, infestation_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (trap_id, now.isoformat(), filename, count, conf, mode, lev))
        
        s = get_settings()
        if count >= s["threshold"]:
            c.execute("""
                INSERT INTO alerts (trap_id, created_at, message, severity)
                VALUES (?, ?, ?, ?)
            """, (trap_id, now.isoformat(), f"{count} moths detected in one capture ({lev} infestation level).", lev.lower()))
        
        c.commit()
        c.close()
        
        return {
            "ok": True,
            "trap_id": trap_id,
            "moth_count": count,
            "confidence": conf,
            "processing_mode": mode,
            "infestation_level": lev,
            "captured_at": now.isoformat(),
            "image": filename
        }
    except Exception as e:
        print(f"CAPTURE ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/alerts/{alert_id}/ack")
def ack(alert_id: int):
    c = conn()
    c.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    c.commit()
    c.close()
    return {"ok": True}