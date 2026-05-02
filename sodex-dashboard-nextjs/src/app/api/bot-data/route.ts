import { NextResponse } from 'next/server';
import sqlite3 from 'sqlite3';
import { open } from 'sqlite';
import path from 'path';

export async function GET() {
  try {
    // Robust Absolute Path
    const dbPath = 'D:/PROJECT/Pribadi/SODEX Trading Bot/sodex-bot-python/trading_data.db';
    
    // Check if DB exists
    const fs = require('fs');
    if (!fs.existsSync(dbPath)) {
      return NextResponse.json({ 
        success: false, 
        error: "Database not found. Please start the Python Bot first." 
      }, { status: 503 });
    }

    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database,
    });

    const stats = await db.get('SELECT * FROM bot_stats WHERE id = 1');
    const logs = await db.all('SELECT * FROM bot_logs ORDER BY id DESC LIMIT 50');
    const position = await db.get('SELECT * FROM active_position WHERE id = 1');
    const history = await db.all('SELECT * FROM trade_history ORDER BY id DESC LIMIT 20');
    const config = await db.get('SELECT * FROM bot_config WHERE id = 1');

    await db.close();

    return NextResponse.json({
      success: true,
      data: {
        stats,
        logs,
        position,
        history,
        config
      }
    });
  } catch (error: any) {
    console.error('Database Error:', error);
    return NextResponse.json({ 
      success: false, 
      error: error.message 
    }, { status: 500 });
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { private_key, account_id, symbol, leverage } = body;
    const dbPath = 'D:/PROJECT/Pribadi/SODEX Trading Bot/sodex-bot-python/trading_data.db';

    const db = await open({
      filename: dbPath,
      driver: sqlite3.Database,
    });

    await db.run(
      'UPDATE bot_config SET private_key = ?, account_id = ?, symbol = ?, leverage = ? WHERE id = 1',
      [private_key, account_id, symbol, leverage]
    );

    await db.close();

    return NextResponse.json({ success: true, message: "Configuration updated successfully" });
  } catch (error: any) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}

