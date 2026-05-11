import os
import requests
from datetime import datetime
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, Form, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from dotenv import load_dotenv

# Load environment variables from .env file for local execution
load_dotenv()

app = FastAPI(title="NIFTY 100 Swing Trader")

# ==========================================
# CONFIGURATION & ENV VARIABLES
# ==========================================
DATABASE_URL = os.getenv("DATABASE_URL")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

NIFTY_100_TICKERS = [
    'ABB.NS', 'ADANIENSOL.NS', 'ADANIGREEN.NS', 'ADANIPOWER.NS', 'AMBUJACEM.NS', 'DMART.NS', 'BAJAJHLDNG.NS', 'BANKBARODA.NS', 'BPCL.NS', 'BOSCHLTD.NS', 'BRITANNIA.NS', 'CGPOWER.NS', 'CANBK.NS', 'CHOLAFIN.NS', 'CUMMINSIND.NS', 'DLF.NS', 'DIVISLAB.NS', 'GAIL.NS', 'GODREJCP.NS', 'HDFCAMC.NS', 'HAL.NS', 'HINDZINC.NS', 'HYUNDAI.NS', 'INDHOTEL.NS', 'IOC.NS', 'IRFC.NS', 'JINDALSTEL.NS', 'LTM.NS', 'LODHA.NS', 'MAZDOCK.NS', 'MUTHOOTFIN.NS', 'PIDILITIND.NS', 'PFC.NS', 'PNB.NS', 'RECLTD.NS', 'MOTHERSON.NS', 'SHREECEM.NS', 'ENRIN.NS', 'SIEMENS.NS', 'SOLARINDS.NS', 'TVSMOTOR.NS', 'TATACAP.NS', 'TMCV.NS', 'TATAPOWER.NS', 'TORNTPHARM.NS', 'UNIONBANK.NS', 'UNITDSPR.NS', 'VBL.NS', 'VEDL.NS', 'ZYDUSLIFE.NS',
    'ADANIENT.NS', 'ADANIPORTS.NS', 'APOLLOHOSP.NS', 'ASIANPAINT.NS', 'AXISBANK.NS', 'BAJAJ-AUTO.NS', 'BAJFINANCE.NS', 'BAJAJFINSV.NS', 'BEL.NS', 'BHARTIARTL.NS', 'CIPLA.NS', 'COALINDIA.NS', 'DRREDDY.NS', 'EICHERMOT.NS', 'ETERNAL.NS', 'GRASIM.NS', 'HCLTECH.NS', 'HDFCBANK.NS', 'HDFCLIFE.NS', 'HINDALCO.NS', 'HINDUNILVR.NS', 'ICICIBANK.NS', 'ITC.NS', 'INFY.NS', 'INDIGO.NS', 'JSWSTEEL.NS', 'JIOFIN.NS', 'KOTAKBANK.NS', 'LT.NS', 'M&M.NS', 'MARUTI.NS', 'MAXHEALTH.NS', 'NTPC.NS', 'NESTLEIND.NS', 'ONGC.NS', 'POWERGRID.NS', 'RELIANCE.NS', 'SBILIFE.NS', 'SHRIRAMFIN.NS', 'SBIN.NS', 'SUNPHARMA.NS', 'TCS.NS', 'TATACONSUM.NS', 'TMPV.NS', 'TATASTEEL.NS', 'TECHM.NS', 'TITAN.NS', 'TRENT.NS', 'ULTRACEMCO.NS', 'WIPRO.NS'
]

# ==========================================
# HELPERS
# ==========================================
def get_db_connection():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL is not set!")
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def send_telegram_alert(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram missing config. Msg:", message)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, data=payload)
    except Exception as e:
        print(f"Telegram error: {e}")

# ==========================================
# WEB DASHBOARD (UI)
# ==========================================
@app.get("/", response_class=HTMLResponse)
def dashboard():
    if not DATABASE_URL:
        return "<h3>Error: DATABASE_URL is missing. Please check your .env file.</h3>"
        
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get Portfolio
        cur.execute("SELECT * FROM portfolio LIMIT 1;")
        portfolio = cur.fetchone()
        if not portfolio:
            return "Database not initialized. Please run setup_db.py."
        
        # Get Active Positions
        cur.execute("SELECT * FROM positions WHERE status = 'active' ORDER BY entry_date DESC;")
        positions = cur.fetchall()
        
        conn.close()
    except Exception as e:
        return f"<h3>Database Connection Error:</h3><p>{e}</p>"
    
    # Basic HTML UI
    html = f"""
    <html>
    <head>
        <title>Swing Trading Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body class="bg-light">
    <div class="container mt-5">
        <h2 class="mb-4">📈 NIFTY 100 Swing Trading Dashboard</h2>
        
        <div class="row">
            <div class="col-md-4">
                <div class="card text-white bg-primary mb-3">
                  <div class="card-header">Portfolio Overview</div>
                  <div class="card-body">
                    <h5 class="card-title">Available Capital</h5>
                    <p class="card-text fs-3">₹{portfolio['available_capital']:,.2f}</p>
                    <small>Initial Capital: ₹{portfolio['total_capital']:,.2f}</small>
                  </div>
                </div>
                
                <div class="card mb-3">
                  <div class="card-header">Log New Trade</div>
                  <div class="card-body">
                    <form action="/add_position_ui" method="post">
                      <input type="text" name="ticker" class="form-control mb-2" placeholder="Ticker (e.g. COALINDIA.NS)" required>
                      <select name="strategy" class="form-control mb-2">
                        <option value="RSI Pullback">RSI Pullback</option>
                        <option value="SMA44 Pullback">SMA44 Pullback</option>
                        <option value="RSI Divergence">RSI Divergence</option>
                      </select>
                      <input type="number" step="0.01" name="entry_price" class="form-control mb-2" placeholder="Entry Price" required>
                      <input type="number" name="quantity" class="form-control mb-2" placeholder="Quantity" required>
                      <input type="number" step="0.01" name="sl_price" class="form-control mb-2" placeholder="Stop Loss" required>
                      <input type="number" step="0.01" name="target_price" class="form-control mb-2" placeholder="Target Price" required>
                      <button type="submit" class="btn btn-success w-100">Add Trade</button>
                    </form>
                  </div>
                </div>
            </div>
            
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">Active Positions</div>
                    <div class="card-body">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Ticker</th><th>Strategy</th><th>Entry Date</th><th>Price</th><th>Qty</th><th>SL</th><th>Target</th><th>Bars</th><th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
    """
    for p in positions:
        html += f"""
            <tr>
                <td><strong>{p['ticker']}</strong></td>
                <td>{p['strategy']}</td>
                <td>{p['entry_date']}</td>
                <td>₹{p['entry_price']:.2f}</td>
                <td>{p['quantity']}</td>
                <td class="text-danger">₹{p['sl_price']:.2f}</td>
                <td class="text-success">₹{p['target_price']:.2f}</td>
                <td>{p['bars_held']}</td>
                <td>
                    <form action="/close_position_ui" method="post" class="m-0">
                        <input type="hidden" name="position_id" value="{p['id']}">
                        <input type="number" step="0.01" name="exit_price" placeholder="Exit Px" required style="width: 70px;">
                        <input type="text" name="reason" placeholder="Reason" required style="width: 80px;">
                        <button type="submit" class="btn btn-sm btn-danger">Close</button>
                    </form>
                </td>
            </tr>
        """
    html += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    </body>
    </html>
    """
    return html

# ==========================================
# UI FORM ENDPOINTS
# ==========================================
@app.post("/add_position_ui")
def add_position_ui(
    ticker: str = Form(...), strategy: str = Form(...), entry_price: float = Form(...),
    quantity: int = Form(...), sl_price: float = Form(...), target_price: float = Form(...)
):
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Deduct capital + 35 INR fees
    cost = (quantity * entry_price) + 35
    cur.execute("UPDATE portfolio SET available_capital = available_capital - %s WHERE id = 1;", (cost,))
    
    # Insert position
    cur.execute("""
        INSERT INTO positions (ticker, strategy, entry_date, entry_price, quantity, sl_price, target_price, bars_held, status)
        VALUES (%s, %s, CURRENT_DATE, %s, %s, %s, %s, 0, 'active')
    """, (ticker.upper(), strategy, entry_price, quantity, sl_price, target_price))
    
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)


@app.post("/close_position_ui")
def close_position_ui(position_id: int = Form(...), exit_price: float = Form(...), reason: str = Form(...)):
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM positions WHERE id = %s AND status = 'active';", (position_id,))
    pos = cur.fetchone()
    if pos:
        entry_price = float(pos['entry_price'])
        sell_value = (pos['quantity'] * exit_price) - 40
        buy_cost = (pos['quantity'] * entry_price) + 35
        profit = sell_value - buy_cost
        ret_pct = ((exit_price / entry_price) - 1) * 100
        
        # Add to available capital
        cur.execute("UPDATE portfolio SET available_capital = available_capital + %s WHERE id = 1;", (sell_value,))
        # Update position
        cur.execute("UPDATE positions SET status = 'closed' WHERE id = %s;", (position_id,))
        # Log to history
        cur.execute("""
            INSERT INTO trade_history (ticker, strategy, entry_date, exit_date, entry_price, exit_price, quantity, profit_loss, return_pct, reason)
            VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s)
        """, (pos['ticker'], pos['strategy'], pos['entry_date'], entry_price, exit_price, pos['quantity'], profit, ret_pct, reason))
        
    conn.commit()
    conn.close()
    return RedirectResponse(url="/", status_code=303)

# ==========================================
# EXITS AUTOMATION (Run at 3:15 PM)
# ==========================================
@app.get("/check_exits")
def check_exits():
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM positions WHERE status = 'active';")
    positions = cur.fetchall()
    
    alerts = []
    
    for pos in positions:
        ticker = pos['ticker']
        try:
            df = yf.download(ticker, period="1d", progress=False)
            if df.empty:
                continue
            
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            today_high = float(df['High'].iloc[-1])
            today_low = float(df['Low'].iloc[-1])
            today_close = float(df['Close'].iloc[-1])
            
            sl_price = float(pos['sl_price'])
            target_price = float(pos['target_price'])
            entry_price = float(pos['entry_price'])
            
            exit_triggered = False
            exit_reason = ""
            exit_price = 0.0
            
            if today_low <= sl_price:
                exit_triggered = True
                exit_reason = "Stop Loss (1.5x ATR)"
                exit_price = sl_price
            elif today_high >= target_price:
                exit_triggered = True
                exit_reason = "Target Hit (1:2 RR)"
                exit_price = target_price
            elif pos['bars_held'] >= 20:
                exit_triggered = True
                exit_reason = "Time Exit (20 Days)"
                exit_price = today_close
                
            if exit_triggered:
                sell_value = (pos['quantity'] * exit_price) - 40
                buy_cost = (pos['quantity'] * entry_price) + 35
                profit = sell_value - buy_cost
                ret_pct = ((exit_price / entry_price) - 1) * 100
                
                cur.execute("UPDATE portfolio SET available_capital = available_capital + %s WHERE id = 1;", (sell_value,))
                cur.execute("UPDATE positions SET status = 'closed' WHERE id = %s;", (pos['id'],))
                cur.execute("""
                    INSERT INTO trade_history (ticker, strategy, entry_date, exit_date, entry_price, exit_price, quantity, profit_loss, return_pct, reason)
                    VALUES (%s, %s, %s, CURRENT_DATE, %s, %s, %s, %s, %s, %s)
                """, (pos['ticker'], pos['strategy'], pos['entry_date'], entry_price, exit_price, pos['quantity'], profit, ret_pct, exit_reason))
                
                icon = "🟢" if profit > 0 else "🔴"
                alerts.append(f"{icon} <b>EXIT EXECUTED: {ticker}</b>\nReason: {exit_reason}\nProfit/Loss: ₹{profit:.2f} ({ret_pct:.2f}%)")
            else:
                cur.execute("UPDATE positions SET bars_held = bars_held + 1 WHERE id = %s;", (pos['id'],))
        except Exception as e:
            print(f"Error checking exit for {ticker}: {e}")

    conn.commit()
    conn.close()
    
    if alerts:
        msg = f"🚨 <b>3:15 PM EXIT ALERTS</b> 🚨\n\n" + "\n\n".join(alerts)
        send_telegram_alert(msg)
        
    return {"status": "checked", "exits_triggered": len(alerts)}

# ==========================================
# ENTRIES AUTOMATION (Run at 4:30 PM)
# ==========================================
@app.get("/generate_entries")
def generate_entries():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT ticker FROM positions WHERE status = 'active';")
    active_tickers = [row['ticker'] for row in cur.fetchall()]
    
    cur.execute("SELECT * FROM portfolio LIMIT 1;")
    portfolio = cur.fetchone()
    conn.close()
    
    nifty = yf.download('^NSEI', period='1y', progress=False)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)
        
    nifty['SMA_50'] = ta.sma(nifty['Close'], length=50)
    nifty['SMA_200'] = ta.sma(nifty['Close'], length=200)
    latest_nifty = nifty.iloc[-1]
    
    regime = "Choppy"
    if latest_nifty['Close'] > latest_nifty['SMA_50'] and latest_nifty['SMA_50'] > latest_nifty['SMA_200']:
        regime = "Bullish"
    elif latest_nifty['Close'] < latest_nifty['SMA_50'] and latest_nifty['SMA_50'] < latest_nifty['SMA_200']:
        regime = "Bearish"

    live_signals = []
    for ticker in NIFTY_100_TICKERS:
        if ticker in active_tickers:
            continue
            
        try:
            df = yf.download(ticker, period='1y', progress=False)
            if len(df) < 200: continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
            df['SMA_44'] = ta.sma(df['Close'], length=44)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['SMA_200'] = ta.sma(df['Close'], length=200)
            df['Vol_SMA_20'] = ta.sma(df['Volume'], length=20)
            df['ATR_14'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            df.bfill(inplace=True)
            
            in_uptrend = df['Close'] > df['SMA_50']
            rsi_dipped = (df['RSI_14'].shift(1) >= 35) & (df['RSI_14'].shift(1) <= 52)
            rsi_bouncing = df['RSI_14'] > (df['RSI_14'].shift(1) + 2)
            vol_conf = df['Volume'] > df['Vol_SMA_20']
            signal_pullback = in_uptrend & rsi_dipped & rsi_bouncing & vol_conf
            
            major_uptrend = df['Close'].shift(1) > df['SMA_200'].shift(1)
            near_sma44 = (abs(df['Close'].shift(1) - df['SMA_44'].shift(1)) / df['SMA_44'].shift(1)) < 0.03
            bounce = (df['Close'] > df['SMA_44']) & (df['Close'].shift(1) <= (df['SMA_44'].shift(1) * 1.01))
            signal_sma44 = major_uptrend & near_sma44 & bounce
            
            last_row = df.iloc[-1]
            sl_dist = 1.5 * last_row['ATR_14']
            
            if signal_pullback.iloc[-1]:
                live_signals.append({'Ticker': ticker, 'Strategy': 'RSI Pullback', 'LTP': last_row['Close'], 'SL': last_row['Close'] - sl_dist, 'Target': last_row['Close'] + (sl_dist * 2), 'RSI': last_row['RSI_14']})
            elif signal_sma44.iloc[-1]:
                live_signals.append({'Ticker': ticker, 'Strategy': 'SMA44 Pullback', 'LTP': last_row['Close'], 'SL': last_row['Close'] - sl_dist, 'Target': last_row['Close'] + (sl_dist * 2), 'RSI': last_row['RSI_14']})
                
        except Exception as e:
            print(f"Error scanning {ticker}: {e}")

    if not live_signals:
        send_telegram_alert(f"📊 Market Regime: {regime}\nNo new actionable signals today.")
        return {"status": "no signals"}
        
    live_signals.sort(key=lambda x: x['RSI'])
    capital_per_trade = float(portfolio['total_capital']) * 0.10
    
    msg = f"🚨 <b>ACTIONABLE SIGNALS FOR TOMORROW</b> 🚨\n"
    msg += f"📊 <b>Regime:</b> {regime.upper()}\n"
    msg += f"💰 <b>Available Funds:</b> ₹{portfolio['available_capital']:,.2f}\n"
    msg += f"💵 <b>Suggested Pos Size:</b> ₹{capital_per_trade:,.2f}\n\n"
    
    for sig in live_signals:
        suggested_qty = int(capital_per_trade // sig['LTP'])
        msg += f"📈 <b>{sig['Ticker']}</b> ({sig['Strategy']})\n"
        msg += f"Trigger/CMP: ₹{sig['LTP']:.2f} | Suggested Qty: {suggested_qty}\n"
        msg += f"SL: ₹{sig['SL']:.2f} | Target: ₹{sig['Target']:.2f}\n"
        msg += f"RSI: {sig['RSI']:.1f}\n\n"
        
    send_telegram_alert(msg)
    return {"status": "signals_sent", "count": len(live_signals)}
