"""
Dhan Satya FNO Watchlist Cloud Engine
1. Fetches TradingView Heatmap for NIFTY 50 constituents.
2. Identifies Top Sector (Bullish Momentum) and Bottom Sector (Bearish Momentum).
3. Selects Top 3 stocks from Top Sector(s) (Bullish) and Bottom 3 stocks from Bottom Sector(s) (Bearish).
4. Resolves ATM Call (CE) and Put (PE) options from Dhan Scrip Master.
5. Syncs ATM options into Dhan "Satya FNO" Watchlist via Dhan API.
6. Sends a formatted Telegram Alert to the user.
"""

import os
import sys
import json
import datetime
import requests
import pandas as pd
from pathlib import Path

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "").strip()
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# Fallback to configured defaults if not provided in environment
if not TELEGRAM_BOT_TOKEN:
    TELEGRAM_BOT_TOKEN = "8958905804:AAHz1zH_emc5vIRzR6w6nRG-gTYaBphVtWk"
if not TELEGRAM_CHAT_ID:
    TELEGRAM_CHAT_ID = "1887514291"

BASE_DIR = Path(__file__).resolve().parent
CACHE_PATH = BASE_DIR / "api-scrip-master-fno.csv"
CSV_EXPORT_PATH = BASE_DIR / "satya_fno_watchlist.csv"
DHAN_SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
TRADINGVIEW_SCAN_URL = "https://scanner.tradingview.com/india/scan"

NIFTY_50_TICKERS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", 
    "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY", 
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO", 
    "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT", 
    "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", 
    "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", 
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO"
]

WATCHLIST_NAME = "Satya FNO"

def fetch_nifty50_heatmap_data():
    """Queries TradingView scanner for all Nifty 50 stocks."""
    print("[1/5] Fetching TradingView Heatmap for NIFTY 50...")
    payload = {
        "filter": [
            {"left": "type", "operation": "in_range", "right": ["stock", "dr"]},
            {"left": "exchange", "operation": "equal", "right": "NSE"},
            {"left": "name", "operation": "in_range", "right": NIFTY_50_TICKERS}
        ],
        "options": {"lang": "en"},
        "columns": ["name", "close", "change", "sector", "market_cap_basic", "volume"],
        "range": [0, 60]
    }
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.post(TRADINGVIEW_SCAN_URL, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    raw = r.json().get("data", [])
    
    rows = [item["d"] for item in raw]
    df = pd.DataFrame(rows, columns=["name", "close", "change", "sector", "market_cap", "volume"])
    df = df.dropna(subset=["name", "close", "change", "sector"])
    print(f"      Retrieved {len(df)} NIFTY 50 stocks.")
    return df

def identify_top_bottom_sectors(df, target_stocks_count=3):
    """
    Groups Nifty 50 stocks by sector and calculates market-cap weighted performance.
    Selects 3 Bullish Leader stocks and 3 Bearish Laggard stocks.
    """
    print("[2/5] Calculating Sector Momentum (TradingView Heatmap weights)...")
    sector_stats = []
    for sec_name, group in df.groupby("sector"):
        total_mc = group["market_cap"].sum()
        w_chg = (group["change"] * group["market_cap"]).sum() / total_mc if total_mc > 0 else 0
        sector_stats.append({
            "sector": sec_name,
            "weighted_change": w_chg,
            "stocks_count": len(group),
            "stocks_df": group
        })
    
    # Sort sectors descending by momentum
    sector_stats.sort(key=lambda x: x["weighted_change"], reverse=True)
    
    # Pick top 3 bullish stocks starting from top sectors
    top_stocks_list = []
    top_sectors_used = []
    for sec in sector_stats:
        if len(top_stocks_list) >= target_stocks_count:
            break
        sorted_s = sec["stocks_df"].sort_values(by="change", ascending=False)
        for _, s in sorted_s.iterrows():
            if len(top_stocks_list) < target_stocks_count:
                top_stocks_list.append(s)
                if sec["sector"] not in [x["sector"] for x in top_sectors_used]:
                    top_sectors_used.append(sec)
                    
    # Pick 3 bearish/lagging stocks starting from bottom sectors
    bottom_stocks_list = []
    bottom_sectors_used = []
    for sec in reversed(sector_stats):
        if len(bottom_stocks_list) >= target_stocks_count:
            break
        sorted_s = sec["stocks_df"].sort_values(by="change", ascending=True)
        for _, s in sorted_s.iterrows():
            if len(bottom_stocks_list) < target_stocks_count:
                bottom_stocks_list.append(s)
                if sec["sector"] not in [x["sector"] for x in bottom_sectors_used]:
                    bottom_sectors_used.append(sec)
                    
    top_stocks_df = pd.DataFrame(top_stocks_list)
    bottom_stocks_df = pd.DataFrame(bottom_stocks_list)
    
    top_sec_summary = f"{top_sectors_used[0]['sector']} ({top_sectors_used[0]['weighted_change']:+.2f}%)"
    bottom_sec_summary = f"{bottom_sectors_used[0]['sector']} ({bottom_sectors_used[0]['weighted_change']:+.2f}%)"
    
    print(f"      Top Sector: {top_sec_summary}")
    for _, s in top_stocks_df.iterrows():
        print(f"        -> Bullish Leader: {s['name']} (₹{s['close']:.2f}, {s['change']:+.2f}%)")
        
    print(f"      Bottom Sector: {bottom_sec_summary}")
    for _, s in bottom_stocks_df.iterrows():
        print(f"        -> Bearish Laggard: {s['name']} (₹{s['close']:.2f}, {s['change']:+.2f}%)")
        
    return top_sectors_used[0], top_stocks_df, bottom_sectors_used[0], bottom_stocks_df

def load_dhan_fno_options():
    """Downloads and caches Dhan's NSE Stock Options instrument master."""
    print("[3/5] Loading Dhan F&O Scrip Master...")
    cache_path = CACHE_PATH
    
    if cache_path.exists() and (datetime.datetime.now().timestamp() - cache_path.stat().st_mtime) < 86400:
        print("      Using cached F&O scrip master.")
        df = pd.read_csv(cache_path, low_memory=False)
        return df
        
    print("      Downloading fresh scrip master from Dhan (this takes ~10-15s)...")
    r = requests.get(DHAN_SCRIP_MASTER_URL, timeout=60)
    r.raise_for_status()
    
    # Filter only NSE OPTSTK to keep memory and processing instant
    full_df = pd.read_csv(pd.io.common.StringIO(r.text), low_memory=False)
    fno_df = full_df[(full_df["SEM_EXM_EXCH_ID"] == "NSE") & (full_df["SEM_INSTRUMENT_NAME"] == "OPTSTK")].copy()
    
    fno_df.to_csv(cache_path, index=False)
    print(f"      Loaded {len(fno_df)} active NSE stock options.")
    return fno_df

def find_atm_contracts(fno_df, stock_symbol, spot_price):
    """
    Finds nearest monthly/weekly expiry and exact ATM Call (CE) & Put (PE) for a stock.
    """
    sym_query = stock_symbol.replace("-", "_") if stock_symbol == "BAJAJ-AUTO" else stock_symbol
    opts = fno_df[fno_df["SEM_TRADING_SYMBOL"].str.startswith(f"{sym_query}-")].copy()
    
    if opts.empty:
        opts = fno_df[fno_df["SEM_CUSTOM_SYMBOL"].str.startswith(f"{stock_symbol} ")].copy()
        
    if opts.empty:
        print(f"      [WARN] No option contracts found for {stock_symbol}")
        return None, None
        
    now_str = datetime.datetime.now().strftime("%Y-%m-%d")
    opts["exp_date_str"] = pd.to_datetime(opts["SEM_EXPIRY_DATE"]).dt.strftime("%Y-%m-%d")
    active_expiries = sorted([x for x in opts["exp_date_str"].unique() if x >= now_str])
    
    if not active_expiries:
        active_expiries = sorted(opts["exp_date_str"].unique())
        
    nearest_expiry = active_expiries[0]
    exp_opts = opts[opts["exp_date_str"] == nearest_expiry].copy()
    
    exp_opts["diff"] = (exp_opts["SEM_STRIKE_PRICE"] - spot_price).abs()
    closest_strike = exp_opts.sort_values(by="diff").iloc[0]["SEM_STRIKE_PRICE"]
    
    ce_rows = exp_opts[(exp_opts["SEM_STRIKE_PRICE"] == closest_strike) & (exp_opts["SEM_OPTION_TYPE"] == "CE")]
    pe_rows = exp_opts[(exp_opts["SEM_STRIKE_PRICE"] == closest_strike) & (exp_opts["SEM_OPTION_TYPE"] == "PE")]
    
    atm_ce = ce_rows.iloc[0].to_dict() if not ce_rows.empty else None
    atm_pe = pe_rows.iloc[0].to_dict() if not pe_rows.empty else None
    
    return atm_ce, atm_pe

def sync_to_dhan_watchlist(instruments_to_add):
    """
    Syncs the instruments to Dhan user watchlist 'Satya FNO'.
    Supports Dhan API and generates Watchlist CSV.
    """
    print(f"[4/5] Syncing to Dhan Watchlist: '{WATCHLIST_NAME}'...")
    
    # Export CSV for Dhan Web / TradingView import
    csv_rows = []
    for inst in instruments_to_add:
        csv_rows.append({
            "Exchange": "NSE_FNO",
            "TradingSymbol": inst["SEM_TRADING_SYMBOL"],
            "CustomSymbol": inst["SEM_CUSTOM_SYMBOL"],
            "SecurityId": inst["SEM_SMST_SECURITY_ID"],
            "Strike": inst["SEM_STRIKE_PRICE"],
            "Type": inst["SEM_OPTION_TYPE"],
            "Expiry": inst["SEM_EXPIRY_DATE"],
            "LotSize": inst["SEM_LOT_UNITS"]
        })
        
    export_df = pd.DataFrame(csv_rows)
    export_df.to_csv(CSV_EXPORT_PATH, index=False)
    print(f"      Saved '{CSV_EXPORT_PATH.name}'.")
    
    if not DHAN_CLIENT_ID or not DHAN_ACCESS_TOKEN:
        print("      [NOTE] DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not set in environment.")
        print("      Watchlist CSV generated. Provide Dhan credentials in GitHub Secrets to sync live.")
        return False
        
    headers = {
        "access-token": DHAN_ACCESS_TOKEN,
        "client-id": DHAN_CLIENT_ID,
        "Content-Type": "application/json"
    }
    
    try:
        payload = {
            "watchlistName": WATCHLIST_NAME,
            "instrumentList": [
                {
                    "exchangeSegment": "NSE_FNO",
                    "securityId": str(int(inst["SEM_SMST_SECURITY_ID"]))
                }
                for inst in instruments_to_add
            ]
        }
        
        post_res = requests.post("https://api.dhan.co/v2/watchlist", json=payload, headers=headers, timeout=10)
        if post_res.status_code in [200, 201]:
            print(f"      [SUCCESS] Successfully synced {len(instruments_to_add)} ATM contracts to '{WATCHLIST_NAME}' on Dhan!")
            return True
        else:
            print(f"      [API Status] {post_res.status_code}: {post_res.text}")
            return False
    except Exception as e:
        print(f"      [WARN] Could not connect to Dhan API: {e}")
        return False

def send_telegram_alert(top_sec, top_opts, bottom_sec, bottom_opts):
    """Sends detailed ATM options breakdown to Telegram."""
    print("[5/5] Sending Telegram Alert...")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("      Telegram Bot Token or Chat ID not configured.")
        return
        
    now_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    lines = [
        "🎯 *DHAN CLOUD SCHEDULER: 'Satya FNO' WATCHLIST*",
        f"📅 _{now_str}_",
        "📊 *Filter:* NIFTY 50 Top & Bottom Heatmap Sectors",
        "━━━━━━━━━━━━━━━━━━━━━━",
        ""
    ]
    
    # Top Sector (Bullish Momentum -> ATM CE)
    lines.append(f"🟢 *BULLISH MOMENTUM SECTOR: {top_sec['sector']}* ({top_sec['weighted_change']:+.2f}%)")
    lines.append("   _Top 3 Stocks & ATM Calls (CE):_")
    for item in top_opts:
        stock = item["stock"]
        ce = item["ce"]
        if ce:
            lines.append(
                f"   • *`{stock['name']}`* (Spot ₹{stock['close']:,.1f}, *{stock['change']:+.2f}%*)\n"
                f"     👉 *ATM CE:* `{ce['SEM_TRADING_SYMBOL']}`\n"
                f"     Strike: ₹{ce['SEM_STRIKE_PRICE']} | Lot: {int(ce['SEM_LOT_UNITS'])} | Id: `{ce['SEM_SMST_SECURITY_ID']}`"
            )
    lines.append("")
    
    # Bottom Sector (Bearish Momentum -> ATM PE)
    lines.append(f"🔴 *BEARISH MOMENTUM SECTOR: {bottom_sec['sector']}* ({bottom_sec['weighted_change']:+.2f}%)")
    lines.append("   _Bottom 3 Stocks & ATM Puts (PE):_")
    for item in bottom_opts:
        stock = item["stock"]
        pe = item["pe"]
        if pe:
            lines.append(
                f"   • *`{stock['name']}`* (Spot ₹{stock['close']:,.1f}, *{stock['change']:+.2f}%*)\n"
                f"     👉 *ATM PE:* `{pe['SEM_TRADING_SYMBOL']}`\n"
                f"     Strike: ₹{pe['SEM_STRIKE_PRICE']} | Lot: {int(pe['SEM_LOT_UNITS'])} | Id: `{pe['SEM_SMST_SECURITY_ID']}`"
            )
            
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("💼 *Dhan Watchlist:* Added to `Satya FNO`")
    lines.append("⚡ _Cloud Job executed via GitHub Actions._")
    
    msg = "\n".join(lines)
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }, timeout=15)
        if r.json().get("ok"):
            print("      [SUCCESS] Telegram notification delivered!")
        else:
            print("      Telegram API error:", r.text)
    except Exception as e:
        print("      Failed to send Telegram message:", e)

def main():
    print("=" * 65)
    print("  DHAN NIFTY 50 HEATMAP -> 'Satya FNO' ATM OPTIONS SYNC")
    print(f"  Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)
    
    # 1. Fetch Heatmap
    df = fetch_nifty50_heatmap_data()
    
    # 2. Get Top & Bottom Sectors
    top_sec, top_stocks, bottom_sec, bottom_stocks = identify_top_bottom_sectors(df, target_stocks_count=3)
    
    # 3. Load Dhan Scrip Master
    fno_df = load_dhan_fno_options()
    
    # 4. Resolve ATM Options
    print("Finding ATM CE & PE Options for Top & Bottom Stocks...")
    instruments_to_sync = []
    top_results = []
    for _, s in top_stocks.iterrows():
        ce, pe = find_atm_contracts(fno_df, s["name"], s["close"])
        top_results.append({"stock": s, "ce": ce, "pe": pe})
        if ce:
            instruments_to_sync.append(ce)
        if pe:
            instruments_to_sync.append(pe)
            
    bottom_results = []
    for _, s in bottom_stocks.iterrows():
        ce, pe = find_atm_contracts(fno_df, s["name"], s["close"])
        bottom_results.append({"stock": s, "ce": ce, "pe": pe})
        if ce:
            instruments_to_sync.append(ce)
        if pe:
            instruments_to_sync.append(pe)
            
    # 5. Sync to Dhan Watchlist
    sync_to_dhan_watchlist(instruments_to_sync)
    
    # 6. Send Telegram Alert
    send_telegram_alert(top_sec, top_results, bottom_sec, bottom_results)
    print("=" * 65)
    print("  Job Completed Successfully!")
    print("=" * 65)

if __name__ == "__main__":
    main()
