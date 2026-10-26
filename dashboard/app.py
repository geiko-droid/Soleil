import os
from pathlib import Path
import pandas as pd
import requests
import streamlit as st
import plotly.express as px

BASE = Path(__file__).resolve().parent.parent
API_URL = st.sidebar.text_input("API URL", os.getenv("API_URL", "https://soleil-7rud.onrender.com")).rstrip("/")

st.set_page_config(page_title="𝙀𝙁𝙎𝘽 𝙈𝙤𝙣𝙞𝙩𝙤𝙧𝙞𝙣𝙜 𝙎𝙮𝙨𝙩𝙚𝙢", page_icon="🦋", layout="wide")

st.markdown("""
<style>
:root {
  --navy:#111827; --navy2:#1f2937; --page:#f6f7f9; --text:#172033;
  --muted:#667085; --line:#e4e7ec; --green:#1f9d55; --blue:#078fa8;
  --amber:#e5a11a; --red:#d92d20;
}
.stApp { background:var(--page); color:var(--text); font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.block-container { padding:0 2rem 2rem; max-width:1600px; }
[data-testid="stSidebar"] { background:var(--navy); border-right:1px solid #293241; }
[data-testid="stSidebar"] * { color:#e8edf5; }
[data-testid="stSidebar"] .stRadio label {
  padding:10px 12px; border-radius:8px; margin:2px 0;
  font-size:13px; font-weight:600;
}
[data-testid="stSidebar"] .stRadio label:hover { background:#1f2937; }
.header {
  background:#fff; margin:0 -2rem 1.5rem; padding:16px 26px 15px;
  border-bottom:1px solid var(--line); display:flex; align-items:center;
}
.header-title { font-size:22px; font-weight:800; margin:0; letter-spacing:-.3px; }
.header-sub { color:var(--muted); font-size:12px; margin-top:2px; }
.title { font-size:27px; font-weight:800; margin-top:8px; letter-spacing:-.5px; }
.sub { color:var(--muted); font-size:14px; margin-bottom:20px; }
.card {
  background:#fff; border:1px solid var(--line); border-radius:13px;
  padding:17px 20px; min-height:145px; box-shadow:0 1px 2px rgba(16,24,40,.035);
}
.card.green { border-left:4px solid var(--green); }
.card.yellow { border-left:4px solid var(--amber); }
.card.cyan { border-left:4px solid var(--blue); }
.card.red { border-left:4px solid var(--red); }
.card-icon {
  float:right; width:34px; height:34px; display:flex; align-items:center;
  justify-content:center; border-radius:8px; font-size:18px; font-weight:700;
}
.icon-green { color:#188b4a; background:#ecfdf3; }
.icon-blue { color:#087f96; background:#eaf9fc; }
.icon-yellow { color:#b27b00; background:#fff8e6; }
.icon-red { color:#c52b20; background:#fff1f0; }
.label { color:#667085; font-size:13px; font-weight:600; }
.value { color:#101828; font-size:30px; font-weight:800; margin-top:16px; line-height:1.05; }
.small { color:#667085; font-size:12px; margin-top:7px; }
.success { color:#16803a; background:#ecfdf3; border:1px solid #b7ebc6; border-radius:6px; padding:3px 8px; font-size:10px; font-weight:800; letter-spacing:.2px; }
.warning { color:#9a6700; background:#fff8e6; border:1px solid #f1d28a; border-radius:6px; padding:3px 8px; font-size:10px; font-weight:800; letter-spacing:.2px; }
.critical { color:#b42318; background:#fff1f0; border:1px solid #f3b5af; border-radius:6px; padding:3px 8px; font-size:10px; font-weight:800; letter-spacing:.2px; }
.panel {
  background:#fff; border:1px solid var(--line); border-radius:13px;
  padding:18px 20px; box-shadow:0 1px 2px rgba(16,24,40,.03);
}
.panel-title { font-size:16px; font-weight:750; }
.panel-sub { color:var(--muted); font-size:12px; margin-bottom:15px; }
.kpi { background:#fff; border:1px solid var(--line); border-radius:13px; text-align:center; padding:19px 10px; box-shadow:0 1px 2px rgba(16,24,40,.03); }
.kpi-value { font-size:28px; font-weight:800; }
.kpi-label { color:var(--muted); font-size:12px; margin-top:4px; }
.alertrow { border:1px solid var(--line); border-radius:9px; padding:10px 12px; margin:7px 0; background:#fff; }
.muted { color:var(--muted); }
.stButton > button { border-radius:7px; font-weight:650; }
</style>
""", unsafe_allow_html=True)

def get(path, default=None):
    try:
        r = requests.get(API_URL + path, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception:
        return default

def post(path, data=None):
    try:
        r = requests.post(API_URL + path, data=data, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None

def badge(level):
    cls = {"Low":"success","Moderate":"warning","High":"warning","Critical":"critical"}.get(level,"success")
    return f'<span class="{cls}">{level.upper()}</span>'

def metric_card(label, value, detail, kind="green", badge_html=""):
    icons = {
        "Total Moths Detected":"🦋",
        "Infestation Status":"◉",
        "Last Capture":"◷",
        "System Uptime":"ϟ",
        "Active Traps":"⌁",
        "Average Battery":"▱",
        "Unacknowledged Alerts":"!",
        "Trap Availability":"✓",
        "Battery Health":"▱",
        "Capture Records":"▤",
        "Alerts":"!",
        "Moths Detected":"🦋",
        "Captures":"▧",
        "Avg. Moths/Capture":"⌁",
        "Battery":"▱",
        "Total Alerts":"!",
        "Unacknowledged":"!",
        "Acknowledged":"✓",
    }
    icon = icons.get(label, "•")
    icon_class = {"green":"icon-green","cyan":"icon-blue","yellow":"icon-yellow","red":"icon-red"}.get(kind,"icon-blue")
    st.markdown(f"""
    <div class="card {kind}">
      <div class="card-icon {icon_class}">{icon}</div>
      <div class="label">{label}</div>
      <div class="value">{value} {badge_html}</div>
      <div class="small">{detail}</div>
    </div>
    """, unsafe_allow_html=True)

summary = get("/api/summary", {
    "total_moths":0,"infestation_status":"Low","last_capture":None,
    "active_traps":0,"total_traps":0,"avg_battery":0,
    "unacknowledged_alerts":0,"uptime_hours":0
})
captures = get("/api/captures?limit=1000", [])
traps = get("/api/traps", [])
alerts = get("/api/alerts", [])
settings = get("/api/settings", {"threshold":50,"high_multiplier":1.5,"critical_multiplier":2})

with st.sidebar:
    st.markdown("💻 EFSB Monitor")
    st.caption("Pheromone Trap Monitoring")
    page = st.radio(
        "Navigation",
        ["🏠︎ Dashboard","🛠️ System Utilization","📊 Trap Performance","⚠️ Threat Alerts",
         "📸 Image Feed","📈 Infestation Trends","📝 Data Logging","⚙️ Settings"],
        label_visibility="visible"
    )
    st.divider()
    st.markdown("**Monitoring Site**")
    st.caption("Brgy. Wawa, Lumban, Laguna")
    st.markdown("**Status**")
    st.success("Operational")
    st.divider()

if page == "🏠︎ Dashboard":
    st.markdown("""
    <div class="header">
      <div class="header-title">EFSB Monitoring System</div>
      <div class="header-sub">Real-time 24/7 monitoring and infestation alerts</div>
    </div>
    <div class="title">System Overview</div>
    <div class="sub">Real-time trap health, moth activity, and field monitoring metrics</div>
    """, unsafe_allow_html=True)

    a,b,c,d = st.columns(4)
    with a:
        metric_card("Total Moths Detected", summary["total_moths"], "From all active traps", "green")
    with b:
        metric_card("Infestation Status", summary["infestation_status"],
                    "Current threat level", "green", badge(summary["infestation_status"]))
    with c:
        last = "No data" if not summary["last_capture"] else str(summary["last_capture"]).replace("T"," ")[:19]
        metric_card("Last Capture", last, "Latest image received", "cyan")
    with d:
        metric_card("System Uptime", f'{summary["uptime_hours"]:.1f} h', "Continuous monitoring", "cyan")

    st.write("")
    left,right = st.columns(2)
    with left:
        st.markdown('<div class="panel"><div class="panel-title">✓ Trap Network Status</div><div class="panel-sub">Health of deployed monitoring units</div>', unsafe_allow_html=True)
        st.write(f"**Active Traps**                                    {summary['active_traps']} / {summary['total_traps']} 🟢")
        st.write(f"**Average Battery**                                   {summary['avg_battery']:.0f}% 🟢")
        st.write(f"**Solar-Powered Units**                             {summary['total_traps']} ☀️")
        st.write(f"**Data Refresh**                                    Every 30 seconds")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel"><div class="panel-title">⚠ Recent Alerts</div><div class="panel-sub">Latest infestation events requiring attention</div>', unsafe_allow_html=True)
        recent = alerts[:4]
        if recent:
            for al in recent:
                sev = al.get("severity","warning").title()
                st.markdown(f'<div class="alertrow"><b>{al["trap_id"]}</b> — {al["message"]}<br><span class="muted">{str(al["created_at"]).replace("T"," ")[:19]}</span> &nbsp; {badge(sev)}</div>', unsafe_allow_html=True)
        else:
            st.info("No alerts recorded yet.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    k1,k2,k3 = st.columns(3)
    with k1:
        st.markdown(f'<div class="kpi"><div class="kpi-value" style="color:#20a34a">{summary["active_traps"]}</div><div class="kpi-label">Active Traps</div></div>', unsafe_allow_html=True)
    with k2:
        st.markdown(f'<div class="kpi"><div class="kpi-value" style="color:#e4a51c">{summary["unacknowledged_alerts"]}</div><div class="kpi-label">Active Alerts</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="kpi"><div class="kpi-value" style="color:#2470c9">{len(captures):,}</div><div class="kpi-label">Capture Records</div></div>', unsafe_allow_html=True)

elif page == "🛠️ System Utilization":
    st.markdown('<div class="title">System Utilization</div><div class="sub">Monitoring performance of the EFSB trap network</div>', unsafe_allow_html=True)
    a,b,c,d = st.columns(4)
    with a: metric_card("Trap Availability", f'{(summary["active_traps"]/summary["total_traps"]*100 if summary["total_traps"] else 0):.0f}%', "Units currently online","green")
    with b: metric_card("Battery Health", f'{summary["avg_battery"]:.0f}%', "Average across traps","cyan")
    with c: metric_card("Capture Records", f'{len(captures):,}', "Stored monitoring events","green")
    with d: metric_card("Alerts", f'{len(alerts):,}', "Generated by threshold rules","red")
    st.write("")
    st.markdown('<div class="panel"><div class="panel-title">Trap Utilization</div><div class="panel-sub">Battery and activity status by monitoring unit</div>', unsafe_allow_html=True)
    if traps:
        df = pd.DataFrame(traps)
        show = df[["trap_id","name","status","battery","last_seen"]].copy()
        show["battery"] = show["battery"].round(0).astype(int).astype(str) + "%"
        st.dataframe(show, use_container_width=True, hide_index=True)
    else:
        st.info("No traps registered.")
    st.markdown("</div>", unsafe_allow_html=True)

elif page == "📊 Trap Performance":
    st.markdown('<div class="title">Trap Performance</div><div class="sub">Hardware and capture performance of deployed units</div>', unsafe_allow_html=True)
    if traps:
        selected = st.selectbox("Select Trap", [t["trap_id"] for t in traps])
        rows = [x for x in captures if x["trap_id"] == selected]
        total = sum(x["moth_count"] for x in rows)
        avg = (total/len(rows)) if rows else 0
        a,b,c,d = st.columns(4)
        with a: metric_card("Moths Detected", total, "Selected trap","green")
        with b: metric_card("Captures", len(rows), "Images received","cyan")
        with c: metric_card("Avg. Moths/Capture", f"{avg:.1f}", "Detection average","yellow")
        with d:
            t = next(x for x in traps if x["trap_id"]==selected)
            metric_card("Battery", f'{float(t["battery"]):.0f}%', "Current battery level","cyan")
        if rows:
            df = pd.DataFrame(rows); df["captured_at"] = pd.to_datetime(df["captured_at"])
            daily = df.groupby(df["captured_at"].dt.date)["moth_count"].sum().reset_index()
            fig = px.line(daily, x="captured_at", y="moth_count", markers=True)
            fig.update_layout(height=360, xaxis_title="", yaxis_title="Moths")
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Register a trap first.")

elif page == "⚠️ Threat Alerts":
    st.markdown('<div class="title">Threat Alerts</div><div class="sub">Infestation alerts generated from moth-count thresholds</div>', unsafe_allow_html=True)
    total=len(alerts); unack=sum(1 for x in alerts if not x["acknowledged"])
    a,b,c=st.columns(3)
    with a: metric_card("Total Alerts",total,"All generated alerts","red")
    with b: metric_card("Unacknowledged",unack,"Require attention","red")
    with c: metric_card("Acknowledged",total-unack,"Resolved alerts","green")
    st.write("")
    for al in alerts:
        with st.container(border=True):
            x,y = st.columns([5,1])
            with x:
                st.write(f"**{al['trap_id']}** — {al['message']}")
                st.caption(str(al["created_at"]).replace("T"," ")[:19])
            with y:
                st.markdown(badge(al["severity"].title()), unsafe_allow_html=True)
                if not al["acknowledged"] and st.button("Acknowledge", key=f"a{al['id']}"):
                    post(f"/api/alerts/{al['id']}/ack")
                    st.rerun()

elif page == "📸 Image Feed":
    st.markdown('<div class="title">CCTV Trap Feed</div><div class="sub">Scheduled 2-hour interval captures and AI analysis</div>', unsafe_allow_html=True)
    
    trap = st.selectbox("Select Trap Unit", ["All Traps"] + [t["trap_id"] for t in traps])
    rows = [x for x in captures if trap == "All Traps" or x["trap_id"] == trap]
    
    if rows:
        latest = rows[0]
        # Construct full remote image URL pointing to Render backend
        img_path_raw = latest.get("image_path", "")
        if img_path_raw.startswith("http"):
            latest_img_url = img_path_raw
        else:
            latest_img_url = f"{API_URL}/{img_path_raw.lstrip('/')}"
        
        st.markdown("### 🔴 Live Security Snapshot")
        col_live1, col_live2 = st.columns([2, 1])
        with col_live1:
            try:
                st.image(latest_img_url, caption=f"Latest Capture - {latest['trap_id']} ({str(latest['captured_at']).replace('T',' ')[:19]})", use_container_width=True)
            except Exception:
                st.warning("Could not load latest image from server.")
        with col_live2:
            st.metric("Detected Moths", latest["moth_count"])
            st.write("**Infestation Status:**", badge(latest["infestation_level"]))
            st.write("**AI Confidence:**", f'{float(latest["confidence"]):.2f}')
            st.info("Next scheduled capture in ~2 hours.")

        st.divider()
        st.markdown("### 🗂️ Historical Archives")
        for row in rows[1:20]:
            with st.container(border=True):
                path_raw = row.get("image_path", "")
                if path_raw.startswith("http"):
                    row_img_url = path_raw
                else:
                    row_img_url = f"{API_URL}/{path_raw.lstrip('/')}"
                
                a, b = st.columns([2, 1])
                with a:
                    try:
                        st.image(row_img_url, use_container_width=True)
                    except Exception:
                        st.info("Image not available from server.")
                with b:
                    st.subheader(row["trap_id"])
                    st.metric("Moth Count", row["moth_count"])
                    st.write("Infestation:", row["infestation_level"])
                    st.write("Confidence:", f'{float(row["confidence"]):.2f}')
                    st.caption(str(row["captured_at"]).replace("T"," ")[:19])
    else: 
        st.info("No captures available yet. Waiting for the first 2-hour interval upload.")

elif page == "📈 Infestation Trends":
    st.markdown('<div class="title">Infestation Trends</div><div class="sub">Analyze EFSB population patterns over time</div>', unsafe_allow_html=True)
    trap=st.selectbox("Trap",["All Traps"]+[t["trap_id"] for t in traps])
    days=st.selectbox("Time Range",[7,30,90],format_func=lambda x:f"Last {x} Days")
    rows=[x for x in captures if trap=="All Traps" or x["trap_id"]==trap]
    if rows:
        df=pd.DataFrame(rows); df["captured_at"]=pd.to_datetime(df["captured_at"],utc=True)
        df=df[df["captured_at"] >= pd.Timestamp.now(tz="UTC")-pd.Timedelta(days=days)]
        if not df.empty:
            daily=df.groupby(df["captured_at"].dt.date)["moth_count"].sum().reset_index()
            fig=px.line(daily,x="captured_at",y="moth_count",markers=True)
            fig.update_layout(height=430,xaxis_title="",yaxis_title="Moths Detected")
            st.plotly_chart(fig,use_container_width=True)
        else: st.info("No data for this period.")
    else: st.info("No capture data available.")

elif page == "📝 Data Logging":
    st.markdown('<div class="title">Data Logging</div><div class="sub">Complete record of capture events and detection metrics</div>', unsafe_allow_html=True)
    q=st.text_input("Search trap, date, or record")
    trap=st.selectbox("Trap",["All Traps"]+[t["trap_id"] for t in traps])
    rows=captures
    if q: rows=[r for r in rows if q.lower() in str(r).lower()]
    if trap!="All Traps": rows=[r for r in rows if r["trap_id"]==trap]
    df=pd.DataFrame(rows)
    if not df.empty:
        st.dataframe(df,use_container_width=True,hide_index=True)
        st.download_button("Export CSV",df.to_csv(index=False),"efsb_capture_records.csv","text/csv")
    else: st.info("No records found.")

elif page == "⚙️ Settings":
    st.markdown('<div class="title">Settings</div><div class="sub">Configure thresholds and system parameters</div>', unsafe_allow_html=True)
    st.markdown('<div class="panel"><div class="panel-title">Alert Threshold Configuration</div><div class="panel-sub">Thresholds determine when the dashboard raises infestation alerts</div>', unsafe_allow_html=True)
    threshold=st.number_input("Moth Count Threshold",1,10000,int(settings["threshold"]))
    a,b,c=st.columns(3)
    with a: metric_card("Moderate",threshold,"moths or more","yellow")
    with b: metric_card("High",int(threshold*1.5),"moths or more","yellow")
    with c: metric_card("Critical",int(threshold*2),"moths or more","red")
    if st.button("Save Settings",type="primary"):
        if post("/api/settings",{"threshold":int(threshold),"high_multiplier":1.5,"critical_multiplier":2.0}):
            st.success("Settings saved.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.write("")
    st.markdown('<div class="panel"><div class="panel-title">System Information</div><div class="panel-sub">EFSB field monitoring deployment information</div>', unsafe_allow_html=True)
    st.write("**Monitoring Period:** Continuous 24/7 (2-hour interval snapshots)")
    st.write("**Deployment Location:** Brgy. Wawa, Lumban, Laguna")
    st.write("**Data Refresh Rate:** Every 2 hours per trap")
    st.write("**Power:** Solar-powered ESP32-CAM")
    st.write("**Monitoring Method:** Pheromone-baited trap + image-based detection")
    st.markdown("</div>", unsafe_allow_html=True)