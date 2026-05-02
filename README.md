# SoDEX AI: Autonomous Intelligence Trading Bot & Dashboard 🚀🤖

**SoDEX AI** is a state-of-the-art autonomous trading agent and real-time intelligence dashboard built specifically for the **SoDEX Protocol** on the **ValueChain Testnet**. It bridges the gap between complex market sentiment and decentralized perpetual trading by utilizing a hybrid ensemble of Large Language Models (LLMs).

---

## 🌟 Key Features

- **Hybrid AI Decision Engine**: Uses a two-stage analysis pipeline (Gemini + OpenRouter/Llama/Gemma) to filter noise and generate high-confidence trade signals.
- **Real-Time News Intelligence**: Aggregates and analyzes market-moving news via **CryptoPanic API** to stay ahead of volatility.
- **Cinematic Trading Dashboard**: A high-performance, Neobrutalist UI built with Next.js and Lightweight Charts for real-time market visualization.
- **Autonomous & Manual Modes**: Toggle between a fully automated trading bot and a manual "One-Click" execution mode based on AI suggestions.
- **Dynamic Price Scaling**: Hardened candlestick charting with auto-fit content and precision price formatting for various perpetual assets.

---

## 🏗️ Architecture

The project is architected as a decoupled system for maximum scalability:

### 1. 🐍 Backend (sodex-bot-python)
The "Brain" of the operation. Written in Python, it handles:
- Real-time data fetching from SoDEX API.
- News aggregation and sentiment scoring.
- EIP-712 signature management for secure trade execution.
- FastAPI server providing real-time analytics to the frontend.

### 2. ⚛️ Frontend (sodex-dashboard-nextjs)
The "Command Center". Built with Next.js 15, it features:
- **Interactive Charts**: Real-time kline visualization.
- **AI Reasoning View**: Deep insights into *why* the bot made a decision.
- **Wallet Integration**: Secure connection via Wagmi & Viem.
- **Autonomous Monitoring UI**: Real-time status tracking for the trading agent.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 18+
- [CryptoPanic API Key](https://cryptopanic.com/developers/api/)
- [Google Gemini API Key](https://aistudio.google.com/)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/frolody/sodex_bot.git
   cd sodex_bot
   ```

2. **Setup Backend**
   ```bash
   cd sodex-bot-python
   pip install -r requirements.txt
   cp .env.example .env
   # Edit .env with your keys
   python api.py
   ```

3. **Setup Frontend**
   ```bash
   cd ../sodex-dashboard-nextjs
   npm install
   cp .env.example .env
   # Edit .env with your NEXT_PUBLIC keys
   npm run dev
   ```

---

## 🛠 Tech Stack

- **Languages**: Python, TypeScript
- **Frameworks**: FastAPI, Next.js 15, Tailwind CSS 4
- **Blockchain**: ValueChain, Viem, Wagmi, Ethers
- **AI Models**: Google Gemini 1.5, Llama 3.3, Gemma 2, MiniMax M2.7
- **Data**: SoDEX Klines API, CryptoPanic News API
- **UI**: Lucide Icons, Lightweight Charts (TradingView)

---

## 🏆 Hackathon Submission
This project is submitted for the **SoDEX X Akindo Wave Hacks Campaign**.

**Developer**: [Your Name/Handle] (Solo Developer)
**Project Status**: Functional Prototype (Wave 1)

---

## 📜 License
MIT License. Created with ❤️ for the SoDEX Community.
