'use client';
import React, { useEffect, useRef, useState } from 'react';

interface TradingChartProps {
  data: any[];
  symbol: string;
}

const TradingChart: React.FC<TradingChartProps> = ({ data, symbol }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const seriesRef = useRef<any>(null);
  const [libLoaded, setLibLoaded] = useState(false);

  useEffect(() => {
    // LOCKING TO STABLE VERSION 3.8.0 to ensure addCandlestickSeries works
    if ((window as any).LightweightCharts) {
      setLibLoaded(true);
      return;
    }

    const script = document.createElement('script');
    script.src = 'https://unpkg.com/lightweight-charts@3.8.0/dist/lightweight-charts.standalone.production.js';
    script.async = true;
    script.onload = () => {
      setLibLoaded(true);
    };
    script.onerror = () => console.error("Failed to load chart library");
    document.head.appendChild(script);
  }, []);

  useEffect(() => {
    if (!libLoaded || !chartContainerRef.current) return;

    const LW = (window as any).LightweightCharts;
    if (!LW) return;

    try {
      const chart = LW.createChart(chartContainerRef.current, {
        layout: {
          backgroundColor: 'transparent',
          textColor: '#94a3b8',
        },
        grid: {
          vertLines: { color: 'rgba(30, 41, 59, 0.1)' },
          horzLines: { color: 'rgba(30, 41, 59, 0.1)' },
        },
        width: chartContainerRef.current.clientWidth,
        height: 350,
        timeScale: {
          borderColor: '#334155',
          timeVisible: true,
        },
      });

      // In v3.8.0, this method is GUARANTEED to exist
      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#22c55e',
        downColor: '#ef4444',
        borderVisible: false,
        wickUpColor: '#22c55e',
        wickDownColor: '#ef4444',
        // Dynamic price formatting
        priceFormat: {
          type: 'price',
          precision: 6,
          minMove: 0.000001,
        },
      });

      chartRef.current = chart;
      seriesRef.current = candlestickSeries;
      
      // Ensure the price scale is visible and auto-scales
      chart.priceScale('right').applyOptions({
        autoScale: true,
        borderVisible: false,
      });

      const handleResize = () => {
        if (chartContainerRef.current && chartRef.current) {
          chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
        }
      };

      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        chart.remove();
      };
    } catch (err) {
      console.error("Chart Init Error:", err);
    }
  }, [libLoaded]);

  useEffect(() => {
    if (seriesRef.current && data && Array.isArray(data) && data.length > 0) {
      try {
        const formattedData = data
          .map((d: any) => {
            // Handle both lowercase and uppercase keys just in case
            const time = (d.t || d.T || d.time);
            const open = parseFloat(d.o || d.O || d.open);
            const high = parseFloat(d.h || d.H || d.high);
            const low = parseFloat(d.l || d.L || d.low);
            const close = parseFloat(d.c || d.C || d.close);

            // Validation: Only include points where all values are valid numbers
            if (!time || isNaN(open) || isNaN(high) || isNaN(low) || isNaN(close)) {
              return null;
            }

            return {
              time: time / 1000,
              open, high, low, close
            };
          })
          .filter((item: any) => item !== null) // Remove invalid points
          .sort((a, b) => a.time - b.time);

        // Remove duplicate timestamps (required by lightweight-charts)
        const uniqueData = formattedData.filter((item, index, self) =>
          index === self.findIndex((t) => t.time === item.time)
        );

        if (uniqueData.length > 0) {
          console.log(`CHART [${symbol}]: Rendering ${uniqueData.length} valid candles.`);
          // Log first and last price to see if they differ
          console.log(`CHART [${symbol}]: First Close: ${uniqueData[0].close}, Last Close: ${uniqueData[uniqueData.length-1].close}`);
          
          seriesRef.current.setData(uniqueData);
          
          // AUTO-FIT: This makes the candles fill the screen and scale correctly
          chartRef.current.timeScale().fitContent();
        } else {
          console.warn(`CHART [${symbol}]: No valid data points to render.`);
        }
      } catch (e) {
        console.error("Data mapping error:", e);
      }
    }
  }, [data, libLoaded]);

  return (
    <div className="relative w-full h-[350px] bg-black/40 border border-slate-800 neobrutal-card overflow-hidden">
      {!libLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/20 z-20">
          <div className="w-6 h-6 border-2 border-accent border-t-transparent rounded-full animate-spin"></div>
        </div>
      )}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <span className="bg-accent text-black px-2 py-0.5 text-[10px] font-black uppercase italic">{symbol}</span>
        <span className="text-slate-500 text-[10px] font-bold uppercase tracking-widest">Live Execution View</span>
      </div>
      <div ref={chartContainerRef} className="w-full h-full" />
    </div>
  );
};

export default TradingChart;
