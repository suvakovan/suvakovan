import requests
import json
import os
import datetime
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.animation as animation

matplotlib.use('Agg')

LEETCODE_USER = "suvakovan"
OUTPUT_PATH = "assets/leetcode_candlestick.gif"
WEEKS_TO_SHOW = 24  # About 6 months

# Theme: Sleek Dark Trending
BG_COLOR    = "#0d1117"
TEXT_COLOR  = "#c9d1d9"
GRID_COLOR  = "#21262d"
UP_COLOR    = "#00ff41"
DOWN_COLOR  = "#ff0000"

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
            headers={
                "Content-Type": "application/json", 
                "Referer": "https://leetcode.com",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
            },
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
    
    # Fill backwards for required duration
    full_range = pd.date_range(end=datetime.date.today(), periods=WEEKS_TO_SHOW*7, freq='D')
    s = s.reindex(full_range, fill_value=0)
    return s

def weekly_ohlc(daily_series: pd.Series) -> pd.DataFrame:
    df = daily_series.to_frame(name='Volume')
    weekly = df.resample('W-MON')
    
    ohlc = pd.DataFrame({
        'Open': weekly['Volume'].first(),
        'High': weekly['Volume'].max(),
        'Low': weekly['Volume'].min(),
        'Close': weekly['Volume'].last()
    })
    ohlc.fillna(0, inplace=True)
    return ohlc.tail(WEEKS_TO_SHOW)

def plot_animated_candlestick(df: pd.DataFrame, out_path: str):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=BG_COLOR)
    ax.set_facecolor(BG_COLOR)
    fig.patch.set_facecolor(BG_COLOR)
    
    # Pre-calculate bounds
    max_high = df['High'].max()
    max_high = max_high * 1.1 if max_high > 0 else 10
    dates = df.index
    
    def update(frame):
        ax.clear()
        ax.set_facecolor(BG_COLOR)
        
        # Current slice of data
        curr_df = df.iloc[:frame+1]
        
        colors = [UP_COLOR if close >= open_ else DOWN_COLOR 
                  for close, open_ in zip(curr_df['Close'], curr_df['Open'])]
        
        # Wicks
        ax.vlines(curr_df.index, curr_df['Low'], curr_df['High'], color="#444444", linewidth=1.2)
        
        # Bodies
        body_tops = curr_df[['Open', 'Close']].max(axis=1)
        body_bottoms = curr_df[['Open', 'Close']].min(axis=1)
        body_heights = body_tops - body_bottoms
        body_heights[body_heights == 0] = 0.5
        
        ax.bar(curr_df.index, body_heights, bottom=body_bottoms, color=colors, edgecolor="#444444", linewidth=1, width=4)
        
        subtitleDate = datetime.date.today().strftime('%b %d, %Y')
        ax.set_title("LeetCode Candlestick Chart", color=TEXT_COLOR, pad=25, fontweight='bold', fontsize=14, loc='center')
        ax.text(0.5, 0.95, f"As of: {subtitleDate}", transform=ax.transAxes, color="#8b949e", fontsize=11, ha='center', va='top')
        
        ax.grid(color=GRID_COLOR, linestyle='-', linewidth=0.5, axis='y')
        ax.tick_params(colors=TEXT_COLOR)
        
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color("#666666")

        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b \'%y'))
        
        ax.set_ylim(0, max_high)
        ax.set_xlim(dates[0] - pd.Timedelta(days=7), dates[-1] + pd.Timedelta(days=7))
    
    ani = animation.FuncAnimation(fig, update, frames=len(df), repeat=True, repeat_delay=2000)
    
    # Save as GIF using pillow
    ani.save(out_path, writer='pillow', fps=8)
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
        dates = pd.date_range(end=datetime.date.today(), periods=WEEKS_TO_SHOW*7, freq="D")
        daily = pd.Series(0, index=dates, dtype=float)
    else:
        calendar = json.loads(user_data["submissionCalendar"])
        daily = build_daily_series(calendar)

    df = weekly_ohlc(daily)
    plot_animated_candlestick(df, OUTPUT_PATH)
    print(f"[OK] Animated Chart generated at {OUTPUT_PATH}")
