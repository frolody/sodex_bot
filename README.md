# SoDEX AI: Autonomous Intelligence Trading Bot & Dashboard 🚀🤖

**SoDEX AI** is a state-of-the-art autonomous intelligence layer designed for high-performance trading on the **SoDEX Protocol** (ValueChain Testnet). It bridges the gap between institutional "Smart Money" flows, macro-market intelligence, and technical analysis to execute precision perpetual trades.

> [!IMPORTANT]
> SoDEX AI is currently operating in a **Testnet Environment** (ValueChain). The system is fully functional for testing and development purposes but has not yet been integrated into the SoDEX Mainnet. Use testnet assets only.

---

## 🌟 What it does
SoDEX AI provides a real-time command center where AI agents analyze multiple data streams to generate actionable trading signals:
- **Institutional Analytics**: Powered by **SoSoValue API**, tracking real-time **ETF net inflows/outflows** to align with big-money institutional moves.
- **Strategy Engine V2**: A sophisticated two-stage pipeline. First, a **Rule-Based Engine** calculates technical indicators (RSI, EMA, Volume) and institutional data. Second, a **Gemini-powered AI Validator** cross-references these signals against macro context for final execution.
- **Macro Intelligence**: Aggregates comprehensive market intelligence and token-specific fundamental data to provide deep context for every trade.
- **Cinematic Dashboard**: A high-performance UI built with Next.js and Lightweight Charts, featuring volume-prioritized asset views synchronized with real-time market data.

---

## 🏗️ Architecture
The project is architected as a decoupled system for maximum scalability:

### 1. 🐍 Backend (sodex-bot-python)
The "Brain" handles:
- **Rule-Based Analysis**: Processing real-time klines and institutional flows.
- **AI Validation**: Leveraging Google Gemini for deep signal verification.
- **Market Intel**: Managing SoSoValue and Macro intelligence aggregation.
- **EIP-712 Signatures**: Securely managing signatures for ValueChain testnet execution.

### 2. ⚛️ Frontend (sodex-dashboard-nextjs)
The "Command Center" handles:
- **Interactive Visualization**: Real-time candle charts and volume analytics.
- **AI Reasoning View**: Deep transparency into the bot's decision-making process.
- **Wallet Connection**: Integrated with Wagmi/Viem for secure autonomous execution.

---

## 🚀 Roadmap

### **Wave 1: Core Infrastructure & Strategy V2 (Current)**
*   **Backend Engine**: High-performance Python backend with parallel multi-user execution.
*   **Strategy V2**: Hybrid Two-Stage Analysis (Rule-Based + AI Validation) with Smart Money (ETF) mode.
*   **Data Integration**: Successful integration with SoSoValue API for institutional flow tracking.
*   **Dashboard**: Real-time market visualization and AI reasoning interface.

### **Wave 2: Analytics & Performance Stability (Next)**
*   **Trade History & PnL Tracker**: Comprehensive trade logging and visual performance metrics.
*   **AI Logic Optimization**: Refining decision-making speed and dynamic risk management (ATR-based TP/SL).
*   **System Hardening**: Enhancing connection resilience and database synchronization.

### **Wave 3: Ecosystem Expansion & Final Polish (Future)**
*   **Spot Trading Support**: Expanding support from Perpetuals to Spot Trading.
*   **Mobile Optimization**: Full UI/UX polish for a premium mobile-responsive experience.
*   **Community Release**: Public deployment for the wider SoDEX ecosystem.

---

## 🛠 Tech Stack
- **Languages**: Python, TypeScript
- **Frameworks**: FastAPI, Next.js 15, Tailwind CSS 4
- **AI Models**: Google Gemini 1.5 (Primary Validator)
- **Data APIs**: SoDEX Klines, SoSoValue (Institutional Flows)
- **UI**: Lightweight Charts (TradingView), Lucide Icons

---

## 🏆 Hackathon Submission
This project is submitted for the **SoDEX X Akindo Wave Hacks Campaign**.

**Developer**: Frolody (Solo Developer)
**Project Status**: Functional Prototype (Wave 1 Complete)

---

## 📜 License
MIT License. Created with ❤️ for the SoDEX Community.
