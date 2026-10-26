from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import uuid
import traceback

import cv2
import numpy as np

# =========================================================
# OPTIONAL YOLO SUPPORT
# =========================================================

try:
    from ultralytics import YOLO
    USE_YOLO = True
except ImportError:
    YOLO = None
    USE_YOLO = False


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

app = FastAPI(title="EFSB Monitoring API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "efsb.db"
IMAGE_DIR = BASE_DIR / "captured_images"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)

# Mount the captured images folder so it can be served publicly via HTTP
app.mount("/captured_images", StaticFiles(directory=str(IMAGE_DIR)), name="captured_images")

MODEL_PATH = BASE_DIR.parent / "models" / "best.pt"

# Load the YOLO model if it exists.
model = None

if USE_YOLO and MODEL_PATH.exists():
    try:
        model = YOLO(str(MODEL_PATH))
        print(f"YOLO model loaded: {MODEL_PATH}")
    except Exception:
        print("WARNING: YOLO model could not be loaded.")
        traceback.print_exc()
        model = None

if model is None:
    print("Using fallback image detection.")


# =========================================================
# DATABASE CONNECTION AND INITIALIZATION
# =========================================================

def conn():
    return sqlite3.connect(DB_PATH, timeout=30)


def init_db():
    connection = conn()

    try:
        connection.execute("""
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

        connection.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trap_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT DEFAULT 'warning',
                acknowledged INTEGER DEFAULT 0
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                threshold INTEGER DEFAULT 50,
                high_multiplier REAL DEFAULT 1.5,
                critical_multiplier REAL DEFAULT 2.0
            )
        """)

        connection.execute("""
            INSERT OR IGNORE INTO settings (
                id, threshold, high_multiplier, critical_multiplier
            )
            VALUES (1, 50, 1.5, 2.0)
        """)

        connection.commit()
        print(f"Database initialized: {DB_PATH}")

    except Exception:
        connection.rollback()
        traceback.print_exc()
        raise

    finally:
        connection.close()


init_db()


# =========================================================
# SETTINGS
# =========================================================

def get_settings():
    connection = conn()

    try:
        row = connection.execute("""
            SELECT threshold, high_multiplier, critical_multiplier
            FROM settings
            WHERE id = 1
        """).fetchone()

        if row:
            return {
                "threshold": row[0],
                "high_multiplier": row[1],
                "critical_multiplier": row[2]
            }

        return {
            "threshold": 50,
            "high_multiplier": 1.5,
            "critical_multiplier": 2.0
        }

    finally:
        connection.close()


# =========================================================
# INFESTATION LEVEL
# =========================================================

def level(count: int):
    settings = get_settings()

    if count >= settings["threshold"] * settings["critical_multiplier"]:
        return "Critical"

    if count >= settings["threshold"] * settings["high_multiplier"]:
        return "High"

    if count >= settings["threshold"]:
        return "Moderate"

    return "Low"


# =========================================================
# FALLBACK IMAGE DETECTION
# =========================================================

def fallback_count(data: bytes):
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_GRAYSCALE)

    if image is None:
        raise ValueError("The uploaded image could not be decoded.")

    blurred = cv2.GaussianBlur(image, (5, 5), 0)

    _, mask = cv2.threshold(
        blurred,
        75,
        255,
        cv2.THRESH_BINARY_INV
    )

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    valid_contours = [
        contour for contour in contours
        if 128 < cv2.contourArea(contour) < 20000
    ]

    count = min(len(valid_contours), 99)

    # Placeholder value only; not a trained-model confidence score.
    confidence = 0.25 if count > 0 else 0.0

    return count, confidence


# =========================================================
# YOLO DETECTION
# =========================================================

def yolo_count(image_path: Path):
    if model is None:
        raise RuntimeError("The YOLO model is not available.")

    result = model.predict(
        source=str(image_path),
        verbose=False
    )[0]

    boxes = result.boxes

    if boxes is None or len(boxes) == 0:
        return 0, 0.0

    confidences = boxes.conf.detach().cpu().numpy().tolist()

    count = len(confidences)
    confidence = (
        float(np.mean(confidences))
        if confidences else 0.0
    )

    return count, confidence


# =========================================================
# ROOT AND HEALTH CHECK
# =========================================================

@app.get("/")
def root():
    return {
        "status": "running",
        "service": "EFSB Monitoring API"
    }


@app.get("/api/health")
def health():
    return {
        "status": "running",
        "database_exists": DB_PATH.exists(),
        "image_directory_exists": IMAGE_DIR.exists(),
        "yolo_enabled": model is not None
    }


# =========================================================
# CAPTURE AND PROCESS IMAGE
# =========================================================

@app.post("/api/capture")
async def capture(request: Request):
    connection = None
    image_path = None

    try:
        data = await request.body()

        if not data:
            raise HTTPException(
                status_code=400,
                detail="Empty image data received."
            )

        trap_id = request.headers.get(
            "X-Trap-Id",
            "TRAP-001"
        )

        try:
            battery = float(
                request.headers.get("X-Battery", "0.0")
            )
        except (ValueError, TypeError):
            battery = 0.0

        captured_at = datetime.now(timezone.utc)

        filename = (
            f"{captured_at.strftime('%Y%m%d_%H%M%S')}_"
            f"{uuid.uuid4().hex[:8]}.jpg"
        )

        image_path = IMAGE_DIR / filename

        image = cv2.imdecode(
            np.frombuffer(data, dtype=np.uint8),
            cv2.IMREAD_COLOR
        )

        if image is None:
            raise HTTPException(
                status_code=400,
                detail="Invalid or corrupted image received."
            )

        # Save the original uploaded image.
        image_path.write_bytes(data)

        # Run the available detection method.
        if model is not None:
            count, confidence = yolo_count(image_path)
            processing_mode = "YOLO"
        else:
            count, confidence = fallback_count(data)
            processing_mode = "fallback"

        infestation = level(count)

        print(
            f"Capture received | Trap={trap_id} | "
            f"Moths={count} | Mode={processing_mode} | "
            f"Infestation={infestation}"
        )

        connection = conn()

        # Store relative URL path for the image feed
        db_image_path = f"/captured_images/{filename}"

        connection.execute("""
            INSERT INTO captures (
                trap_id,
                captured_at,
                image_path,
                moth_count,
                confidence,
                processing_mode,
                infestation_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            trap_id,
            captured_at.isoformat(),
            db_image_path,
            count,
            confidence,
            processing_mode,
            infestation
        ))

        settings = get_settings()

        if count >= settings["threshold"]:
            connection.execute("""
                INSERT INTO alerts (
                    trap_id,
                    created_at,
                    message,
                    severity
                )
                VALUES (?, ?, ?, ?)
            """, (
                trap_id,
                captured_at.isoformat(),
                (
                    f"{count} moths detected in one capture "
                    f"({infestation} infestation level)."
                ),
                infestation.lower()
            ))

        connection.commit()

        return {
            "ok": True,
            "trap_id": trap_id,
            "moth_count": count,
            "confidence": confidence,
            "processing_mode": processing_mode,
            "infestation_level": infestation,
            "captured_at": captured_at.isoformat(),
            "image": db_image_path
        }

    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise

    except Exception as error:
        if connection is not None:
            try:
                connection.rollback()
            except sqlite3.Error:
                pass

        print("CAPTURE ERROR:")
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"{type(error).__name__}: {error}"
        )

    finally:
        if connection is not None:
            connection.close()


# =========================================================
# GET RECENT CAPTURES
# =========================================================

@app.get("/api/captures")
def get_captures(limit: int = 100):
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 1000."
        )

    connection = conn()

    try:
        rows = connection.execute("""
            SELECT
                id,
                trap_id,
                captured_at,
                image_path,
                moth_count,
                confidence,
                processing_mode,
                infestation_level
            FROM captures
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        columns = [
            "id",
            "trap_id",
            "captured_at",
            "image_path",
            "moth_count",
            "confidence",
            "processing_mode",
            "infestation_level"
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        connection.close()


# =========================================================
# GET ALERTS
# =========================================================

@app.get("/api/alerts")
def get_alerts():
    connection = conn()

    try:
        rows = connection.execute("""
            SELECT
                id,
                trap_id,
                created_at,
                message,
                severity,
                acknowledged
            FROM alerts
            ORDER BY id DESC
        """).fetchall()

        columns = [
            "id",
            "trap_id",
            "created_at",
            "message",
            "severity",
            "acknowledged"
        ]

        return [
            dict(zip(columns, row))
            for row in rows
        ]

    finally:
        connection.close()


# =========================================================
# ACKNOWLEDGE ALERT
# =========================================================

@app.put("/api/alerts/{alert_id}/ack")
def ack(alert_id: int):
    connection = conn()

    try:
        cursor = connection.execute("""
            UPDATE alerts
            SET acknowledged = 1
            WHERE id = ?
        """, (alert_id,))

        if cursor.rowcount == 0:
            raise HTTPException(
                status_code=404,
                detail="Alert not found."
            )

        connection.commit()

        return {
            "ok": True,
            "alert_id": alert_id,
            "acknowledged": True
        }

    except HTTPException:
        connection.rollback()
        raise

    except Exception:
        connection.rollback()
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail="Failed to acknowledge alert."
        )
    finally:
        connection.close()