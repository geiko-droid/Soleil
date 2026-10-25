# EFSB Monitoring System - Improved

This version follows the uploaded EFSB Monitoring reference: Dashboard, Image Feed,
Infestation Trends, Alert History, Trap Management, Data Logging, Settings,
threshold configuration, system information and REST API section.

Default threshold: 50 moths.
Moderate = threshold; High = threshold x 1.5; Critical = threshold x 2.

Run from the project root:
python -m venv .venv
.venv\Scripts\activate
pip install -r dashboard\requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Open a second terminal:
streamlit run dashboard\app.py

Dashboard: http://localhost:8501
API docs: http://localhost:8000/docs

The fallback image counter is for integration testing only. Replace it with a validated YOLO model for research results.
