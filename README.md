# 🚀 Live Options Trading Dashboard  
**Excel + Python + Upstox API (Intraday | Option Buying | Scalping)**

---

## 📌 Project Overview

This project is a **Live Options Trading Dashboard** that allows you to **place real trades directly into your Upstox broker account from Excel**, using a Python backend integrated with the **Upstox API**.

The dashboard provides **real-time account data, live P&L, margin usage, brokerage calculation, and automated trade controls**, enabling fast **option-buying scalping trades** with keyboard-based execution.

📷 **Refer to the dashboard image below for layout and feature understanding:**

<p align="center">
  <img src="Images/Dashboard.png" alt="Live Options Trading Dashboard" width="1000">
</p>

---

## 🎯 Core Objective

- Trade **live options** directly from Excel
- See **actual broker-side P&L instantly**
- Know **true net profit (after brokerage)** immediately
- Avoid over-leveraging by **blocking trades beyond available funds**
- Enable **fast scalping execution** using keyboard shortcuts

---

## 🔗 Broker Integration

- **Broker:** Upstox  
- **Mode:** Live Trading  
- **Integration:** Python + Upstox API  
- **Order Execution:** Real orders placed in broker account  
- **Latency:** Subject to API response time (handled in logic)

---

## 📊 Live Account & Trade Metrics (Real-Time)

The dashboard continuously fetches and displays:

### 💰 Funds & Margin
- Available Funds
- Used Margin
- Maximum Lots allowed (based on funds)
- Auto-block if entered lots exceed permissible limit

### 📈 P&L & Accuracy
- Live Upstox P&L
- Total Brokerage (all trades combined)
- Net Profit (Take-home profit after charges)
- Profit Trades vs Loss Trades
- Trade Accuracy %

➡️ **Key Advantage:**  
You get **final net profit instantly after exit**, without waiting for the contract note.

---

## 🧠 Strategy Scope (Strictly Controlled)

⚠️ **Only the following positions are allowed (by design):**

- ✅ Naked Call Buy (Z + UP)
- ✅ Naked Put Buy (X + UP)
- ✅ Buy Straddle (B + UP)

🚫 Selling strategies are intentionally blocked  
🚫 Complex multi-leg selling is not allowed  

📌 This dashboard is **purely for option buying & scalping**.

---

## ⌨️ Trade Execution Controls

- Entry & Exit are triggered via **keyboard keys**
- No mouse dependency during live market
- Faster reaction during volatile moves

Supported Order Types:
- Buy Breakout Order (BBO)
- Buy Limit Order (BLO)

---

## 🎯 Target & Stop Loss Logic

- Target and Stop Loss must be set **before entry**
- Once trade is entered:
  - ❌ Target cannot be changed
  - ❌ Stop Loss cannot be changed
- Exit is **automatic** on:
  - Target hit
  - Stop Loss hit
  - Manual exit key

📌 Exit follows **real broker execution**, respecting API latency.

---

## 🧮 Brokerage & Margin Transparency

The dashboard includes:
- Per-lot brokerage calculation
- Brokerage for total lots entered
- Real-time brokerage deduction from P&L
- Margin calculator for:
  - Buying
  - (Reference) Selling

➡️ You always know:
> **What you earn is what you take home**

---

## 📍 Trade Intelligence & Context Display

Displayed live on the dashboard:
- Index Spot Price (NIFTY)
- Expiry Date
- DTE (Days to Expiry)
- Manual Strike Entry
- Synthetic ATM Strike Display
- Maximum Lot per Order (exchange constraint)
- RSI / EMA / VWAP logical references (for decision support)

---

## 👁 Visual Trade Representation

- Actual live trade shown with **real P&L**
- A **hypothetical max-lot trade (e.g., 27 lots)** is shown below:
  - For visualization only
  - Helps understand scaling impact
  - Does NOT place real orders

📌 This makes risk and reward **visually obvious** before scaling up.

---

## 🔄 Auto Features (Optional Logic-Based)

The system supports auto-logic modules such as:
- Auto Entry (based on simple indicators)
- Auto Exit (target / SL driven)
- Spike-based entry conditions
- EMA / VWAP contextual confirmations

⚠️ These are intentionally kept **simple and transparent**, not black-box.

---

## 🛡 Safety Mechanisms

- Blocks trade if:
  - Lots entered > allowed by funds
  - Invalid strike or expiry
- Prevents mid-trade modification of SL/Target
- One-direction bias enforcement

---

## 📈 Ideal Use Case

- Intraday option scalping
- High-speed discretionary trading
- Strategy execution discipline
- Capital & risk awareness
- Traders who want **Excel-level control + real execution**

---

## ⚠️ Disclaimer

This is a **live trading system**.  
Losses are possible.  
Use at your own risk.  
This project is intended for **educational and personal trading use only**.

---

## 👤 Author
**Mohit Sharma**  
Live Trading Automation | Options Scalping | Excel + Python Systems

---

🚀 *Trade fast. Trade informed. Trade disciplined.*
