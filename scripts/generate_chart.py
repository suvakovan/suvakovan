import requests
import json
import os
import datetime
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

matplotlib.use('Agg')

LEETCODE_USER = "suvakovan"
OUTPUT_PATH = "assets/leetcode_trend.png"
DAYS_TO_SHOW = 120  # Roughly 4 months

# Theme: Sleek Dark Trending
BG_COLOR    = "#0d1117"
TEXT_COLOR  = "#c9d1d9"
GRID_COLOR  = "#21262d"
LINE_COLOR  = "#00ff41"
FILL_COLOR  = "#00ff41"

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
    dates_counts = {}
    for ts_str, count in calendar_data.items():
        ts = int(ts_str)
        dt = datetime.datetime.fromtimestamp(ts).date()
        dates_counts[dt] = dates_counts.get(dt, 0) + count
    
    if not dates_counts:
        return pd.Series(dtype=float)

    s = pd.Series(dates_counts)
    s.index = pd.to_datetime(s.index)
    
    full_range = pd.date_range(end=datetime.date.today(), periods=DAYS_TO_SHOW, freq='D')
    s = s.reindex(full_range, fill_value=0)
    return s

def plot_trend_chart(s: pd.Series, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    # Apply a 7-day rolling average to create a smooth "trend"
    trend = s.rolling(window=7, min_periods=1).mean()
    
    fig, ax = plt.subplots(figsize=(10, 4), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    
    dates = trend.index
    values = trend.values
    
    # Plot the vibrant line
    ax.plot(dates, values, color=LINE_COLOR, linewidth=2.5, alpha=0.9)
    
    # Add a glowing area fill under the line
    ax.fill_between(dates, values, 0, color=FILL_COLOR, alpha=0.15)
    
    # Clean styling
    ax.set_title("LeetCode Submission Trend (7-Day Avg)", color=TEXT_COLOR, pad=15, fontweight='bold', fontsize=14, loc='center')
    ax.grid(color=GRID_COLOR, linestyle='-', linewidth=1, alpha=0.5)
    ax.tick_params(colors=TEXT_COLOR)
    
    # Remove top/right spines
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(GRID_COLOR)
    ax.spines['bottom'].set_color(GRID_COLOR)

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d'))
    plt.xticks(rotation=0)
    
    # Ensure baseline is exactly 0
    ax.set_ylim(bottom=0)
    ax.set_xlim(left=dates[0], right=dates[-1])
    
    plt.tight_layout()
    plt.savefig(out_path, dpi=120, transparent=False, bbox_inches='tight', facecolor=BG_COLOR)
    plt.close()

if __name__ == "__main__":
    print(f"[INFO] Fetching LeetCode data for '{LEETCODE_USER}' …")
    user_data = fetch_leetcode_data(LEETCODE_USER)
    
    stats_path = os.path.join(os.path.dirname(OUTPUT_PATH), "leetcode_stats.json")
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)
    if user_data and "profile" in user_data:
        rank = user_data["profile"]["ranking"]
        formatted_rank = f"{rank:,}"
        with open(stats_path, "w") as f:
            json.dump({"rank": formatted_rank}, f)
        print(f"[OK] Rank saved → {stats_path}")

    if not user_data or "submissionCalendar" not in user_data:
        print("[WARN] No submission data returned — generating empty chart.")
        dates = pd.date_range(end=datetime.date.today(), periods=DAYS_TO_SHOW, freq="D")
        daily = pd.Series(0, index=dates, dtype=float)
    else:
        calendar = json.loads(user_data["submissionCalendar"])
        daily = build_daily_series(calendar)

    plot_trend_chart(daily, OUTPUT_PATH)
    print(f"[OK] Trend Chart generated at {OUTPUT_PATH}")
