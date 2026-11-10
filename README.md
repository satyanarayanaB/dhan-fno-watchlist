# 🚀 Dhan 'Satya FNO' Watchlist - Cloud Scheduler (GitHub Actions)

Autonomous cloud workflow that runs **every weekday at 09:20 AM IST** without requiring your computer to be turned on.

---

## ⚡ How It Works
1. **TradingView Heatmap Scan**: Scans all 50 constituents of **NIFTY 50** at 09:20 AM IST.
2. **Top & Bottom Sector Ranking**: Calculates market-cap weighted performance matching TradingView Heatmap's visual coloring to identify:
   - **Bullish Momentum Sector** (Brightest Green)
   - **Bearish Momentum Sector** (Deepest Red)
3. **Stock Selection**:
   - Shortlists the **Top 3 Bullish Stocks** from the leading sector(s).
   - Shortlists the **Bottom 3 Bearish Stocks** from the lagging sector(s).
4. **ATM Option Resolution**: Queries Dhan's live NSE F&O instrument master to calculate the exact **At-The-Money (ATM) Strike Price** for each stock:
   - **ATM CE (Call Option)** for bullish momentum.
   - **ATM PE (Put Option)** for bearish momentum / hedging.
5. **Dhan Account Sync**:
   - Syncs the contracts into your Dhan user watchlist: **`Satya FNO`**.
   - Generates a downloadable `satya_fno_watchlist.csv` artifact.
6. **Instant Telegram Alert**: Dispatches a formatted notification with spot prices, strikes, lot sizes, and Dhan Security IDs to your Telegram bot (`@Sathya2207bot`).

---

## 🕒 Cloud Schedule
- **Schedule**: `50 3 * * 1-5` (UTC 03:50 = **09:20 AM IST**, Monday through Friday).
- **Execution Platform**: GitHub Actions (Ubuntu Cloud Runner).
- **Zero Local Dependency**: Your PC does **NOT** need to be turned on or connected to the internet.

---

## 🔐 Setup Instructions

### Step 1: Push Code to Your GitHub Repository
1. Create a new repository on [GitHub](https://github.com/new) (e.g. `dhan-fno-watchlist`).
2. Run these commands from this folder (`C:\Users\ADMIN\dhan_fno_watchlist`):
   ```bash
   git remote add origin https://github.com/<YOUR-GITHUB-USERNAME>/<YOUR-REPO-NAME>.git
   git branch -M main
   git push -u origin main
   ```

### Step 2: Configure GitHub Repository Secrets
Go to your GitHub repository:
**Settings** > **Secrets and variables** > **Actions** > **New repository secret**

Add the following 4 secrets:
| Secret Name | Description | Example / Value |
|---|---|---|
| `DHAN_CLIENT_ID` | Your Dhan Client ID | Found on `web.dhan.co` |
| `DHAN_ACCESS_TOKEN` | Dhan API JWT Access Token | Generated via DhanHQ Trading APIs |
| `TELEGRAM_BOT_TOKEN` | Your Telegram Bot Token | '8905804:AAHz1zH_emc5vIRzR6w6nRG-gTYaBphVtWk` |
| `TELEGRAM_CHAT_ID` | Your Telegram Chat ID | `1887514291` |

### Step 3: Trigger a Manual Test Run
1. In your GitHub repository, click the **Actions** tab.
2. Select **"Dhan Satya FNO Watchlist Cloud Scheduler"** on the left.
3. Click **Run workflow** > **Run workflow**.
4. Check your Telegram for the delivered alert!
