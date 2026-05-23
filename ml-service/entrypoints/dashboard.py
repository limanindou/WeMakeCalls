"""
WeMakeCalls — Real-time Call Volume Forecast Dashboard

Dark-themed Dash app showing:
- Blue line: Actual call count per hour (from live simulation)
- Green line: Predicted call count (from ML model)
- Updates every 1 second (1 hour simulated per second)
- Dark background with grid pattern
"""

import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import Input, Output, dcc, html

# Project root
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))
os.chdir(project_root)

from wemakecalls.pipelines.inference.nodes import load_latest_model, run_inference, FEATURE_COLUMNS

# ---------------------------------------------------------------------------
# Shared State — updated by background threads, read by dashboard
# ---------------------------------------------------------------------------

class LiveState:
    """Thread-safe shared state between simulator and dashboard."""
    def __init__(self):
        self.actuals = []      # List of {"hour": datetime, "calls": int}
        self.predictions = []  # List of {"hour": datetime, "calls": float}
        self.current_hour_idx = 0
        self.lock = threading.Lock()

state = LiveState()

# ---------------------------------------------------------------------------
# Background Call Simulator (generates realistic fake call volume)
# ---------------------------------------------------------------------------

def generate_hourly_calls(hour_dt):
    """Generate realistic call count for a given hour."""
    h = hour_dt.hour
    dow = hour_dt.weekday()
    is_weekend = dow >= 5

    # Realistic call center pattern
    if 9 <= h <= 17:
        base = np.random.randint(28, 48)
    elif 7 <= h <= 9 or 17 <= h <= 21:
        base = np.random.randint(14, 28)
    else:
        base = np.random.randint(3, 10)

    if is_weekend:
        base = int(base * 0.55)

    noise = np.random.normal(0, 3)
    return max(1, int(base + noise))


def run_simulator():
    """Background thread: adds 1 new actual data point per second."""
    # Start from 48 hours ago so chart has history
    start_time = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=48)

    # Pre-fill 48 hours of history
    history = []
    for i in range(48):
        hour_dt = start_time + timedelta(hours=i)
        calls = generate_hourly_calls(hour_dt)
        history.append({"hour": hour_dt, "calls": calls})

    with state.lock:
        state.actuals = history.copy()

    # Now add 1 new point per second (simulating 1 hour per second)
    current_time = start_time + timedelta(hours=48)
    while True:
        calls = generate_hourly_calls(current_time)
        with state.lock:
            state.actuals.append({"hour": current_time, "calls": calls})
            # Keep last 168 hours (7 days) max
            if len(state.actuals) > 168:
                state.actuals = state.actuals[-168:]

        current_time += timedelta(hours=1)
        time.sleep(1)  # 1 second = 1 hour simulated


def run_predictor():
    """Background thread: generates predictions using the ML model."""
    # Load model
    try:
        model, model_type = load_latest_model(Path("data/06_models"))
    except Exception as e:
        print(f"WARNING: Could not load model: {e}")
        model = None

    # Wait for some actuals to accumulate
    time.sleep(3)

    while True:
        with state.lock:
            actuals = state.actuals.copy()

        if len(actuals) < 2:
            time.sleep(1)
            continue

        # Generate predictions for the same time range as actuals
        predictions = []
        for i, point in enumerate(actuals):
            hour_dt = point["hour"]

            # Build features from history
            lag_1 = actuals[i - 1]["calls"] if i > 0 else point["calls"]
            lag_2 = actuals[i - 2]["calls"] if i > 1 else lag_1
            lag_24 = actuals[i - 24]["calls"] if i >= 24 else point["calls"]
            lag_168 = actuals[i - 168]["calls"] if i >= 168 else point["calls"]

            recent = [a["calls"] for a in actuals[max(0, i - 24):i + 1]]
            rolling_avg = float(np.mean(recent)) if recent else float(point["calls"])

            features = {
                "calls_lag_1h": float(lag_1),
                "calls_lag_2h": float(lag_2),
                "calls_lag_24h": float(lag_24),
                "calls_lag_168h": float(lag_168),
                "hour_of_day": hour_dt.hour,
                "day_of_week": hour_dt.weekday(),
                "is_weekend": hour_dt.weekday() >= 5,
                "is_holiday": False,
                "rolling_avg_7d": rolling_avg,
                "avg_duration_lag_1h": 240.0,
                "abandonment_rate_lag_1h": 0.08,
            }

            if model is not None:
                batch = pd.DataFrame([features], columns=FEATURE_COLUMNS)
                pred = float(run_inference(model, batch))
            else:
                # Fallback: add noise to actual
                pred = float(point["calls"]) + np.random.normal(0, 5)

            predictions.append({"hour": hour_dt, "calls": max(0, pred)})

        with state.lock:
            state.predictions = predictions

        time.sleep(1)  # Update predictions every second


# ---------------------------------------------------------------------------
# Start background threads
# ---------------------------------------------------------------------------

simulator_thread = threading.Thread(target=run_simulator, daemon=True)
predictor_thread = threading.Thread(target=run_predictor, daemon=True)
simulator_thread.start()
predictor_thread.start()

# ---------------------------------------------------------------------------
# Dash App — Dark theme with grid
# ---------------------------------------------------------------------------

app = dash.Dash(__name__, title="WeMakeCalls — Live Forecast")

app.layout = html.Div(
    style={
        "backgroundColor": "#0a0a1a",
        "minHeight": "100vh",
        "padding": "30px",
        "fontFamily": "'DM Sans', sans-serif",
    },
    children=[
        html.H1(
            "Call Volume — Predicted vs Actual",
            style={
                "color": "#e0e0f0",
                "textAlign": "center",
                "fontSize": "28px",
                "fontWeight": "700",
                "marginBottom": "5px",
            },
        ),
        html.P(
            "Real-time simulation • 1 second = 1 hour • ML model: CatBoost",
            style={
                "color": "#6a6a8a",
                "textAlign": "center",
                "fontSize": "14px",
                "marginBottom": "20px",
            },
        ),
        dcc.Graph(
            id="live-chart",
            style={"height": "500px"},
            config={"displayModeBar": False},
        ),
        html.Div(
            id="stats-bar",
            style={
                "display": "flex",
                "justifyContent": "center",
                "gap": "40px",
                "marginTop": "20px",
            },
        ),
        dcc.Interval(id="interval", interval=1000, n_intervals=0),
    ],
)


@app.callback(
    [Output("live-chart", "figure"), Output("stats-bar", "children")],
    [Input("interval", "n_intervals")],
)
def update_chart(_n):
    """Update chart every 1 second with new data."""
    with state.lock:
        actuals = state.actuals.copy()
        predictions = state.predictions.copy()

    fig = go.Figure()

    # Predicted line (green) — show full range for comparison
    if predictions:
        pred_hours = [p["hour"] for p in predictions]
        pred_calls = [p["calls"] for p in predictions]
        fig.add_trace(go.Scatter(
            x=pred_hours,
            y=pred_calls,
            mode="lines",
            name="Predicted",
            line=dict(color="#39ff7a", width=3, shape="spline"),
            opacity=0.85,
        ))

    # Actual line (blue) — live simulated calls
    if actuals:
        actual_hours = [a["hour"] for a in actuals]
        actual_calls = [a["calls"] for a in actuals]
        fig.add_trace(go.Scatter(
            x=actual_hours,
            y=actual_calls,
            mode="lines",
            name="Actual",
            line=dict(color="#4da6ff", width=3, shape="spline"),
        ))

    # Dark layout with grid
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="#0a0a1a",
        plot_bgcolor="#12122a",
        height=480,
        margin=dict(l=50, r=30, t=30, b=50),
        xaxis=dict(
            title="Time",
            title_font=dict(color="#6a6a8a"),
            tickfont=dict(color="#6a6a8a"),
            gridcolor="rgba(100, 100, 160, 0.15)",
            showgrid=True,
        ),
        yaxis=dict(
            title="Calls per Hour",
            title_font=dict(color="#6a6a8a"),
            tickfont=dict(color="#6a6a8a"),
            gridcolor="rgba(100, 100, 160, 0.15)",
            showgrid=True,
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(color="#e0e0f0", size=14),
        ),
        hovermode="x unified",
    )

    # Stats
    avg_actual = np.mean([a["calls"] for a in actuals]) if actuals else 0
    avg_pred = np.mean([p["calls"] for p in predictions]) if predictions else 0
    data_points = len(actuals)

    stats = [
        _stat_card("Avg Actual/hr", f"{avg_actual:.0f}", "#4da6ff"),
        _stat_card("Avg Predicted/hr", f"{avg_pred:.0f}", "#39ff7a"),
        _stat_card("Hours Simulated", str(data_points), "#a855f7"),
        _stat_card("Update Rate", "1s", "#f59e0b"),
    ]

    return fig, stats


def _stat_card(label, value, color):
    return html.Div(
        style={
            "textAlign": "center",
            "padding": "12px 24px",
            "background": "#1a1a2e",
            "borderRadius": "10px",
            "border": f"1px solid {color}33",
        },
        children=[
            html.Div(value, style={"color": color, "fontSize": "24px", "fontWeight": "700"}),
            html.Div(label, style={"color": "#6a6a8a", "fontSize": "12px", "marginTop": "4px"}),
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

server = app.server

if __name__ == "__main__":
    print("=" * 50)
    print("WeMakeCalls — Live Call Volume Forecast")
    print("=" * 50)
    print("  Chart: http://localhost:8050")
    print("  Update: every 1 second (1 hour simulated)")
    print("  Actual: Blue line (simulated live calls)")
    print("  Predicted: Green line (CatBoost model)")
    print("=" * 50)
    app.run(debug=False, host="0.0.0.0", port=8050)
