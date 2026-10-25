import os, sqlite3, uuid, time
from datetime import datetime, timezone
from pathlib import Path
import cv2, numpy as np
from fastapi import FastAPI, File, Form, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

BASE=Path(__file__).resolve().parent.parent
DB=BASE/"moth_monitoring.db"; IMAGE_DIR=BASE/"captured_images"; IMAGE_DIR.mkdir(exist_ok=True)
USE_YOLO=os.getenv("USE_YOLO","false").lower()=="true"; MODEL_PATH=BASE/"models"/"moth_detector.pt"
START=time.time()

app=FastAPI(title="EFSB Monitoring API",version="1.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init_db():
    c=conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS traps(trap_id TEXT PRIMARY KEY,name TEXT NOT NULL,location TEXT DEFAULT '',status TEXT DEFAULT 'active',battery REAL DEFAULT 0,last_seen TEXT);
    CREATE TABLE IF NOT EXISTS captures(id INTEGER PRIMARY KEY AUTOINCREMENT,trap_id TEXT NOT NULL,captured_at TEXT NOT NULL,image_path TEXT,moth_count INTEGER DEFAULT 0,confidence REAL DEFAULT 0,processing_mode TEXT DEFAULT 'fallback',infestation_level TEXT DEFAULT 'Low');
    CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY AUTOINCREMENT,trap_id TEXT NOT NULL,created_at TEXT NOT NULL,message TEXT NOT NULL,severity TEXT DEFAULT 'warning',acknowledged INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),threshold INTEGER DEFAULT 50,high_multiplier REAL DEFAULT 1.5,critical_multiplier REAL DEFAULT 2.0);
    INSERT OR IGNORE INTO settings(id,threshold,high_multiplier,critical_multiplier) VALUES(1,50,1.5,2.0);
    """)
    c.commit(); c.close()
init_db()

def get_settings():
    c=conn(); r=c.execute("SELECT * FROM settings WHERE id=1").fetchone(); c.close(); return dict(r)

def level(count):
    s=get_settings(); t=s["threshold"]
    if count>=t*s["critical_multiplier"]: return "Critical"
    if count>=t*s["high_multiplier"]: return "High"
    if count>=t: return "Moderate"
    return "Low"

def fallback_count(data):
    arr=np.frombuffer(data,np.uint8); img=cv2.imdecode(arr,cv2.IMREAD_GRAYSCALE)
    if img is None:return 0,0.0
    blur=cv2.GaussianBlur(img,(5,5),0); _,mask=cv2.threshold(blur,75,255,cv2.THRESH_BINARY_INV)
    cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    return min(sum(1 for c in cs if 120<=cv2.contourArea(c)<=20000),99),0.25

def yolo_count(path):
    from ultralytics import YOLO
    r=YOLO(str(MODEL_PATH)).predict(source=str(path),verbose=False)[0]
    if r.boxes is None:return 0,0.0
    conf=r.boxes.conf.detach().cpu().numpy().tolist()
    return len(conf),float(np.mean(conf)) if conf else 0.0

@app.get("/")
def root(): return {"status":"online","service":"EFSB Monitoring API"}

@app.get("/api/settings")
def settings(): return get_settings()

@app.post("/api/settings")
def update_settings(threshold:int=Form(...),high_multiplier:float=Form(1.5),critical_multiplier:float=Form(2.0)):
    c=conn(); c.execute("UPDATE settings SET threshold=?,high_multiplier=?,critical_multiplier=? WHERE id=1",(threshold,high_multiplier,critical_multiplier)); c.commit(); c.close(); return get_settings()

@app.get("/api/summary")
def summary():
    c=conn()
    total=c.execute("SELECT COALESCE(SUM(moth_count),0)n FROM captures").fetchone()["n"]
    active=c.execute("SELECT COUNT(*)n FROM traps WHERE status='active'").fetchone()["n"]
    total_traps=c.execute("SELECT COUNT(*)n FROM traps").fetchone()["n"]
    unack=c.execute("SELECT COUNT(*)n FROM alerts WHERE acknowledged=0").fetchone()["n"]
    avg=c.execute("SELECT COALESCE(AVG(battery),0)n FROM traps WHERE status='active'").fetchone()["n"]
    last=c.execute("SELECT captured_at,infestation_level FROM captures ORDER BY captured_at DESC LIMIT 1").fetchone()
    c.close()
    return {"total_moths":int(total),"infestation_status":last["infestation_level"] if last else "Low","last_capture":last["captured_at"] if last else None,"active_traps":active,"total_traps":total_traps,"avg_battery":round(float(avg),1),"unacknowledged_alerts":unack,"uptime_hours":round((time.time()-START)/3600,1)}

@app.get("/api/traps")
def traps():
    c=conn(); rows=c.execute("SELECT * FROM traps ORDER BY trap_id").fetchall(); c.close(); return [dict(r) for r in rows]

@app.get("/api/captures")
def captures(limit:int=1000):
    c=conn(); rows=c.execute("SELECT * FROM captures ORDER BY captured_at DESC LIMIT ?",(limit,)).fetchall(); c.close(); return [dict(r) for r in rows]

@app.get("/api/alerts")
def alerts():
    c=conn(); rows=c.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT 500").fetchall(); c.close(); return [dict(r) for r in rows]

@app.post("/api/traps/register")
def register_trap(trap_id:str=Form(...),name:str=Form(...),location:str=Form("")):
    now=datetime.now(timezone.utc).isoformat(); c=conn()
    c.execute("""INSERT INTO traps(trap_id,name,location,status,last_seen) VALUES(?,?,?,?,?)
    ON CONFLICT(trap_id) DO UPDATE SET name=excluded.name,location=excluded.location,status='active',last_seen=excluded.last_seen""",(trap_id,name,location,"active",now))
    c.commit(); c.close(); return {"ok":True,"trap_id":trap_id}

@app.post("/api/capture")
async def capture(
    image: UploadFile = File(None),
    trap_id: str = Form("TRAP-001"),
    battery: float = Form(0.0),
    request: Request = None
):
    if image is not None:
        data = await image.read()
    else:
        data = await request.body()

    if not data: 
        raise HTTPException(400, "Empty image data received")
        
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
    c.execute("""INSERT INTO traps(trap_id,name,location,status,battery,last_seen) VALUES(?,?,?,?,?,?)
    ON CONFLICT(trap_id) DO UPDATE SET battery=excluded.battery,last_seen=excluded.last_seen,status='active'""",(trap_id, trap_id, "Brgy. Wawa, Lumban, Laguna", "active", battery, now.isoformat()))
    
    c.execute("""INSERT INTO captures(trap_id,captured_at,image_path,moth_count,confidence,processing_mode,infestation_level) VALUES(?,?,?,?,?,?,?)""",(trap_id, now.isoformat(), filename, count, conf, mode, lev))
    
    s = get_settings()
    if count >= s["threshold"]:
        c.execute("INSERT INTO alerts(trap_id,created_at,message,severity) VALUES(?,?,?,?)",(trap_id, now.isoformat(), f"{count} moths detected in one capture ({lev} infestation level).", lev.lower()))
    
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

@app.post("/api/alerts/{alert_id}/ack")
def ack(alert_id:int):
    c=conn(); c.execute("UPDATE alerts SET acknowledged=1 WHERE id=?",(alert_id,)); c.commit(); c.close(); return {"ok":True}