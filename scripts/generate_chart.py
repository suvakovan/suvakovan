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

# Theme: Clean Light Trading View
BG_COLOR    = "#ffffff"
TEXT_COLOR  = "#333333"
GRID_COLOR  = "#e0e0e0"
UP_COLOR    = "#00Bf41"  # Classic Green
DOWN_COLOR  = "#ff3333"  # Classic Red

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

def plot_light_candlestick(df: pd.DataFrame, out_path: str):
    """Plot custom raw candlestick to mimic exact classic trading UI."""
    # Ensure directory
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG_COLOR)
    
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    
    # Calculate colors based on Close >= Open
    colors = [UP_COLOR if close >= open_ else DOWN_COLOR 
              for close, open_ in zip(df['Close'], df['Open'])]
    edge_colors = ["#000000" for _ in colors] # Dark edges
    
    dates = df.index
    # Draw wicks (thin black or colored lines)
    ax.vlines(dates, df['Low'], df['High'], color="#444444", linewidth=1.2)
    
    # Draw candle bodies
    body_tops = df[['Open', 'Close']].max(axis=1)
    body_bottoms = df[['Open', 'Close']].min(axis=1)
    body_heights = body_tops - body_bottoms
    body_heights[body_heights == 0] = 0.5 # Minimum height visibility
    
    ax.bar(dates, body_heights, bottom=body_bottoms, color=colors, edgecolor="#444444", linewidth=1, width=4)
    
    # Title & styling
    ax.set_title("LeetCode Weekly Activity", color=TEXT_COLOR, pad=15, fontweight='bold', fontsize=14, loc='left')
    ax.grid(color=GRID_COLOR, linestyle='-', linewidth=0.5, axis='y') # Only Y grid like standard
    ax.tick_params(colors=TEXT_COLOR)
    
    # Clean up spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['bottom'].set_color("#666666")

    # X-axis Date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b \'%y'))
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, transparent=False, bbox_inches='tight', facecolor=BG_COLOR)
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
    plot_light_candlestick(df, OUTPUT_PATH)
    print(f"[OK] Chart generated at {OUTPUT_PATH}")
