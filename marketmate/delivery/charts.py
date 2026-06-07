"""
marketmate.delivery.charts
──────────────────────────
Professional candlestick chart renderer for MarketMate signals.

Accepts a Signal object or a plain dict and a pandas OHLCV DataFrame.
Renders a dark-theme institutional chart with entry/SL/TP overlays.
Runs matplotlib in a dedicated 2-worker ThreadPoolExecutor so concurrent
renders never exceed 2 threads and the event loop is never blocked.

Returns the path to a PNG file, or None on any failure.
Never raises — all errors are caught and logged.

Migrated from services/chart_renderer.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import numpy as np
import pandas as pd

from marketmate.core.logger import get_logger

log = get_logger("chart_renderer")

# ─── Pre-import matplotlib at module load time ─────────────────────────────────
# This hides the ~500 ms first-import penalty from signal delivery latency.
# Must call matplotlib.use("Agg") before pyplot is imported anywhere.
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.ticker as mticker
    import matplotlib.dates as mdates
    import matplotlib.gridspec as gridspec
    import matplotlib.colors as mcolors

    # Warmup: create and immediately close a dummy figure so that on the
    # first real render, font/layout systems are already initialised.
    _warmup_fig = plt.figure()
    plt.close(_warmup_fig)

    _MPL_AVAILABLE = True
    log.info("chart_renderer_ready", backend=matplotlib.get_backend())
except ImportError as _mpl_err:
    _MPL_AVAILABLE = False
    log.warning("matplotlib_not_installed",
                error=str(_mpl_err),
                hint="pip install matplotlib pillow")

# ─── Dedicated render executor ────────────────────────────────────────────────
# max_workers=2 — concurrent signal bursts never spawn more than 2 threads,
# each holding ~50-100 MB of matplotlib state.
_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="chart_render")


# ─── Value extractor — handles both Signal dataclass and plain dict ───────────

def _v(obj, *keys, default=0.0):
    """Return the first non-None value found in obj by trying each key."""
    for k in keys:
        try:
            val = obj.get(k) if isinstance(obj, dict) else getattr(obj, k, None)
            if val is not None:
                return val
        except Exception:
            pass
    return default


# ─── Colour palette ───────────────────────────────────────────────────────────
# TradingView dark theme — exact hex values from TV's CSS.

C_BG     = "#131722"    # outermost background
C_PANEL  = "#1e222d"    # chart panel background
C_GRID   = "#2a2e39"    # grid lines
C_GRID_DAY = "#3a3f4b"  # date separator lines (slightly brighter)
C_TEXT   = "#787b86"    # axis labels and minor text
C_WHITE  = "#d1d4dc"    # primary text (title, important labels)
C_BULL   = "#26a69a"    # teal — bull candles (TradingView default)
C_BEAR   = "#ef5350"    # red  — bear candles
C_ENTRY  = "#ffd700"    # gold — entry level
C_SL     = "#ef5350"    # red  — stop loss
C_TP1    = "#26a69a"    # teal — TP1
C_TP2    = "#4caf50"    # green — TP2
C_TP3    = "#81c784"    # light green — TP3 (lower emphasis)


# ─── Synchronous render (called via executor) ─────────────────────────────────

def _render_sync(df: pd.DataFrame, signal, output_path: str,
                 timezone_str: str = "UTC") -> str:
    """
    Pure matplotlib candlestick chart renderer.
    Runs in a thread pool executor — must not use asyncio.

    Chart composition:
      - TradingView dark palette
      - Real datetime x-axis with date separator lines
      - Candlestick bodies + wicks with subtle edge borders
      - Dual y-axis (left + right price labels)
      - Volume sub-panel (when volume data is available)
      - Horizontal overlays: Entry (gold), SL (dashed red), TP1/TP2/TP3 (dotted green)
      - Label collision avoidance with dark bbox background
      - UTC timezone indicator in title
    """

    # ── Defensive prep ────────────────────────────────────────────────────────
    df = df.copy()

    # Normalise timestamp into a proper column
    if "timestamp" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={"index": "timestamp"})
        else:
            df["timestamp"] = pd.RangeIndex(len(df))

    # Use last 100 candles, ordered oldest → newest
    df = df.tail(100).reset_index(drop=True)
    n  = len(df)

    opens  = df["open"].astype(float).values
    highs  = df["high"].astype(float).values
    lows   = df["low"].astype(float).values
    closes = df["close"].astype(float).values

    has_volume = (
        "volume" in df.columns
        and df["volume"].notna().any()
        and float(df["volume"].max()) > 0
    )

    # ── X-axis: real datetime vs integer fallback ─────────────────────────────
    has_dates = False
    is_weekend_render = False   # Flag: all chart data falls on a weekend
    x = np.arange(n, dtype=float)        # fallback
    candle_width = 0.55                   # fallback (integer units)

    try:
        ts_series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        if ts_series.notna().all():
            # Strip timezone before date2num — matplotlib needs naive datetimes
            x_naive = ts_series.dt.tz_convert(None)

            # ── Weekend filter ─────────────────────────────────────────────
            weekend_mask = x_naive.dt.dayofweek < 5   # Mon=0 … Fri=4

            if weekend_mask.any():
                df       = df[weekend_mask.values]
                x_naive  = x_naive[weekend_mask]
            else:
                is_weekend_render = True
                log.info("chart_weekend_fallback",
                         hint="All data is weekend — rendering with unfiltered data")

            if df.empty:
                log.warning("chart_empty_after_filter")
                return output_path   # nothing left to draw

            # Recompute OHLC arrays after filter
            opens  = df["open"].astype(float).values
            highs  = df["high"].astype(float).values
            lows   = df["low"].astype(float).values
            closes = df["close"].astype(float).values
            n      = len(df)

            x = mdates.date2num(x_naive.to_numpy())

            # ── Dynamic candle width from median bar spacing ───────────────
            deltas = np.diff(x)
            median_delta = float(np.median(deltas)) if len(deltas) > 0 else (1 / 24 / 4)
            candle_width = median_delta * 0.6

            has_dates = True
    except Exception as exc:
        log.debug("chart_datetime_fallback", reason=str(exc))

    half_w = candle_width / 2

    # ── Extract signal values (with NaN sanitisation) ─────────────────────────
    def _safe_last_close() -> float:
        """Return the last non-NaN close, or 0 if none exists."""
        valid = closes[~np.isnan(closes)]
        return float(valid[-1]) if len(valid) > 0 else 0.0

    entry_raw = _v(signal, "entry_mid", "entry")
    entry     = float(entry_raw) if (entry_raw is not None and not (
                    isinstance(entry_raw, float) and np.isnan(entry_raw)
                )) else _safe_last_close()

    sl        = float(_v(signal, "stop_loss", "sl",  default=0.0))
    tp1       = float(_v(signal, "tp1",               default=0.0))
    tp2       = float(_v(signal, "tp2",               default=0.0))
    tp3_raw   = _v(signal, "tp3", default=None)
    tp3       = float(tp3_raw) if (tp3_raw is not None and tp3_raw != 0) else None
    direction = str(_v(signal, "direction",           default="BUY")).upper()
    symbol    = str(_v(signal, "symbol",              default="XAUUSD"))
    rr        = _v(signal, "rr",                      default=0.0)
    confidence = str(_v(signal, "confidence",         default="")).upper()

    # ── Figure & GridSpec ─────────────────────────────────────────────────────
    if has_volume:
        fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=C_BG)
        gs  = gridspec.GridSpec(
            2, 1,
            height_ratios=[4, 1],
            hspace=0.02,
            figure=fig,
        )
        ax     = fig.add_subplot(gs[0])
        ax_vol = fig.add_subplot(gs[1], sharex=ax)
    else:
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        fig.patch.set_facecolor(C_BG)
        ax_vol = None

    fig.patch.set_facecolor(C_BG)
    ax.set_facecolor(C_PANEL)

    # ── Draw candlestick bodies and wicks ─────────────────────────────────────
    visible_range = highs.max() - lows.min()
    min_body      = visible_range * 0.001

    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        bull        = c >= o
        color       = C_BULL if bull else C_BEAR
        body_lo     = min(o, c)
        body_hi     = max(o, c)
        body_height = max(body_hi - body_lo, min_body)

        xi = x[i]

        # Wick (high–low line)
        ax.plot([xi, xi], [l, h],
                color=color, linewidth=0.9, zorder=2, solid_capstyle="round")

        # Body rectangle — subtle edge border for professional look
        edge_col = "#c8e6c9" if bull else "#ffcdd2"
        body = mpatches.Rectangle(
            (xi - half_w, body_lo),
            candle_width, body_height,
            facecolor=color,
            edgecolor=edge_col,
            linewidth=0.4,
            zorder=3,
        )
        ax.add_patch(body)

    # ── Date separator lines (day boundaries) ─────────────────────────────────
    if has_dates:
        try:
            ts_arr = pd.to_datetime(df["timestamp"], utc=True)
            day_changes = ts_arr[ts_arr.dt.hour == 0]
            for dt in day_changes:
                xv = mdates.date2num(dt.to_pydatetime())
                ax.axvline(xv, color=C_GRID_DAY, linewidth=0.7,
                           linestyle="--", alpha=0.5, zorder=1)
        except Exception:
            pass

    # ── Overlay lines: Entry / SL / TP levels ─────────────────────────────────
    placed_labels: list[float] = []
    MIN_LABEL_GAP = visible_range * 0.02

    def _next_clear_y(price: float) -> float:
        final_y = price
        while True:
            if all(abs(final_y - py) >= MIN_LABEL_GAP for py in placed_labels):
                break
            final_y += MIN_LABEL_GAP * 1.2
        placed_labels.append(final_y)
        return final_y

    if has_dates and n > 0:
        label_x = x[-1] + candle_width * 2.5
    else:
        label_x = n + 0.5

    def _hline(
        price:  float,
        color:  str,
        style:  str,
        lw:     float,
        label:  str,
        alpha:  float = 0.92,
    ) -> None:
        """Draw a horizontal line at the exact price + a collision-free label."""
        if price <= 0 or np.isnan(price):
            return
        ax.axhline(price, color=color, linewidth=lw,
                   linestyle=style, zorder=5, alpha=alpha)
        label_y = _next_clear_y(price)
        ax.text(
            label_x, label_y,
            f" {label}  {price:,.2f}",
            color=color,
            fontsize=8.5,
            va="center",
            ha="left",
            fontfamily="monospace",
            zorder=6,
            clip_on=False,
            bbox=dict(
                facecolor=C_BG, edgecolor=color,
                alpha=0.88, pad=1.5,
                boxstyle="round,pad=0.2",
            ),
        )

    _hline(entry, C_ENTRY, "-",  1.6, "Entry")
    _hline(sl,    C_SL,    "--", 1.3, "SL   ")
    _hline(tp1,   C_TP1,   "--", 1.3, "TP1  ")
    _hline(tp2,   C_TP2,   ":",  1.1, "TP2  ", alpha=0.85)
    if tp3:
        _hline(tp3, C_TP3,  ":",  1.0, "TP3  ", alpha=0.70)

    # ── Dual y-axis (right side) ──────────────────────────────────────────────
    ax_right = ax.twinx()
    ax_right.set_ylim(ax.get_ylim())
    ax_right.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:,.2f}")
    )
    ax_right.tick_params(colors=C_TEXT, labelsize=8.5, length=3)
    ax_right.set_facecolor(C_PANEL)
    ax_right.grid(False)

    # ── X-axis formatting ─────────────────────────────────────────────────────
    if has_dates:
        span_days = x[-1] - x[0]
        if span_days <= 2:
            major_fmt = mdates.DateFormatter('%H:%M')
        else:
            major_fmt = mdates.DateFormatter('%m/%d\n%H:%M')

        ax.xaxis.set_major_formatter(major_fmt)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))
        if span_days <= 1:
            ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=15))
        elif span_days <= 7:
            ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=range(0, 24, 4)))
        for label in ax.get_xticklabels():
            label.set_rotation(0)
    else:
        tick_step = max(n // 10, 1)
        xticks    = list(range(0, n, tick_step))
        ts_col    = df["timestamp"]

        def _fmt_ts(idx: int) -> str:
            try:
                t = ts_col.iloc[idx]
                return t.strftime("%m/%d\n%H:%M") if hasattr(t, "strftime") else str(t)
            except Exception:
                return ""

        ax.set_xticks(xticks)
        ax.set_xticklabels([_fmt_ts(i) for i in xticks],
                           fontsize=7.5, color=C_TEXT, linespacing=1.2)

    ax.tick_params(axis="y", colors=C_TEXT, labelsize=8.5, length=4)
    ax.tick_params(axis="x", colors=C_TEXT, labelsize=7.5, length=4, pad=4)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:,.2f}")
    )

    # ── Grid ──────────────────────────────────────────────────────────────────
    ax.grid(
        True,
        color=C_GRID,
        linewidth=0.5,
        linestyle=(0, (0.5, 2.0)),
        alpha=0.6,
    )
    ax.set_axisbelow(True)

    # ── Spines ────────────────────────────────────────────────────────────────
    for spine in ax.spines.values():
        spine.set_edgecolor("#252a35")
        spine.set_linewidth(0.7)

    # ── Title ─────────────────────────────────────────────────────────────────
    dir_arrow = "▲" if direction == "BUY" else "▼"
    rr_str    = f"  ·  1:{rr:.2f}R" if rr else ""
    conf_str  = f"  ·  {confidence}" if confidence else ""
    tz_label  = timezone_str if timezone_str and timezone_str != "UTC" else "UTC"
    weekend_tag = "  ·  WEEKEND" if is_weekend_render else ""
    ax.set_title(
        f"{symbol}   {dir_arrow} {direction}{rr_str}{conf_str}{weekend_tag}   [{tz_label}]",
        color=C_WHITE, fontsize=13, fontweight="bold",
        loc="left", pad=10,
    )

    # ── Weekend watermark overlay ─────────────────────────────────────────────
    if is_weekend_render:
        ax.text(
            0.5, 0.5,
            "MARKET CLOSED",
            transform=ax.transAxes,
            fontsize=42, fontweight="bold",
            color="#ef5350", alpha=0.15,
            ha="center", va="center",
            rotation=25,
            zorder=0,
        )

    # ── Y limits ──────────────────────────────────────────────────────────────
    all_levels = [v for v in [entry, sl, tp1, tp2, tp3] if v and v > 0]
    y_min = min(lows.min(), min(all_levels) if all_levels else lows.min())
    y_max = max(highs.max(), max(all_levels) if all_levels else highs.max())
    pad   = max((y_max - y_min) * 0.07, 0.5)
    ax.set_ylim(y_min - pad, y_max + pad)
    ax_right.set_ylim(y_min - pad, y_max + pad)

    if has_dates and n > 0:
        ax.set_xlim(x[0] - candle_width, x[-1] + candle_width * 18)
    else:
        ax.set_xlim(-1, n + 12)

    # ── Volume sub-panel ──────────────────────────────────────────────────────
    if has_volume and ax_vol is not None:
        ax_vol.set_facecolor(C_PANEL)
        vol    = df["volume"].astype(float).values
        v_cols = [C_BULL if closes[i] >= opens[i] else C_BEAR for i in range(n)]
        ax_vol.bar(x, vol, width=candle_width,
                   color=v_cols, edgecolor="none", linewidth=0, alpha=0.7)
        ax_vol.set_ylabel("Vol", color=C_TEXT, fontsize=8)
        ax_vol.tick_params(colors=C_TEXT, labelsize=7, length=3)
        ax_vol.yaxis.set_major_locator(mticker.MaxNLocator(3))
        ax_vol.yaxis.set_major_formatter(
            mticker.FuncFormatter(lambda v, _: f"{v/1e3:.0f}K" if v >= 1e3 else f"{v:.0f}")
        )
        ax_vol.grid(True, color=C_GRID, linewidth=0.4, alpha=0.5)
        for spine in ax_vol.spines.values():
            spine.set_edgecolor("#252a35")
        plt.setp(ax.get_xticklabels(), visible=False)

    # ── Logo watermark ────────────────────────────────────────────────────────
    _LOGO_PATH = (
        __import__("pathlib").Path(__file__).parent.parent / "assets" / "logo.png"
    )
    if not _LOGO_PATH.exists():
        log.warning("chart_watermark_skipped",
                    reason="logo_not_found", path=str(_LOGO_PATH))
    else:
        try:
            from matplotlib.offsetbox import OffsetImage, AnnotationBbox

            LOGO_H = 80

            try:
                from PIL import Image as _PILImage
                _img  = _PILImage.open(str(_LOGO_PATH)).convert("RGBA")
                LOGO_W = int(LOGO_H * (_img.width / _img.height))
                _img  = _img.resize((LOGO_W, LOGO_H), _PILImage.LANCZOS)
                logo_arr = __import__("numpy").array(_img) / 255.0
            except ImportError:
                import matplotlib.image as _mpimg
                import numpy as _np2
                _raw   = _mpimg.imread(str(_LOGO_PATH))
                _scale = LOGO_H / _raw.shape[0]
                LOGO_W = int(_raw.shape[1] * _scale)
                _iy    = (_np2.arange(LOGO_H) / _scale).astype(int).clip(0, _raw.shape[0] - 1)
                _ix    = (_np2.arange(LOGO_W) / _scale).astype(int).clip(0, _raw.shape[1] - 1)
                logo_arr = _raw[_np2.ix_(_iy, _ix)]

            imagebox = OffsetImage(logo_arr, zoom=1.0, alpha=0.45)
            ab = AnnotationBbox(
                imagebox,
                (0.993, 0.018),
                xycoords="axes fraction",
                frameon=False,
                box_alignment=(1, 0),
                zorder=10,
            )
            ax.add_artist(ab)
            log.debug("chart_watermark_placed",
                      size=f"{LOGO_W}x{LOGO_H}px", alpha=0.45)

        except Exception as _wm_exc:
            log.warning("chart_watermark_failed", error=str(_wm_exc))

    # ── Save ──────────────────────────────────────────────────────────────────
    plt.tight_layout(pad=1.2)

    save_kwargs: dict = dict(
        dpi=100,
        bbox_inches="tight",
        facecolor=C_BG,
        format="png",
    )
    try:
        import PIL  # noqa: F401
        save_kwargs["pil_kwargs"] = {"optimize": True, "compress_level": 9}
    except ImportError:
        pass

    plt.savefig(output_path, **save_kwargs)
    plt.close(fig)
    return output_path


# ─── Public async entry point ─────────────────────────────────────────────────

async def render_signal_chart(
    signal,
    df: pd.DataFrame,
    output_path: Optional[str] = None,
    timezone_str: str = "UTC",
) -> Optional[str]:
    """
    Render a candlestick chart for a signal and return the PNG file path.

    Args:
        signal:      Signal dataclass instance OR plain dict.
        df:          OHLCV DataFrame. Needs open/high/low/close columns.
        output_path: Optional output path. A temp file is created if None.

    Returns:
        Absolute path to the generated PNG, or None if rendering failed.

    Never raises.
    """
    if not _MPL_AVAILABLE:
        log.warning("chart_skipped", reason="matplotlib_not_installed")
        return None

    if df is None or df.empty:
        log.warning("chart_skipped", reason="empty_dataframe")
        return None

    if len(df) < 10:
        log.warning("chart_skipped", reason="insufficient_candles", count=len(df))
        return None

    if output_path is None:
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", prefix="mm_chart_", delete=False
            )
            tmp.close()
            output_path = tmp.name
        except Exception as exc:
            log.error("chart_tempfile_failed", error=str(exc))
            return None

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _EXECUTOR, _render_sync, df, signal, output_path, timezone_str
        )
    except Exception as exc:
        log.error("chart_render_error", error=str(exc), exc_info=True)
        _cleanup(output_path)
        return None

    if not os.path.exists(output_path):
        log.warning("chart_render_failed", reason="output_file_missing")
        return None

    size = os.path.getsize(output_path)
    if size < 2048:
        log.warning("chart_render_failed", reason="output_too_small", bytes=size)
        _cleanup(output_path)
        return None

    log.info("chart_rendered",
             path=output_path,
             size_kb=round(size / 1024, 1),
             has_volume="volume" in df.columns)
    return output_path


# ─── Educational Chart Renderer (MMAcademy) ──────────────────────────────────

async def render_education_chart(
    df: pd.DataFrame,
    annotations: list,
    title: str = "XAUUSD",
    output_path: Optional[str] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
) -> Optional[str]:
    """
    Render an educational candlestick chart with SMC concept annotations.

    Unlike render_signal_chart(), this:
      - Has NO TP/SL/Entry lines
      - Has NO watermarks/logos on the chart
      - Supports SMC concept annotations
      - Uses MMAcademy palette
      - Saves to public/charts/ if no output_path given
    """
    if not _MPL_AVAILABLE:
        log.warning("edu_chart_skipped", reason="matplotlib_not_installed")
        return None

    if df is None or df.empty or len(df) < 5:
        log.warning("edu_chart_skipped", reason="insufficient_data",
                    count=len(df) if df is not None else 0)
        return None

    if output_path is None:
        charts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "public", "charts"
        )
        os.makedirs(charts_dir, exist_ok=True)
        try:
            tmp = tempfile.NamedTemporaryFile(
                suffix=".png", prefix="edu_", delete=False, dir=charts_dir
            )
            tmp.close()
            output_path = tmp.name
        except Exception as exc:
            log.error("edu_chart_tempfile_failed", error=str(exc))
            return None

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            _EXECUTOR, _render_education_sync, df, annotations, title, output_path,
            date_start, date_end,
        )
    except Exception as exc:
        log.error("edu_chart_render_error", error=str(exc), exc_info=True)
        _cleanup(output_path)
        return None

    if not os.path.exists(output_path) or os.path.getsize(output_path) < 2048:
        log.warning("edu_chart_render_failed", path=output_path)
        _cleanup(output_path)
        return None

    size = os.path.getsize(output_path)
    log.info("edu_chart_rendered", path=output_path, size_kb=round(size / 1024, 1))
    return output_path


def _render_education_sync(
    df: pd.DataFrame,
    annotations: list,
    title: str,
    output_path: str,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
) -> str:
    """Synchronous educational chart render — runs in thread pool.

    Pipeline:
      1. Normalise timestamp column
      2. Filter candles by requested date range
      3. Tail to max 80 candles
      4. Build visible DataFrame
      5. Map annotation timestamps to nearest candle indices
      6. Validate annotation prices against visible range
      7. Render with x/y clamping and vertical stagger
    """
    df = df.copy()
    _df_original = df.copy()

    if "timestamp" not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={"index": "timestamp"})
        else:
            df["timestamp"] = pd.RangeIndex(len(df))

    # ── Filter by requested date range ────────────────────────────────────
    if date_start or date_end:
        ts_col = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        mask = pd.Series(True, index=df.index)
        if date_start:
            start_dt = pd.to_datetime(date_start, utc=True, errors="coerce")
            if start_dt is not pd.NaT:
                mask = mask & (ts_col >= start_dt)
        if date_end:
            end_dt = pd.to_datetime(date_end, utc=True, errors="coerce")
            if end_dt is not pd.NaT:
                end_dt = end_dt + pd.Timedelta(days=1) - pd.Timedelta(microseconds=1)
                mask = mask & (ts_col <= end_dt)
        df = df[mask.values].reset_index(drop=True)
        log.info("edu_chart_date_filter",
                 date_start=date_start, date_end=date_end,
                 rows_after=len(df))

    if df.empty:
        df = _df_original.copy()
        if df.empty:
            return None
        if "timestamp" not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index().rename(columns={"index": "timestamp"})
            else:
                df["timestamp"] = pd.RangeIndex(len(df))

    df = df.tail(80).reset_index(drop=True)
    n = len(df)

    opens  = df["open"].astype(float).values
    highs  = df["high"].astype(float).values
    lows   = df["low"].astype(float).values
    closes = df["close"].astype(float).values

    # X-axis
    has_dates = False
    x = np.arange(n, dtype=float)
    candle_width = 0.55

    try:
        ts_series = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        if ts_series.notna().all():
            x_naive = ts_series.dt.tz_convert(None)
            weekend_mask = x_naive.dt.dayofweek < 5
            if weekend_mask.any():
                df = df[weekend_mask.values]
                x_naive = x_naive[weekend_mask]
            if not df.empty:
                opens  = df["open"].astype(float).values
                highs  = df["high"].astype(float).values
                lows   = df["low"].astype(float).values
                closes = df["close"].astype(float).values
                n = len(df)
                x = mdates.date2num(x_naive.to_numpy())
                deltas = np.diff(x)
                median_delta = float(np.median(deltas)) if len(deltas) > 0 else (1 / 24 / 4)
                candle_width = median_delta * 0.6
                has_dates = True
    except Exception:
        pass

    half_w = candle_width / 2

    # MMAcademy palette
    EDU_BG    = "#0A0B0C"
    EDU_PANEL = "#0E1014"
    EDU_GRID  = "#1A1C1F"
    EDU_TEXT  = "#8892A4"
    EDU_WHITE = "#E8EAF0"
    EDU_BULL  = "#10B981"
    EDU_BEAR  = "#EF4444"
    EDU_GOLD  = "#D4AF37"

    # Category color map
    CATEGORY_COLORS = {
        "bullish":   "#10B981",
        "bearish":   "#EF4444",
        "structure": "#EAB308",
        "liquidity": "#A855F7",
        "wick":      "#06B6D4",
        "pattern":   "#F97316",
        "default":   "#D4AF37",
    }

    TYPE_CATEGORY = {
        "bos":             "structure",
        "choch":           "structure",
        "mss":             "structure",
        "order_block":     "structure",
        "ob":              "structure",
        "fvg":             "structure",
        "liquidity_sweep": "liquidity",
        "bullish":         "bullish",
        "bearish":         "bearish",
        "wick":            "wick",
        "pattern":         "pattern",
        "concept":         "liquidity",
        "candle":          "bullish",
        "body":            "bullish",
        "label":           "default",
        "arrow":           "default",
        "box":             "default",
        "line":            "default",
        "range":           "default",
    }

    def _get_ann_color(ann):
        raw = None
        explicit = ann.get("color")
        if explicit:
            raw = explicit
        if not raw:
            style = ann.get("style", {})
            raw = style.get("color") or style.get("borderColor")
        if not raw:
            ann_type = ann.get("type", "").lower()
            category = ann.get("category", "") or TYPE_CATEGORY.get(ann_type, "")
            raw = CATEGORY_COLORS.get(category, CATEGORY_COLORS["default"])
        if raw and isinstance(raw, str) and raw.startswith("rgba"):
            try:
                parts = raw.strip("rgba()").split(",")
                r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
                raw = f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                raw = EDU_GOLD
        return raw or EDU_GOLD

    # ── Figure ────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
    fig.patch.set_facecolor(EDU_BG)
    ax.set_facecolor(EDU_PANEL)

    visible_range = highs.max() - lows.min()
    min_body = visible_range * 0.001

    for i in range(n):
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        bull = c >= o
        color = EDU_BULL if bull else EDU_BEAR
        body_lo = min(o, c)
        body_hi = max(o, c)
        body_height = max(body_hi - body_lo, min_body)
        xi = x[i]

        ax.plot([xi, xi], [l, h],
                color=color, linewidth=0.9, zorder=2, solid_capstyle="round")
        edge_col = "#a7f3d0" if bull else "#fecaca"
        body = mpatches.Rectangle(
            (xi - half_w, body_lo),
            candle_width, body_height,
            facecolor=color, edgecolor=edge_col,
            linewidth=0.4, zorder=3,
        )
        ax.add_patch(body)

    # ── Render annotations ────────────────────────────────────────────────
    for ann in annotations:
        ann_type = ann.get("type", "").lower()
        ann_color = _get_ann_color(ann)
        label = ann.get("label", ann_type.replace("_", " ").title())

        try:
            # Zone-type annotations (order_block, fvg, ob)
            if ann_type in ("order_block", "ob", "fvg", "box", "range"):
                price_low = ann.get("price_low", 0)
                price_high = ann.get("price_high", 0)
                if price_low and price_high:
                    ax.axhspan(price_low, price_high,
                               alpha=0.15, color=ann_color, zorder=1)
                    ax.text(x[-1] + candle_width, price_high,
                            f" {label}", color=ann_color,
                            fontsize=7.5, va="bottom", ha="left",
                            fontfamily="monospace", zorder=6,
                            clip_on=False,
                            bbox=dict(facecolor=EDU_BG, edgecolor=ann_color,
                                      alpha=0.85, pad=1.5,
                                      boxstyle="round,pad=0.2"))

            # Horizontal line annotations (bos, choch, mss, liquidity_sweep)
            elif ann_type in ("bos", "choch", "mss", "liquidity_sweep", "line"):
                price = ann.get("price", 0)
                if price:
                    ax.axhline(price, color=ann_color, linewidth=1.2,
                               linestyle="--", alpha=0.85, zorder=4)
                    ax.text(x[-1] + candle_width, price,
                            f" {label}", color=ann_color,
                            fontsize=7.5, va="center", ha="left",
                            fontfamily="monospace", zorder=6,
                            clip_on=False,
                            bbox=dict(facecolor=EDU_BG, edgecolor=ann_color,
                                      alpha=0.85, pad=1.5,
                                      boxstyle="round,pad=0.2"))

            # Simple label annotations
            elif ann_type in ("label", "arrow", "candle", "body", "wick",
                              "pattern", "concept", "bullish", "bearish"):
                price = ann.get("price", (highs.max() + lows.min()) / 2)
                if price:
                    ax.text(x[-1] + candle_width, price,
                            f" {label}", color=ann_color,
                            fontsize=7.5, va="center", ha="left",
                            fontfamily="monospace", zorder=6,
                            clip_on=False,
                            bbox=dict(facecolor=EDU_BG, edgecolor=ann_color,
                                      alpha=0.85, pad=1.5,
                                      boxstyle="round,pad=0.2"))
        except Exception as exc:
            log.warning("edu_chart_annotation_failed",
                        type=ann_type, error=str(exc))

    # ── Axis formatting ───────────────────────────────────────────────────
    if has_dates:
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d\n%H:%M'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=6, maxticks=12))
        for label in ax.get_xticklabels():
            label.set_rotation(0)

    ax.tick_params(axis="y", colors=EDU_TEXT, labelsize=8.5, length=4)
    ax.tick_params(axis="x", colors=EDU_TEXT, labelsize=7.5, length=4, pad=4)
    ax.yaxis.set_major_formatter(
        mticker.FuncFormatter(lambda v, _: f"{v:,.2f}")
    )
    ax.grid(True, color=EDU_GRID, linewidth=0.5,
            linestyle=(0, (0.5, 2.0)), alpha=0.6)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1c1f")
        spine.set_linewidth(0.7)

    ax.set_title(title, color=EDU_WHITE, fontsize=13, fontweight="bold",
                 loc="left", pad=10)

    # Y limits
    y_min = lows.min()
    y_max = highs.max()
    pad = max((y_max - y_min) * 0.07, 0.5)
    ax.set_ylim(y_min - pad, y_max + pad)

    if has_dates and n > 0:
        ax.set_xlim(x[0] - candle_width, x[-1] + candle_width * 18)
    else:
        ax.set_xlim(-1, n + 12)

    plt.tight_layout(pad=1.2)
    save_kwargs: dict = dict(dpi=100, bbox_inches="tight", facecolor=EDU_BG, format="png")
    try:
        import PIL  # noqa: F401
        save_kwargs["pil_kwargs"] = {"optimize": True, "compress_level": 9}
    except ImportError:
        pass

    plt.savefig(output_path, **save_kwargs)
    plt.close(fig)
    return output_path


# ─── Cleanup helper ───────────────────────────────────────────────────────────

def _cleanup(path: str) -> None:
    """Remove a temp file, ignoring errors."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass
