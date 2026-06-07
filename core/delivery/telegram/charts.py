"""
signal_engine.delivery.charts
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

from signal_engine.core.logger import get_logger

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

    # ── Sanitise: drop rows with NaN/Inf in OHLC columns ──────────────────────
    # This is the #1 cause of blank charts — providers and cache can return
    # rows with NaN or Inf in price columns, which crashes matplotlib's axis
    # limit computation with "Axis limits cannot be NaN or Inf".
    ohlc_cols = ["open", "high", "low", "close"]
    for col in ohlc_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # Replace Inf with NaN, then drop NaN rows
    df = df.replace([np.inf, -np.inf], np.nan)
    pre_len = len(df)
    df = df.dropna(subset=ohlc_cols).reset_index(drop=True)
    if len(df) < pre_len:
        log.warning("chart_dropped_nan_rows",
                    dropped=pre_len - len(df), remaining=len(df))
    if df.empty:
        log.warning("chart_empty_after_sanitise")
        # Still save the file so we don't return None for a temp file path
        fig, ax = plt.subplots(figsize=(16, 9), dpi=100)
        fig.patch.set_facecolor(C_BG)
        ax.set_facecolor(C_PANEL)
        ax.text(0.5, 0.5, "No valid price data",
                transform=ax.transAxes, fontsize=24,
                color=C_TEXT, ha="center", va="center")
        plt.savefig(output_path, dpi=100, facecolor=C_BG, format="png")
        plt.close(fig)
        return output_path

    # Use last 100 candles, ordered oldest → newest
    df = df.tail(100).reset_index(drop=True)
    n  = len(df)

    opens  = df["open"].astype(float).values
    highs  = df["high"].astype(float).values
    lows   = df["low"].astype(float).values
    closes = df["close"].astype(float).values

    # Sanitise volume: replace NaN/Inf/negative with 0
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0)
        df["volume"] = df["volume"].replace([np.inf, -np.inf], 0).clip(lower=0)

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

            # Backups in case weekend filter removes all data
            df_tail_backup = df.copy()
            x_naive_backup = x_naive.copy()

            # ── Weekend filter ─────────────────────────────────────────────
            weekend_mask = x_naive.dt.dayofweek < 5   # Mon=0 … Fri=4

            if weekend_mask.any():
                # Some weekday data — filter out weekends
                df       = df[weekend_mask.values]
                x_naive  = x_naive[weekend_mask]
            else:
                # ALL data is on a weekend — skip the filter and render anyway
                # (crypto trades 24/7, and gold data often includes weekend gaps)
                is_weekend_render = True
                log.info("chart_weekend_fallback",
                         hint="All data is weekend — rendering with unfiltered data")

            if df.empty:
                log.warning("chart_empty_after_weekend_filter")
                # Don't return a blank file — skip the filter and use all data
                df = df_tail_backup.copy()
                x_naive = x_naive_backup.copy()
                is_weekend_render = True

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

    # ── Logo watermark skipped (removed in refactored version)
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


# ─── Education chart renderer removed (not needed in refactored version)

# ─── Cleanup helper ───────────────────────────────────────────────────────────

def _cleanup(path: str) -> None:
    """Remove a temp file, ignoring errors."""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass
