import requests
import json
import os
import datetime
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

matplotlib.use('Agg') # Headless backend

LEETCODE_USER = "suvakovan"
OUTPUT_PATH = "assets/leetcode_candlestick.png"
WEEKS_TO_SHOW = 24  # About 6 months of data

# Theme: Dark, classic trading platform
BG_COLOR    = "#0d1117"
TEXT_COLOR  = "#c9d1d9"
GRID_COLOR  = "#21262d"
UP_COLOR    = "#00ff41"  # Green for growth
DOWN_COLOR  = "#ff0000"  # Red for decline
MA_COLOR    = "#ffa500"  # Orange for moving average

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
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("matchedUser", {})
    except Exception as e:
        print(f"[WARN] Could not fetch live data: {e}")
        return {}

def build_daily_series(calendar_data: dict) -> pd.Series:
    """Convert {'timestamp': count} to a daily pandas Series."""
    dates_counts = {}
    for ts_str, count in calendar_data.items():
        ts = int(ts_str)
        dt = datetime.datetime.fromtimestamp(ts).date()
        dates_counts[dt] = dates_counts.get(dt, 0) + count
    
    if not dates_counts:
        return pd.Series(dtype=float)

    s = pd.Series(dates_counts)
    s.index = pd.to_datetime(s.index)
    
    # Fill missing days with 0
    full_range = pd.date_range(start=s.index.min(), end=datetime.date.today(), freq='D')
    s = s.reindex(full_range, fill_value=0)
    return s

def weekly_ohlc(daily_series: pd.Series) -> pd.DataFrame:
    """Group by week and compute OHLC + Volume properly mapped to daily."""
    df = daily_series.to_frame(name='Volume')
    # Resample weekly starting Monday
    weekly = df.resample('W-MON')
    
    ohlc = pd.DataFrame({
        'Open': weekly['Volume'].first(),
        'High': weekly['Volume'].max(),
        'Low': weekly['Volume'].min(),
        'Close': weekly['Volume'].last(),
        'Volume': weekly['Volume'].sum()
    })
    
    # In weeks where volume entirely was 0, it should be 0 across the board
    ohlc.fillna(0, inplace=True)
    return ohlc.tail(WEEKS_TO_SHOW)

def plot_dark_candlestick(df: pd.DataFrame, out_path: str):
    """Plot custom raw candlestick + volume + 3-period MA to mimic trading UI without mplfinance dependency."""
    # Ensure directory
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    fig = plt.figure(figsize=(10, 6), facecolor=BG_COLOR)
    # 2 rows for layout: 1 for OHLC, 1 for Volume
    gs = fig.add_gridspec(3, 1, hspace=0.1)
    ax1 = fig.add_subplot(gs[0:2, 0])
    ax2 = fig.add_subplot(gs[2, 0], sharex=ax1)
    
    ax1.set_facecolor(BG_COLOR)
    ax2.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    
    # Calculate colors based on Close > Open
    colors = [UP_COLOR if close >= open_ else DOWN_COLOR 
              for close, open_ in zip(df['Close'], df['Open'])]
    
    dates = df.index
    # Draw wicks
    ax1.vlines(dates, df['Low'], df['High'], color=colors, linewidth=1.5)
    
    # Draw candle bodies
    # If Close == Open, make it slightly thicker so it's visible
    body_tops = df[['Open', 'Close']].max(axis=1)
    body_bottoms = df[['Open', 'Close']].min(axis=1)
    body_heights = body_tops - body_bottoms
    body_heights[body_heights == 0] = 0.5 # Minimum height visibility
    
    ax1.bar(dates, body_heights, bottom=body_bottoms, color=colors, edgecolor=colors, width=4)
    
    # Plot 4-period Moving Average on Closing prices (equating roughly to a 1-month MA for weekly candles)
    if len(df) >= 4:
        df['MA4'] = df['Close'].rolling(window=4).mean()
        ax1.plot(dates, df['MA4'], color=MA_COLOR, linewidth=2, label='1-Month MA')
        ax1.legend(loc="upper left", facecolor=BG_COLOR, edgecolor=GRID_COLOR, labelcolor=TEXT_COLOR)
    
    # Title & styling
    ax1.set_title(f"LeetCode Activity (Weekly OHLC)", color=TEXT_COLOR, pad=15, fontweight='bold', fontsize=14)
    for ax in [ax1, ax2]:
        ax.grid(color=GRID_COLOR, linestyle='-', linewidth=0.5)
        ax.tick_params(colors=TEXT_COLOR)
        for spine in ax.spines.values():
            spine.set_color(GRID_COLOR)

    # Plot Volume
    ax2.bar(dates, df['Volume'], color=colors, width=4, alpha=0.7)
    ax2.set_ylabel("Total Solves", color=TEXT_COLOR, fontweight='bold')
    # hide x labels on ax1
    plt.setp(ax1.get_xticklabels(), visible=False)
    
    # X-axis Date formatting
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, transparent=False, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close()

# ── Main ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"[INFO] Fetching LeetCode data for '{LEETCODE_USER}' …")
    user_data = fetch_leetcode_data(LEETCODE_USER)
    
    # Save rank data to JSON for dynamic badge
    stats_path = os.path.join(os.path.dirname(OUTPUT_PATH), "leetcode_stats.json")
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    if user_data and "profile" in user_data:
        rank = user_data["profile"]["ranking"]
        formatted_rank = f"{rank:,}"
        with open(stats_path, "w") as f:
            json.dump({"rank": formatted_rank}, f)
        print(f"[OK] Rank saved → {stats_path}")

    if not user_data or "submissionCalendar" not in user_data:
        print("[WARN] No submission data returned — generating placeholder chart.")
        dates = pd.date_range(end=datetime.date.today(), periods=WEEKS_TO_SHOW, freq="W-MON")
        daily = pd.Series(0, index=dates, dtype=float)
    else:
        calendar = json.loads(user_data["submissionCalendar"])
        daily = build_daily_series(calendar)

    df = weekly_ohlc(daily)
    plot_dark_candlestick(df, OUTPUT_PATH)
    print(f"[OK] Chart generated at {OUTPUT_PATH}")
