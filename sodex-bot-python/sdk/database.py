import sqlite3
import time
import os

class DatabaseManager:
    def __init__(self, db_path=None):
        if db_path is None:
            # Always use absolute path relative to this file's directory
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(os.path.dirname(base_dir), "trading_data.db")
        else:
            self.db_path = db_path
        self._init_db()

    def _init_db(self):
        print(f"Initializing Database at: {self.db_path}")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for Bot Status & Global Stats
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_stats (
                id INTEGER PRIMARY KEY,
                equity REAL,
                daily_pnl REAL,
                win_rate REAL,
                is_online INTEGER,
                last_update TIMESTAMP
            )
        ''')
        
        # Table for Logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                message TEXT,
                type TEXT
            )
        ''')
        
        # Table for Active Position
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS active_position (
                id INTEGER PRIMARY KEY,
                symbol TEXT,
                side TEXT,
                size REAL,
                entry_price REAL,
                mark_price REAL,
                unrealized_pnl REAL,
                tp_price REAL,
                sl_price REAL,
                leverage INTEGER
            )
        ''')
        
        # Table for Trade History
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP,
                symbol TEXT,
                side TEXT,
                size REAL,
                entry_price REAL,
                exit_price REAL,
                pnl REAL
            )
        ''')
        
        # Table for Bot Config (Multi-user support via wallet_address)
        try:
            cursor.execute("SELECT wallet_address FROM bot_config LIMIT 1")
        except sqlite3.OperationalError:
            # Table doesn't exist OR it's the old schema (no wallet_address column)
            print(">>> DATABASE: Migrating bot_config to new multi-user schema...")
            cursor.execute("DROP TABLE IF EXISTS bot_config")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_config (
                wallet_address TEXT PRIMARY KEY,
                private_key TEXT,
                account_id INTEGER,
                symbol TEXT,
                leverage INTEGER,
                is_active INTEGER DEFAULT 0
            )
        ''')

        # Insert initial stats if empty
        cursor.execute("SELECT COUNT(*) FROM bot_stats")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO bot_stats (id, equity, daily_pnl, win_rate, is_online, last_update) VALUES (1, 0, 0, 0, 1, ?)", (time.time(),))

        conn.commit()
        conn.close()

    def get_config(self, address=None):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Ensure address is a valid string before calling lower()
        if address and isinstance(address, str) and address.strip() != "":
            cursor.execute("SELECT * FROM bot_config WHERE wallet_address = ?", (address.lower(),))
        else:
            # Fallback if no address provided
            cursor.execute("SELECT * FROM bot_config LIMIT 1")
            
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else {}

    def toggle_bot_active(self, address, active):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        val = 1 if active else 0
        cursor.execute("UPDATE bot_config SET is_active = ? WHERE wallet_address = ?", (val, address.lower()))
        conn.commit()
        conn.close()

    def save_config(self, address, private_key, account_id, symbol, leverage):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        address = address.lower()
        
        cursor.execute('''
            INSERT INTO bot_config (wallet_address, private_key, account_id, symbol, leverage)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(wallet_address) DO UPDATE SET
                private_key=excluded.private_key,
                account_id=excluded.account_id,
                symbol=excluded.symbol,
                leverage=excluded.leverage
        ''', (address, private_key, account_id, symbol, leverage))
        
        conn.commit()
        conn.close()

    def add_trade_history(self, symbol, side, size, entry, exit_p, pnl):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO trade_history (timestamp, symbol, side, size, entry_price, exit_price, pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (time.strftime('%Y-%m-%d %H:%M:%S'), symbol, side, size, entry, exit_p, pnl))
        conn.commit()
        conn.close()

    def update_stats(self, equity, daily_pnl, win_rate, is_online=1):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE bot_stats SET 
            equity = ?, daily_pnl = ?, win_rate = ?, is_online = ?, last_update = ?
            WHERE id = 1
        ''', (equity, daily_pnl, win_rate, is_online, time.time()))
        conn.commit()
        conn.close()

    def add_log(self, message, log_type="info"):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO bot_logs (timestamp, message, type) VALUES (?, ?, ?)", 
                       (time.strftime('%H:%M:%S'), message, log_type))
        # Keep only last 50 logs
        cursor.execute("DELETE FROM bot_logs WHERE id IN (SELECT id FROM bot_logs ORDER BY id DESC LIMIT -1 OFFSET 50)")
        conn.commit()
        conn.close()

    def update_position(self, symbol, side, size, entry, mark, pnl, tp=0, sl=0, leverage=15):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM active_position") # Only one active position for now
        if size != 0:
            cursor.execute('''
                INSERT INTO active_position (id, symbol, side, size, entry_price, mark_price, unrealized_pnl, tp_price, sl_price, leverage)
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (symbol, side, size, entry, mark, pnl, tp, sl, leverage))
        conn.commit()
        conn.close()
