import asyncio
from config import Config
from sdk.client import SodexClient
from agents.strategy_engine import StrategyEngine
from agents.news_aggregator import NewsAggregator

def test_analysis():
    Config.validate()
    client = SodexClient()
    news_agg = NewsAggregator()
    engine = StrategyEngine()

    symbol = 'BTC-USD'
    p = client.get_mark_price(symbol)
    if p:
        klines = client.get_klines(symbol, '15m', 20)
        news = news_agg.fetch_latest_news(symbol)
        news_str = '\n'.join([f"- {n['title']}" for n in news]) if news else 'No news'
        
        res = engine.ensemble_analyze(symbol, p, 'OPEN', news_str, klines)
        print('Decision:', res)
        
        tr_sum = sum([float(k.get('h', 0)) - float(k.get('l', 0)) for k in klines])
        atr = tr_sum / len(klines) if klines else 250.0
        print('Price:', p)
        print('ATR:', atr)
    else:
        print('Failed to get price')

if __name__ == "__main__":
    test_analysis()
