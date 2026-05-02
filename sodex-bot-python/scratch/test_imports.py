print("Testing imports...")
from config import Config
print("Config OK")
from sdk.client import SodexClient
print("SodexClient OK")
from agents.news_aggregator import NewsAggregator
print("NewsAggregator OK")
from agents.strategy_engine import StrategyEngine
print("StrategyEngine OK")
from sdk.database import DatabaseManager
print("DatabaseManager OK")
from sdk.autonomous_bot import AutonomousBot
print("AutonomousBot OK")
print("All imports successful!")
