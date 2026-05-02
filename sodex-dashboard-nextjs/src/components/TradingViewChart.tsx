"use client";
import React, { useEffect, useRef } from 'react';

export default function TradingViewChart({ symbol = "BINANCE:BTCUSDT" }) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    
    // Check if script already exists to avoid duplication
    if (container.current.querySelector('script')) return;

    const script = document.createElement("script");
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.type = "text/javascript";
    script.async = true;
    script.innerHTML = JSON.stringify({
      "autosize": true,
      "symbol": symbol,
      "interval": "15",
      "timezone": "Etc/UTC",
      "theme": "dark",
      "style": "1",
      "locale": "en",
      "enable_publishing": false,
      "allow_symbol_change": true,
      "calendar": false,
      "support_host": "https://www.tradingview.com",
      "backgroundColor": "rgba(2, 6, 23, 1)",
      "gridColor": "rgba(30, 41, 59, 0.1)",
      "hide_top_toolbar": true,
      "container_id": "tradingview_chart"
    });
    
    container.current.appendChild(script);
  }, [symbol]);

  return (
    <div className="tradingview-widget-container h-full w-full" ref={container} style={{ minHeight: "350px" }}>
      <div className="tradingview-widget-container__widget h-full w-full" id="tradingview_chart"></div>
    </div>
  );
}
