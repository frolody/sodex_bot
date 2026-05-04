import json
import requests
from google import genai
from config import Config
from agents.prompts import (
    GEMINI_FILTER_PROMPT, 
    MINIMAX_DECISION_PROMPT
)
from sdk.database import DatabaseManager

class StrategyEngine:
    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        self.custom_keys = {}
        # Gemini setup (Stage 1: Sentiment Filter)
        if Config.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
            self.gemini_model_id = "gemini-3.1-flash-lite-preview"
        
        self.minimax_api_key = Config.MINIMAX_API_KEY
        self.minimax_base_url = Config.MINIMAX_BASE_URL

    def _parse_json(self, text):
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
        except:
            pass
        return None

    def _format_chart_context(self, klines):
        if not klines or not isinstance(klines, list):
            return "No chart data available."
        lines = ["Time (UTC), O, H, L, C, V"]
        for k in klines[-15:]: 
            if isinstance(k, list):
                ts, o, h, l, c, v = k[0], k[1], k[2], k[3], k[4], k[5]
            else:
                ts, o, h, l, c, v = k.get('t'), k.get('o'), k.get('h'), k.get('l'), k.get('c'), k.get('v')
            lines.append(f"{ts}, {o}, {h}, {l}, {c}, {v}")
        return "\n".join(lines)

    def _call_openrouter(self, system_msg, user_prompt, model_ids):
        """Generic helper for OpenRouter API calls with automatic model rotation."""
        api_key = self.custom_keys.get("openrouter_api_key") or Config.OPENROUTER_API_KEY
        if not api_key: return None
        
        if isinstance(model_ids, str):
            model_ids = [model_ids]
            
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://sodex.dev",
            "X-Title": "SoDEX Trading Bot",
            "Content-Type": "application/json"
        }
        
        for model_id in model_ids:
            messages = []
            if "google" in model_id or "gemma" in model_id:
                messages = [{"role": "user", "content": f"SYSTEM INSTRUCTION:\n{system_msg}\n\nUSER PROMPT:\n{user_prompt}"}]
            else:
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ]

            payload = {"model": model_id, "messages": messages, "temperature": 0.1}
            
            try:
                print(f"Trying OpenRouter Model: {model_id}...")
                # Shortened timeout: 5s to connect, 15s to wait for response
                response = requests.post(url, json=payload, headers=headers, timeout=(5, 15))
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"].get("content", "")
                    if content: return content, model_id
                elif response.status_code == 429:
                    print(f"Model {model_id} is rate-limited (429). Trying next...")
                else:
                    print(f"OpenRouter Error {response.status_code} for {model_id}")
            except: pass
        
        return None, None

    def ensemble_analyze(self, symbol, price, market_status, news_content, klines=None, market_intel=None, risk_profile="SAFETY", balance="100", custom_keys=None):
        self.custom_keys = custom_keys or {}
        chart_str = self._format_chart_context(klines)
        
        # Format Market Intel
        intel_str = "No institutional data available."
        if market_intel:
            etf = market_intel.get("etf")
            ind = market_intel.get("indicators", {})
            etf_str = f"Net Inflow: ${etf['net_inflow']:,.2f}" if etf else "N/A"
            fear_greed = ind.get("fear_greed", {}).get("value", "N/A")
            intel_str = f"ETF FLOWS: {etf_str}\nFEAR & GREED INDEX: {fear_greed}"

        combined_context = f"NEWS:\n{news_content}\n\nINSTITUTIONAL DATA:\n{intel_str}"
        filter_user_prompt = f"TARGET: {symbol}\n{combined_context}\nCHART:\n{chart_str}"
        filter_system_prompt = GEMINI_FILTER_PROMPT.format(
            symbol=symbol, price=price, chart_context=chart_str, news_content=combined_context
        )
        
        # STAGE 1: HYBRID SENTIMENT ANALYSIS (Gemini Primary)
        filter_result = None
        gemini_key = self.custom_keys.get("gemini_api_key") or Config.GEMINI_API_KEY
        
        if gemini_key:
            try:
                # Use User-Specific Key if provided
                client = genai.Client(api_key=gemini_key) if gemini_key != Config.GEMINI_API_KEY else self.gemini_client
                response = client.models.generate_content(
                    model=self.gemini_model_id,
                    contents=filter_user_prompt,
                    config={"system_instruction": filter_system_prompt}
                )
                filter_result = self._parse_json(response.text)
                if filter_result:
                    filter_result["model_name"] = self.gemini_model_id
                    print(f"Hybrid Analysis (Gemini): Trend={filter_result.get('trend_direction')}, Score={filter_result.get('impact_score')}/10")
            except Exception as e:
                print(f"Gemini Stage 1 Error: {e}")

        # Fallback to OpenRouter for Stage 1 if Gemini fails
        if not filter_result:
            print("--- STAGE 1 FALLBACK: OpenRouter ---")
            news_models = ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-12b-it:free"]
            raw_text, model_id = self._call_openrouter(filter_system_prompt, filter_user_prompt, news_models)
            if raw_text:
                filter_result = self._parse_json(raw_text)
                if filter_result: filter_result["model_name"] = model_id

        if not filter_result:
            filter_result = {"trend_direction": "NEUTRAL", "impact_score": 5}

        # STAGE 2: FINAL DECISION (OpenRouter / Minimax)
        risk_instruction = f"MANDATORY RISK PROFILE: {risk_profile}. "
        if risk_profile == "AGGRESSIVE":
            risk_instruction += "Use 10x-25x leverage, target 5-10% profit. Be bold."
        elif risk_profile == "MODERATE":
            risk_instruction += "Use 5x-10x leverage, target 2-4% profit."
        else:
            risk_instruction += "Use 1x-5x leverage, target 1% profit. Prioritize survival."

        decision_system_prompt = risk_instruction + "\n" + MINIMAX_DECISION_PROMPT.format(
            symbol=symbol, price=price, balance=balance, market_status=market_status,
            chart_context=chart_str, filtered_signal=json.dumps(filter_result)
        )
        decision_user_prompt = f"Analyze all data and finalize {symbol} execution plan. Result must be JSON."

        final_result = None
        # 1. TRY MINIMAX (Optional)
        if self.minimax_api_key:
            try:
                url = f"{self.minimax_base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {self.minimax_api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "abab6.5s-chat",
                    "messages": [{"role": "system", "content": decision_system_prompt}, {"role": "user", "content": decision_user_prompt}],
                    "temperature": 0.05
                }
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    final_result = self._parse_json(content)
                    if final_result: final_result["analysis_model"] = "minimax-abab6.5s"
            except: pass

        # 2. FINAL FALLBACK: OPENROUTER
        if not final_result:
            print("--- STAGE 2: Calling OpenRouter Decision Queue ---")
            decision_models = [
                "meta-llama/llama-3.3-70b-instruct:free", 
                "google/gemma-3-12b-it:free",
                "qwen/qwen3-next-80b-a3b-instruct:free"
            ]
            raw_text, model_id = self._call_openrouter(decision_system_prompt, decision_user_prompt, decision_models)
            if raw_text:
                final_result = self._parse_json(raw_text)
                if final_result: final_result["analysis_model"] = model_id

        # 3. GEMINI EMERGENCY FALLBACK (Ensures Reasoning is NEVER Empty)
        if not final_result and gemini_key:
            try:
                print("--- STAGE 2 EMERGENCY: Gemini Fallback for Decision ---")
                client = genai.Client(api_key=gemini_key) if gemini_key != Config.GEMINI_API_KEY else self.gemini_client
                resp = client.models.generate_content(
                    model=self.gemini_model_id,
                    contents=f"{decision_system_prompt}\n\n{decision_user_prompt}",
                    config={"temperature": 0.1, "response_mime_type": "application/json"}
                )
                final_result = self._parse_json(resp.text)
                if final_result: final_result["analysis_model"] = f"{self.gemini_model_id} (fallback)"
            except: pass

        if not final_result:
            # Final Technical Fallback
            final_result = self._technical_fallback(symbol, price, klines, filter_result, risk_profile)

        return {
            "symbol": symbol, "current_price": price, "analysis": final_result,
            "sentiment": filter_result, "sentiment_score": filter_result.get("impact_score"), "risk_profile": risk_profile
        }

    def _technical_fallback(self, symbol, price, klines, filter_result, risk_profile):
        print("--- FALLBACK: Technical Rules ---")
        decision = "HOLD"
        tech_reason = "Consolidating. No clear trend detected on 5-candle average."
        
        if klines and len(klines) >= 5:
            closes = [float(k[4]) if isinstance(k, list) else float(k.get('c')) for k in klines[-5:]]
            avg = sum(closes) / len(closes)
            curr = float(price)
            if curr > avg * 1.002: 
                decision = "LONG"
                tech_reason = f"Price (${curr}) is trending above 5-period average (${avg:.2f}). Bullish momentum."
            elif curr < avg * 0.998: 
                decision = "SHORT"
                tech_reason = f"Price (${curr}) is trending below 5-period average (${avg:.2f}). Bearish pressure."
        
        # Prepare full structure that frontend expects
        return {
            "decision": decision,
            "reasoning": "Technical indicator fallback (AIs offline).",
            "fundamental_analysis": "AI Analysis currently unavailable. News sentiment appears " + filter_result.get("trend_direction", "NEUTRAL"),
            "technical_analysis": tech_reason,
            "params": {
                "leverage": 5 if risk_profile == "SAFETY" else 10,
                "margin_percent": 10,
                "tp_price": str(float(price) * 1.02) if decision == "LONG" else str(float(price) * 0.98),
                "sl_price": str(float(price) * 0.99) if decision == "LONG" else str(float(price) * 1.01)
            }
        }
