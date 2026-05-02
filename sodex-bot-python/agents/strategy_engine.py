import json
from google import genai
import anthropic
from config import Config
from agents.prompts import (
    GEMINI_FILTER_PROMPT, 
    MINIMAX_DECISION_PROMPT
)

from sdk.database import DatabaseManager

class StrategyEngine:
    def __init__(self, db: DatabaseManager = None):
        self.db = db or DatabaseManager()
        # Gemini setup (News Filter) using the NEW google-genai SDK
        if Config.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=Config.GEMINI_API_KEY)
            self.gemini_model_id = "gemini-3.1-flash-lite-preview"
        
        # MiniMax setup (Decision Maker)
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
        if not Config.OPENROUTER_API_KEY:
            return None
        
        if isinstance(model_ids, str):
            model_ids = [model_ids]
            
        import requests
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://sodex.dev",
            "X-Title": "SoDEX Trading Bot",
            "Content-Type": "application/json"
        }
        
        for model_id in model_ids:
            # Fix for models like Gemma 3 that may not support 'system' role
            messages = []
            if "google" in model_id or "gemma" in model_id:
                messages = [{"role": "user", "content": f"SYSTEM INSTRUCTION:\n{system_msg}\n\nUSER PROMPT:\n{user_prompt}"}]
            else:
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt}
                ]

            payload = {
                "model": model_id,
                "messages": messages,
                "temperature": 0.1
            }
            
            try:
                print(f"Trying OpenRouter Model: {model_id}...")
                response = requests.post(url, json=payload, headers=headers, timeout=45)
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"].get("content", "")
                    return content, model_id # Return both content and the successful model ID
                elif response.status_code == 429:
                    print(f"Model {model_id} is rate-limited (429). Trying next in queue...")
                    continue
                else:
                    print(f"OpenRouter Error {response.status_code} for {model_id}: {response.text}")
            except Exception as e:
                print(f"OpenRouter Network Error for {model_id}: {e}")
        
        return None, None

    def ensemble_analyze(self, symbol, price, market_status, news_content, klines=None):
        chart_str = self._format_chart_context(klines)
        filter_user_prompt = f"TARGET: {symbol}\nNEWS:\n{news_content}\nCHART:\n{chart_str}"
        filter_system_prompt = GEMINI_FILTER_PROMPT.format(
            symbol=symbol, price=price, chart_context=chart_str, news_content=news_content
        )
        
        filter_result = None
        # 1. TRY GEMINI
        if hasattr(self, 'gemini_client'):
            try:
                response = self.gemini_client.models.generate_content(
                    model=self.gemini_model_id,
                    contents=filter_user_prompt,
                    config={"system_instruction": filter_system_prompt}
                )
                filter_result = self._parse_json(response.text)
                if filter_result:
                    filter_result["model_name"] = self.gemini_model_id
                    print(f"Hybrid Analysis (Gemini): Score={filter_result.get('impact_score')}/10")
            except Exception as e:
                print(f"Gemini Error ({str(e)[:50]}...). Trying OpenRouter Fallback...")

        # 2. FALLBACK TO OPENROUTER (Rotation of Free Models)
        if not filter_result:
            print("--- STAGE 1 FALLBACK: Calling OpenRouter Model Queue ---")
            news_models = ["google/gemma-3-4b-it:free", "google/gemma-3-12b-it:free"]
            raw_text, model_id = self._call_openrouter(filter_system_prompt, filter_user_prompt, news_models)
            if raw_text:
                filter_result = self._parse_json(raw_text)
                if filter_result:
                    filter_result["model_name"] = model_id
                    print(f"Hybrid Analysis (OpenRouter Fallback): Score={filter_result.get('impact_score')}/10 using {model_id}")

        if not filter_result:
            return {"decision": "HOLD", "reasoning": "News analysis unavailable (All AI engines failed).", "model_name": "None"}

        impact_score = filter_result.get("impact_score", 0)
        if impact_score >= Config.IMPORTANCE_THRESHOLD:
            return self._call_minimax_decision(symbol, price, market_status, filter_result, chart_str, klines)
        
        return {
            "decision": "HOLD", 
            "reasoning": f"Signal score ({impact_score}) below threshold.",
            "model_name": filter_result.get("model_name", self.gemini_model_id)
        }

    def _call_minimax_decision(self, symbol, price, market_status, filtered_signal, chart_str, klines):
        system_msg = MINIMAX_DECISION_PROMPT.format(
            symbol=symbol, price=price, market_status=market_status, 
            filtered_signal=json.dumps(filtered_signal), chart_context=chart_str
        )
        user_prompt = f"Signal: {json.dumps(filtered_signal)}\nHistory:\n{chart_str}"

        # 1. TRY NVIDIA MINIMAX
        if Config.NVIDIA_MINIMAX_API_KEY:
            try:
                import requests
                url = f"{Config.NVIDIA_BASE_URL}/chat/completions"
                headers = {"Authorization": f"Bearer {Config.NVIDIA_MINIMAX_API_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "minimaxai/minimax-m2.7",
                    "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": user_prompt}],
                    "temperature": 0.1, "max_tokens": 1024
                }
                response = requests.post(url, json=payload, headers=headers, timeout=60)
                if response.status_code == 200:
                    text = response.json()["choices"][0]["message"].get("content", "")
                    res = self._parse_json(text)
                    if res: 
                        res["model_name"] = "minimaxai/minimax-m2.7"
                        return res
            except: pass

        # 2. FALLBACK TO OPENROUTER (Rotation of State-of-the-Art Free Models)
        print("--- STAGE 2 FALLBACK: Calling OpenRouter Decision Queue ---")
        decision_models = [
            "liquid/lfm-2.5-1.2b-thinking:free",
            "meta-llama/llama-3.3-70b-instruct:free", 
            "google/gemma-3-12b-it:free",
            "qwen/qwen3-next-80b-a3b-instruct:free",
            "minimax/minimax-m2.5:free"
        ]
        raw_text, model_id = self._call_openrouter(system_msg, user_prompt, decision_models)
        if raw_text:
            print(f"DEBUG OPENROUTER RAW TEXT:\n{raw_text}\n" + "="*50)
            res = self._parse_json(raw_text)
            if res: 
                res["model_name"] = model_id
                return res

        # 4. FINAL RULE-BASED FALLBACK
        return self._call_rule_based_fallback(symbol, price, klines)

    def _call_rule_based_fallback(self, symbol, current_price, klines):
        print("--- FINAL FALLBACK: Using Technical Rules ---")
        if not klines or len(klines) < 5:
            return {"decision": "HOLD", "reasoning": "AIs offline and insufficient chart data."}
        try:
            closes = [float(k[4]) if isinstance(k, list) else float(k.get('c')) for k in klines[-5:]]
            avg_price = sum(closes) / len(closes)
            curr = float(current_price)
            if curr > avg_price * 1.002:
                return {"decision": "LONG", "reasoning": "Rules: Price > 5-candle avg.", "params": {"side": 1, "positionSide": 1, "leverage": 10}}
            elif curr < avg_price * 0.998:
                return {"decision": "SHORT", "reasoning": "Rules: Price < 5-candle avg.", "params": {"side": 2, "positionSide": 1, "leverage": 10}}
        except: pass
        return {"decision": "HOLD", "reasoning": "Rules: Sideways market."}
