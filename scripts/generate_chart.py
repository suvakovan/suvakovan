"""
LeetCode Candlestick Chart Generator
Fetches weekly submission data from LeetCode GraphQL API and plots
an OHLC candlestick chart saved as assets/leetcode_candlestick.png
"""

import json
import os
import datetime
import requests
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D

# ── Config ──────────────────────────────────────────────────────────
LEETCODE_USER = "suvakovan"
OUTPUT_PATH   = os.path.join(os.path.dirname(__file__), "..", "assets", "leetcode_candlestick.png")
WEEKS_TO_SHOW = 16   # how many recent weeks to display

# ── Colours (terminal theme) ─────────────────────────────────────────
BG_COLOR    = "#0d1117"
PANEL_COLOR = "#161b22"
GREEN       = "#00ff41"
RED         = "#ff4444"
TEXT_COLOR  = "#c9d1d9"
GRID_COLOR  = "#21262d"

# ── Fetch submission calendar & rank from LeetCode GraphQL ─────────────
GRAPHQL_URL = "https://leetcode.com/graphql"
QUERY = """
query userProfileCalendar($username: String!, $year: Int) {
  matchedUser(username: $username) {
    profile {
      ranking
      userAvatar
    }
    submissionCalendar
  }
}
"""

def fetch_leetcode_data(username: str) -> dict:
    try:
        resp = requests.post(
            GRAPHQL_URL,
            json={"query": QUERY, "variables": {"username": username}},
            headers={"Content-Type": "application/json", "Referer": "https://leetcode.com"},
            timeout=15,
        )
        data = resp.json()
        return data["data"]["matchedUser"]
    except Exception as e:
        print(f"[WARN] Could not fetch live data: {e}")
        return {}

# ── Build daily Series ───────────────────────────────────────────────
def build_daily_series(calendar: dict) -> pd.Series:
    if not calendar:
        return pd.Series(dtype=float)
    records = {
        datetime.date.fromtimestamp(int(ts)): int(cnt)
        for ts, cnt in calendar.items()
    }
    idx = pd.date_range(min(records), max(records), freq="D")
    s = pd.Series(0, index=idx, dtype=float)
    for d, c in records.items():
        s[pd.Timestamp(d)] = c
    return s

# ── Aggregate to weekly OHLC ─────────────────────────────────────────
def weekly_ohlc(daily: pd.Series) -> pd.DataFrame:
    # Resample to weekly frequency (Monday-start)
    weekly = daily.resample("W-MON", label="left", closed="left")
    df = pd.DataFrame({
        "open":   weekly.first(),
        "high":   weekly.max(),
        "low":    weekly.min(),
        "close":  weekly.last(),
        "volume": weekly.sum(),
    }).dropna()
    # Keep only weeks with at least one submission
    df = df[df["volume"] > 0]
    return df.tail(WEEKS_TO_SHOW)

# ── Draw chart ───────────────────────────────────────────────────────
def draw_candlestick(df: pd.DataFrame, output_path: str):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    fig, (ax_candle, ax_vol) = plt.subplots(
        2, 1, figsize=(14, 7),
        gridspec_kw={"height_ratios": [3, 1]},
        facecolor=BG_COLOR,
    )

    for ax in (ax_candle, ax_vol):
        ax.set_facecolor(PANEL_COLOR)
        ax.tick_params(colors=TEXT_COLOR, labelsize=8)
        ax.yaxis.label.set_color(TEXT_COLOR)
        ax.xaxis.label.set_color(TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID_COLOR)
        ax.grid(color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.7)

    x_positions = range(len(df))
    x_labels    = [d.strftime("%b %d") for d in df.index]

    bull_patches, bear_patches = [], []

    for i, (idx, row) in enumerate(df.iterrows()):
        o, h, l, c = row["open"], row["high"], row["low"], row["close"]
        color  = GREEN if c >= o else RED
        body_h = abs(c - o) if abs(c - o) > 0.05 else 0.1
        body_b = min(o, c)

        # Body
        rect = mpatches.FancyBboxPatch(
            (i - 0.3, body_b), 0.6, body_h,
            boxstyle="square,pad=0",
            linewidth=0.8, edgecolor=color, facecolor=color + "88",
        )
        ax_candle.add_patch(rect)

        # Wicks
        ax_candle.plot([i, i], [l, body_b],         color=color, linewidth=1.2)
        ax_candle.plot([i, i], [body_b + body_h, h], color=color, linewidth=1.2)

        if c >= o:
            bull_patches.append(rect)
        else:
            bear_patches.append(rect)

        # Volume bars
        vol_color = color + "bb"
        ax_vol.bar(i, row["volume"], color=vol_color, width=0.6, linewidth=0)

    # Axes formatting
    ax_candle.set_xlim(-0.8, len(df) - 0.2)
    ymin = df["low"].min()
    ymax = df["high"].max()
    pad  = max((ymax - ymin) * 0.15, 1)
    ax_candle.set_ylim(ymin - pad, ymax + pad)
    ax_candle.set_xticks([])

    ax_vol.set_xlim(-0.8, len(df) - 0.2)
    ax_vol.set_xticks(list(x_positions))
    ax_vol.set_xticklabels(x_labels, rotation=45, ha="right", fontsize=7)
    ax_vol.set_ylabel("Submissions", fontsize=8, color=TEXT_COLOR)

    # Title
    ax_candle.set_title(
        f"  LeetCode Weekly OHLC  ·  @{LEETCODE_USER}  ·  Last {len(df)} Weeks",
        fontsize=12, color=GREEN, fontfamily="monospace",
        loc="left", pad=10,
    )
    ax_candle.set_ylabel("Problems Solved / Day", fontsize=8, color=TEXT_COLOR)

    # Legend
    legend_elements = [
        Line2D([0], [0], color=GREEN, linewidth=2, label="Bullish (more solves → close ≥ open)"),
        Line2D([0], [0], color=RED,   linewidth=2, label="Bearish (fewer solves → close < open)"),
    ]
    ax_candle.legend(
        handles=legend_elements, loc="upper left",
        facecolor=PANEL_COLOR, edgecolor=GRID_COLOR,
        labelcolor=TEXT_COLOR, fontsize=8,
    )

    # Watermark
    fig.text(
        0.99, 0.01, "generated by github-action · suvakovan/suvakovan",
        ha="right", va="bottom", fontsize=6, color="#444d56", fontstyle="italic",
    )

    plt.tight_layout(pad=1.5)
    fig.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=BG_COLOR, edgecolor="none")
    plt.close(fig)
    print(f"[OK] Chart saved → {output_path}")


# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[INFO] Fetching LeetCode data for '{LEETCODE_USER}' …")
    user_data = fetch_leetcode_data(LEETCODE_USER)
    
    # Save rank data to JSON for dynamic badge
    stats_path = os.path.join(os.path.dirname(OUTPUT_PATH), "leetcode_stats.json")
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    if user_data and "profile" in user_data:
        rank = user_data["profile"]["ranking"]
        # Format rank with commas (e.g. 1,691,179)
        formatted_rank = f"{rank:,}"
        with open(stats_path, "w") as f:
            json.dump({"rank": formatted_rank}, f)
        print(f"[OK] Rank saved → {stats_path}")

    if not user_data or "submissionCalendar" not in user_data:
        print("[WARN] No submission data returned — generating placeholder chart.")
        # Fallback: generate a placeholder with zeros so the README image doesn't break
        dates = pd.date_range(end=datetime.date.today(), periods=WEEKS_TO_SHOW, freq="W-MON")
        daily = pd.Series(0, index=dates, dtype=float)
    else:
        calendar = json.loads(user_data["submissionCalendar"])
        daily = build_daily_series(calendar)

    df = weekly_ohlc(daily)

    if df.empty:
        print("[WARN] No weekly data to plot — skipping chart generation.")
    else:
        draw_candlestick(df, OUTPUT_PATH)
