"""Streamlit scanner: sweep any ticker universe and surface high-confidence picks."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from little_warren.application.analysis_service.service import AnalysisService
from little_warren.application.scan_service import ScanResult, ScanService
from little_warren.domain.entities import Pick
from little_warren.infrastructure.data import YFinanceProvider
from little_warren.infrastructure.data.universes import PRESETS

INK = "#444444"
STOP_COLOR = "#c0392b"
TARGET_COLOR = "#1e8449"
UP_COLOR = "#7fb3a4"
DOWN_COLOR = "#c98a8a"

st.set_page_config(page_title="little-warren scanner", page_icon=None, layout="wide")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_frame(ticker: str, lookback_days: int) -> pd.DataFrame:
    end = date.today()
    return YFinanceProvider().fetch_ohlcv(ticker, start=end - timedelta(days=lookback_days), end=end)


def run_scan(tickers: list[str], lookback_days: int, reversal: float, stochastic_gate: bool) -> ScanResult:
    analysis = AnalysisService(provider=YFinanceProvider(), reversal=reversal, stochastic_gate=stochastic_gate)
    scanner = ScanService(analysis)
    progress = st.progress(0.0, text="Scanning...")

    def on_progress(done: int, total: int) -> None:
        progress.progress(done / total, text=f"Scanning {done}/{total}")

    result = scanner.scan(tickers, as_of=date.today(), lookback_days=lookback_days, on_progress=on_progress)
    progress.empty()
    return result


def picks_table(picks: list[Pick]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "ticker": p.ticker,
                "direction": p.direction.value,
                "confidence": p.confidence,
                "entry": round(p.entry, 2),
                "stop": round(p.stop, 2),
                "target": None if p.target is None else round(p.target, 2),
                "reward/risk": None if p.target is None else round(abs(p.entry - p.target) / p.risk_per_unit, 2),
                "stochastics": p.evidence.get("stoch_filter"),
                "rules": ", ".join(p.rules_fired),
            }
            for p in picks
        ]
    )


def pick_chart(pick: Pick, lookback_days: int) -> go.Figure:
    frame = fetch_frame(pick.ticker, lookback_days).tail(180)
    figure = go.Figure(
        go.Candlestick(
            x=frame.index,
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            increasing_line_color=UP_COLOR,
            decreasing_line_color=DOWN_COLOR,
            name=pick.ticker,
            showlegend=False,
        )
    )
    for level, label, color in (
        (pick.entry, f"entry {pick.entry:.2f}", INK),
        (pick.stop, f"stop {pick.stop:.2f}", STOP_COLOR),
        (pick.target, f"target {pick.target:.2f}" if pick.target else "", TARGET_COLOR),
    ):
        if level is not None:
            figure.add_hline(
                y=level,
                line_color=color,
                line_width=1,
                line_dash="dot",
                annotation_text=label,
                annotation_font_color=color,
                annotation_position="right",
            )
    figure.update_layout(
        xaxis_rangeslider_visible=False,
        margin={"l": 40, "r": 90, "t": 20, "b": 30},
        height=420,
        xaxis={"gridcolor": "rgba(128,128,128,0.15)"},
        yaxis={"gridcolor": "rgba(128,128,128,0.15)", "side": "left"},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return figure


def main() -> None:
    st.title("little-warren scanner")
    st.caption("Rules-based picks with stop, target and a calibrated confidence score. Not financial advice.")

    with st.sidebar:
        st.header("Universe")
        chosen_presets = st.multiselect("Presets", list(PRESETS), default=["US large caps"])
        custom = st.text_area("Any other tickers", placeholder="TSLA, BTC-USD, GOLD ... anything Yahoo knows")
        st.header("Filters")
        min_confidence = st.slider("Minimum confidence", 0.0, 0.95, 0.70, step=0.05)
        with st.expander("Advanced"):
            lookback_days = st.number_input("Lookback (days)", 200, 3650, 730, step=50)
            reversal = st.number_input("Swing threshold", 0.02, 0.10, 0.04, step=0.01, format="%.2f")
            stochastic_gate = st.checkbox("Hard stochastic gate (ENT-COR-03)", value=False)
        scan_clicked = st.button("Scan", type="primary", use_container_width=True)

    tickers = [t for preset in chosen_presets for t in PRESETS[preset]]
    tickers += custom.replace(",", " ").split()

    if scan_clicked:
        if not tickers:
            st.warning("Pick at least one preset or type some tickers.")
            return
        st.session_state["scan"] = run_scan(tickers, int(lookback_days), float(reversal), stochastic_gate)

    result: ScanResult | None = st.session_state.get("scan")
    if result is None:
        st.info("Choose a universe on the left and hit Scan.")
        return

    high = result.picks_above(min_confidence)
    scanned, signals, failed = result.scanned, len(result.picks), len(result.failed)
    for column, (label, value) in zip(
        st.columns(4),
        (
            ("Tickers scanned", scanned),
            ("Signals found", signals),
            (f"Confidence >= {min_confidence:.0%}", len(high)),
            ("Fetch failures", failed),
        ),
        strict=True,
    ):
        column.metric(label, value)

    if failed:
        st.caption(f"No data for: {', '.join(result.failed)}")
    if not high:
        st.info(
            "No picks above the confidence bar right now. That is expected most days: "
            "the system stays silent unless every condition holds (FND-25)."
        )
        return

    st.dataframe(
        picks_table(high),
        use_container_width=True,
        hide_index=True,
        column_config={
            "confidence": st.column_config.ProgressColumn("confidence", format="percent", min_value=0, max_value=1)
        },
    )

    st.subheader("Pick detail")
    label_by_pick = {f"{p.ticker} {p.direction.value} ({p.confidence:.0%})": p for p in high}
    selected = st.selectbox("Inspect", list(label_by_pick))
    pick = label_by_pick[selected]
    st.plotly_chart(pick_chart(pick, int(lookback_days)), use_container_width=True)
    left, right = st.columns(2)
    left.markdown(f"**Rules fired:** {', '.join(pick.rules_fired)}")
    left.markdown(f"**Notes:** {pick.notes}")
    right.markdown("**Evidence**")
    right.json(pick.evidence, expanded=False)


main()
