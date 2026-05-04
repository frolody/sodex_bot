import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Intelligence Layer
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY")
    MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/anthropic")
    NVIDIA_MINIMAX_API_KEY = os.getenv("NVIDIA_MINIMAX_API_KEY")
    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    
    # Data Sources
    CRYPTO_PANIC_API_KEY = os.getenv("CRYPTO_PANIC_API_KEY")
    SOSOVALUE_API_KEY = os.getenv("SOSOVALUE_API_KEY")
    
    # Environment
    SODEX_TESTNET = os.getenv("SODEX_TESTNET", "true").lower() == "true"
    SODEX_CHAIN_ID = int(os.getenv("SODEX_CHAIN_ID", "138565"))
    
    # Sodex Core
    SODEX_PRIVATE_KEY = os.getenv("EVM_WALLET_PRIVATE_KEY") if SODEX_TESTNET else os.getenv("SODEX_PRIVATE_KEY")
    SODEX_API_KEY = os.getenv("SODEX_API_KEY") # THE PUBLIC KEY 0x6036...
    SODEX_API_NAME = os.getenv("API_KEY_NAME") # THE LABEL FROLODY_KEY
    SODEX_ACCOUNT_ID = int(os.getenv("SODEX_ACCOUNT_ID", "4739"))
    MASTER_ADDRESS = os.getenv("MASTER_ADDRESS")
    
    BASE_DOMAIN = "testnet-gw.sodex.dev" if SODEX_TESTNET else "mainnet-gw.sodex.dev"
    
    # Trading Logic
    TARGET_SYMBOL = os.getenv("TARGET_SYMBOL", "BTC-USD")
    TRADING_INTERVAL_SECONDS = int(os.getenv("TRADING_INTERVAL_SECONDS", "300"))
    IMPORTANCE_THRESHOLD = int(os.getenv("IMPORTANCE_THRESHOLD", "5"))
    DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "10"))

    @staticmethod
    def validate():
        missing = []
        if not Config.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        if not Config.SODEX_PRIVATE_KEY: missing.append("EVM_WALLET_PRIVATE_KEY (testnet) or SODEX_PRIVATE_KEY (mainnet)")
        if not Config.SODEX_API_NAME: missing.append("API_KEY_NAME")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
