"use strict";
/**
 * SODEX STABILITY NOTES (DO NOT REMOVE):
 * 1. NONCE SYNC: clOrdID timestamp MUST match X-API-Nonce (use shared 'nonce' variable).
 * 2. KEY ORDER: JSON keys must follow strict sequence for valid signature:
 *    - Main: clOrdID, modifier, side, type, timeInForce, [price], quantity, reduceOnly, positionSide.
 *    - TP/SL: clOrdID, modifier, side, type, timeInForce, quantity, stopPrice, stopType, triggerType, reduceOnly, positionSide.
 * 3. MODIFIERS: Normal=1, Bracket(Parent)=3, AttachedStop(TP/SL)=4.
 * 4. MARKET: Omit 'price' to avoid IOC slippage cancellation.
 */
'use client';

import { useState, useEffect } from 'react';
import dynamic from 'next/dynamic';
import { ConnectButton } from '@rainbow-me/rainbowkit';
import {
  Zap,
  TrendingUp,
  TrendingDown,
  Search,
  BarChart3,
  ShieldCheck,
  BrainCircuit,
  MessageSquareQuote,
  AlertTriangle,
  Wallet,
  History,
  Info,
  ChevronRight,
  LayoutDashboard,
  Settings as SettingsIcon,
  MessageSquare,
  Menu,
  X,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';

const DynamicTradingChart = dynamic(() => import('@/components/TradingChart'), { ssr: false });

import { useAccount, useBalance, useSignTypedData, useChainId, useSwitchChain } from 'wagmi';
import { SODEX_ROUTER_ADDRESS, SODEX_ROUTER_ABI } from './constants';
import { valueChain } from './providers';
import { keccak256, stringToBytes, parseSignature } from 'viem';
import { privateKeyToAccount } from 'viem/accounts';

export default function Dashboard() {
  const { address, isConnected } = useAccount();
  const { data: balance } = useBalance({ address });
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();

  const { signTypedDataAsync, data: signature, isPending: isSigning, isSuccess: isSigned } = useSignTypedData();

  // Custom states for transaction tracking
  const [isExecuting, setIsExecuting] = useState(false);
  const [isConfirmed, setIsConfirmed] = useState(false);
  const [hash, setHash] = useState<string | null>(null);

  // Account Status
  const [isRegistered, setIsRegistered] = useState<boolean | null>(null);
  const [accountInfo, setAccountInfo] = useState<any>(null);
  const [autoTrading, setAutoTrading] = useState(false);
  const [isToggling, setIsToggling] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [symbol, setSymbol] = useState('BTC-USD');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState<any>(null);
  const [activePayload, setActivePayload] = useState<any>(null);
  const [userPrivateKey, setUserPrivateKey] = useState<string>('');
  const [geminiKey, setGeminiKey] = useState<string>('');
  const [openrouterKey, setOpenrouterKey] = useState<string>('');
  const [tradingMode, setTradingMode] = useState<string>('MOMENTUM');
  const [lastAutoLog, setLastAutoLog] = useState<string>('');
  const [showPK, setShowPK] = useState(false);
  // 3. Precise Price Formatter for low-priced tokens
  const formatPrice = (price: any) => {
    if (!price || price === '---' || price === '0') return '---';
    const val = typeof price === 'string' ? parseFloat(price) : price;
    if (isNaN(val)) return price;
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: val < 1 ? 4 : 2,
      maximumFractionDigits: val < 1 ? 8 : 2
    }).format(val);
  };

  const [availableMarkets, setAvailableMarkets] = useState<string[]>([]);
  const [klines, setKlines] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [marketIntel, setMarketIntel] = useState<any>(null);

  // Modal & Trade States
  const [showModal, setShowModal] = useState(false);
  const [execLeverage, setExecLeverage] = useState(10);
  const [marginUSD, setMarginUSD] = useState("10");
  const [execTP, setExecTP] = useState("");
  const [execTPDesc, setExecTPDesc] = useState("");
  const [execSL, setExecSL] = useState("");
  const [execSLDesc, setExecSLDesc] = useState("");
  const [execPrice, setExecPrice] = useState("");
  const [execOrderType, setExecOrderType] = useState(2); // 2 = MARKET, 1 = LIMIT
  const [activeNonce, setActiveNonce] = useState<number>(0);
  const [overrideSide, setOverrideSide] = useState<'LONG' | 'SHORT' | null>(null);
  const [riskProfile, setRiskProfile] = useState<'SAFETY' | 'MODERATE' | 'AGGRESSIVE'>('SAFETY');

  // Fetch Klines on symbol change
  useEffect(() => {
    fetchKlines(symbol);
  }, [symbol]);

  // Check registration on address change or connection
  useEffect(() => {
    fetchMarkets();
    if (isConnected && address) {
      checkRegistration();
      fetchSettings(address);
      
      // Trigger immediately on change
      fetchStats();
      fetchMarketIntel();
      
      // Then start the interval
      const interval = setInterval(() => {
        fetchStats();
        fetchMarketIntel();
      }, 5000);
      return () => clearInterval(interval);
    } else {
      setIsRegistered(null);
      setAccountInfo(null);
      setStats(null); // Clear statistics and positions
    }
  }, [isConnected, address]);

  // 4. Polling for Auto-Trading Logs
  useEffect(() => {
    let interval: any;
    if (autoTrading && address) {
      interval = setInterval(() => {
        fetchSettings(address);
      }, 10000); // Poll every 10s for logs
    }
    return () => clearInterval(interval);
  }, [autoTrading, address]);

  const getBaseUrl = () => {
    if (typeof window !== 'undefined') {
      return `http://${window.location.hostname}:8000`;
    }
    return 'http://localhost:8000';
  };

  const fetchSettings = async (addr: string) => {
    try {
      const resp = await fetch(`${getBaseUrl()}/api/settings?address=${addr}`);
      const data = await resp.json();
      setAutoTrading(data.is_active === 1);
      if (data.private_key) {
        setUserPrivateKey(data.private_key);
      }
      if (data.gemini_api_key) setGeminiKey(data.gemini_api_key);
      if (data.openrouter_api_key) setOpenrouterKey(data.openrouter_api_key);
      if (data.trading_mode) setTradingMode(data.trading_mode);
      if (data.last_auto_log) setLastAutoLog(data.last_auto_log);
    } catch (err) { console.error(err); }
  };

  const fetchStats = async () => {
    try {
      const url = address
        ? `${getBaseUrl()}/api/stats?address=${address}`
        : `${getBaseUrl()}/api/stats`;
      const resp = await fetch(url);
      const data = await resp.json();
      setStats(data);
      
      // Also update accountInfo if data contains it to ensure balance refreshes
      if (data.account_id) {
        setAccountInfo(data);
      }
    } catch (err) { console.error(err); }
  };

  const fetchMarketIntel = async () => {
    try {
      const resp = await fetch(`${getBaseUrl()}/api/market-intelligence?symbol=${symbol}`);
      const data = await resp.json();
      setMarketIntel(data);
    } catch (err) { console.error(err); }
  };

  const fetchMarkets = async () => {
    try {
      const resp = await fetch(`${getBaseUrl()}/api/markets`);
      const data = await resp.json();
      if (data.markets) {
        setAvailableMarkets(data.markets);
      }
    } catch (err) { console.error(err); }
  };

  const fetchKlines = async (sym: string) => {
    setChartLoading(true);
    try {
      const resp = await fetch(`${getBaseUrl()}/api/chart/klines?symbol=${sym}&interval=15m&limit=500`);
      const data = await resp.json();
      if (data.klines) {
        setKlines(data.klines);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setChartLoading(false);
    }
  };

  const saveSettings = async () => {
    if (!address || !userPrivateKey) {
      alert("Address and Private Key are required to save.");
      return;
    }
    try {
      const resp = await fetch(`${getBaseUrl()}/api/settings/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          address: address,
          private_key: userPrivateKey,
          account_id: accountInfo?.account_id,
          symbol: symbol,
          gemini_api_key: geminiKey,
          openrouter_api_key: openrouterKey,
          trading_mode: tradingMode
        })
      });
      const data = await resp.json();
      if (data.status === "success") {
        alert("SETTINGS SAVED: Your Private Key is now persisted for this wallet.");
      }
    } catch (err) { console.error(err); }
  };

  const toggleAutoTrading = async () => {
    if (isToggling || !address) return;
    const newState = !autoTrading;

    // VALIDATION: Check if private key exists before enabling auto
    if (newState && (!userPrivateKey || userPrivateKey.trim() === "")) {
      alert("CRITICAL: EVM Private Key is missing! \n\nPlease enter and SAVE your Private Key in the Session Auth field first.");
      return;
    }

    setIsToggling(true);
    try {
      await fetch(`${getBaseUrl()}/api/settings/toggle?address=${address}&active=${newState}`, { method: 'POST' });
      setAutoTrading(newState);
    } catch (err) {
      console.error(err);
    } finally {
      setIsToggling(false);
    }
  };

  const formatSodexSignature = (sig: string) => {
    if (!sig) return "";
    try {
      // Use viem's parseSignature for reliable R, S, V extraction
      const { r, s, v } = parseSignature(sig as `0x${string}`);

      // Normalize V: SoDEX expects 00 or 01 (instead of 27 or 28)
      const vNormalized = Number(v) >= 27 ? Number(v) - 27 : Number(v);
      const vHex = vNormalized.toString(16).padStart(2, '0');

      // The 0x01 prefix is often required by SoDEX for EIP-712 signatures
      return `0x01${r.slice(2)}${s.slice(2)}${vHex}`;
    } catch (err) {
      console.error("Signature formatting failed:", err);
      return sig; // Fallback to raw signature
    }
  };

  const checkRegistration = async () => {
    try {
      const resp = await fetch(`${getBaseUrl()}/api/check-account?address=${address}`);
      const data = await resp.json();
      setIsRegistered(data.registered);
      setAccountInfo(data);
    } catch (err) {
      console.error("Account check failed:", err);
    }
  };

  const submitTradeWithSig = async (payload: any, signature: string, nonce: number) => {
    try {
      const resp = await fetch(`${getBaseUrl()}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload, signature, nonce })
      });
      const result = await resp.json();
      if (result.code === 0) {
        setIsConfirmed(true);
        setTimeout(() => setIsConfirmed(false), 3000);
      } else {
        alert("Execution Error: " + (result.msg || result.error || "Unknown error"));
      }
    } catch (err) {
      console.error("Submit error:", err);
      alert("Network Error during execution");
    } finally {
      setIsExecuting(false);
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    try {
      const bal = accountInfo?.balance || "100";
      const resp = await fetch(`${getBaseUrl()}/api/analyze?symbol=${symbol}&risk=${riskProfile}&balance=${bal}&address=${address}&mode=${tradingMode}`);
      const data = await resp.json();
      setAnalysis(data);
      
      // Auto-update margin/TP/SL with cleaned values and descriptions
      if (data.analysis?.params?.margin_usd) {
        const rawMargin = data.analysis.params.margin_usd.toString();
        const numMargin = rawMargin.match(/[\d.]+/);
        if (numMargin) setMarginUSD(numMargin[0]);
      }
      if (data.analysis?.params?.tp_price) {
        const rawTP = data.analysis.params.tp_price.toString();
        const numTP = rawTP.match(/[\d.]+/);
        if (numTP) setExecTP(numTP[0]);
        setExecTPDesc(data.analysis.params.tp_desc || "");
      }
      if (data.analysis?.params?.sl_price) {
        const rawSL = data.analysis.params.sl_price.toString();
        const numSL = rawSL.match(/[\d.]+/);
        if (numSL) setExecSL(numSL[0]);
        setExecSLDesc(data.analysis.params.sl_desc || "");
      }
    } catch (err) {
      console.error("Analysis failed:", err);
      alert("Failed to connect to AI backend. Ensure api.py is running on port 8000.");
    } finally {
      setLoading(false);
    }
  };

  const handleExecute = (manualSide?: 'LONG' | 'SHORT') => {
    if (!analysis) return;

    const side = manualSide || (analysis.analysis.decision as 'LONG' | 'SHORT');
    if (side !== 'LONG' && side !== 'SHORT') {
      alert("Please select a side (LONG/SHORT) or wait for AI signal.");
      return;
    }

    setOverrideSide(side);
    setExecLeverage(analysis.analysis.params?.leverage || 10);
    setExecTP(analysis.analysis.params?.tp_price || "");
    setExecPrice(analysis.current_price.toString());
    setExecOrderType(2); // Default to Market for convenience

    setShowModal(true);
  };

  // SODEX AUTH HELPER
  const SodexAuth = {
    signExecuteRequest: async (params: any, type: string, passedNonce?: number) => {
      const nonce = passedNonce || Date.now();
      // FIX: Ensure very strict stringification for hashing
      const payloadJson = JSON.stringify(params).replace(/\s/g, '');
      const payloadHash = keccak256(stringToBytes(`{"type":"${type}","params":${payloadJson}}`));

      const domain = {
        name: 'futures', version: '1', chainId: BigInt(138565),
        verifyingContract: '0x0000000000000000000000000000000000000000' as `0x${string}`,
      };
      const types = {
        ExchangeAction: [{ name: 'payloadHash', type: 'bytes32' }, { name: 'nonce', type: 'uint64' }],
      };
      const message = { payloadHash: payloadHash as `0x${string}`, nonce: BigInt(nonce) };

      let rawSig;
      if (userPrivateKey && userPrivateKey.length >= 64) {
        const pk = userPrivateKey.startsWith('0x') ? userPrivateKey : `0x${userPrivateKey}`;
        const account = privateKeyToAccount(pk as `0x${string}`);
        rawSig = await account.signTypedData({ domain, types, primaryType: 'ExchangeAction', message });
      } else {
        rawSig = await signTypedDataAsync({ domain, types, primaryType: 'ExchangeAction', message });
      }

      return { signature: formatSodexSignature(rawSig), nonce };
    }
  };

  const confirmExecute = async (side: 'LONG' | 'SHORT') => {
    if (!analysis || !accountInfo) return;
    setIsExecuting(true);
    setShowModal(false);
    try {
      const calcQty = (parseFloat(marginUSD) * execLeverage / parseFloat(analysis.current_price)).toFixed(3);
      const payload = {
        address: address,
        account_id: Number(accountInfo.account_id),
        symbol: symbol,
        side: side === 'LONG' ? 1 : 2,
        order_type: execOrderType,
        quantity: calcQty,
        price: execOrderType === 2 ? analysis.current_price.toString() : execPrice,
        leverage: Math.round(execLeverage),
        margin_mode: 2,
        tp_price: execTP,
        sl_price: execSL
      };
      const resp = await fetch(`${getBaseUrl()}/api/trade-unified`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const result = await resp.json();
      if (result.code === 0) { alert(`Successfully executed ${side}!`); fetchStats(); }
      else { alert(`Error: ${result.error || result.msg}`); }
    } catch (err) { alert("Network Error"); } finally { 
      setIsExecuting(false);
      setOverrideSide(null);
    }
  };

  const confirmExecuteClassic = async (side: 'LONG' | 'SHORT') => {
    if (!analysis || !accountInfo) return;
    setIsExecuting(true);
    setShowModal(false);
    try {
      const nonce = Date.now();
      const calcQty = (parseFloat(marginUSD) * execLeverage / parseFloat(analysis.current_price)).toFixed(3);
      const hasBracket = execTP || execSL;
      const calcPrice = execOrderType === 2 ? analysis.current_price.toString() : execPrice;

      const mainOrder: any = {
        clOrdID: `${accountInfo.account_id}-${nonce}`,
        modifier: hasBracket ? 3 : 1,
        side: side === 'LONG' ? 1 : 2,
        type: execOrderType,
        timeInForce: execOrderType === 2 ? 3 : 1
      };

      // Price MUST come before quantity for SoDEX signature
      if (execOrderType !== 2) {
        mainOrder.price = calcPrice;
      }

      mainOrder.quantity = calcQty;
      mainOrder.reduceOnly = false;
      mainOrder.positionSide = 1;

      const orders: any[] = [mainOrder];

      if (execTP) {
        orders.push({
          clOrdID: `${accountInfo.account_id}-${nonce}-tp`,
          modifier: 4, // ATTACHED_STOP (Same as SL for SoDEX)
          side: side === 'LONG' ? 2 : 1,
          type: 2, // MARKET
          timeInForce: 3,
          quantity: calcQty,
          stopPrice: execTP,
          stopType: 2, // TAKE_PROFIT
          triggerType: 2, // MARK_PRICE
          reduceOnly: true,
          positionSide: 1
        });
      }

      if (execSL) {
        orders.push({
          clOrdID: `${accountInfo.account_id}-${nonce}-sl`,
          modifier: 4, // STOP_LOSS
          side: side === 'LONG' ? 2 : 1,
          type: 2, // MARKET
          timeInForce: 3,
          quantity: calcQty,
          stopPrice: execSL,
          stopType: 1, // STOP_LOSS
          triggerType: 2, // MARK_PRICE
          reduceOnly: true,
          positionSide: 1
        });
      }

      const orderPayload = {
        params: {
          accountID: Number(accountInfo.account_id),
          symbolID: symbol === 'BTC-USD' ? 1 : 2,
          orders: orders
        }
      };

      const { signature } = await SodexAuth.signExecuteRequest(orderPayload.params, 'newOrder', nonce);
      const resp = await fetch(`${getBaseUrl()}/api/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ payload: orderPayload, signature, nonce })
      });

      const result = await resp.json();
      if (result.code === 0) { alert(`Classic Success: ${side}`); fetchStats(); }
      else { alert(`Classic Error: ${result.error || result.msg}`); }
    } catch (err) { alert("Classic Failed"); } finally { 
      setIsExecuting(false);
      setOverrideSide(null);
    }
  };

  // --- SECRET DEMO MODE WITH VIRTUAL CURSOR ---
  const [cursorPos, setCursorPos] = useState({ x: -100, y: -100 });
  const [isClicking, setIsClicking] = useState(false);

  const moveCursorTo = async (elementId: string) => {
    const el = document.getElementById(elementId);
    if (el) {
      const rect = el.getBoundingClientRect();
      const x = rect.left + rect.width / 2 + window.scrollX;
      const y = rect.top + rect.height / 2 + window.scrollY;
      setCursorPos({ x, y });
      await new Promise(r => setTimeout(r, 1000)); // Travel time
      setIsClicking(true);
      await new Promise(r => setTimeout(r, 200));
      setIsClicking(false);
    }
  };

  useEffect(() => {
    const handleKeyDown = async (e: KeyboardEvent) => {
      if (e.altKey && e.key === 's') {
        console.log("🎬 CINEMATIC DEMO START!");

        // 1. Move to Token Selector
        await moveCursorTo('token-select');
        setSymbol('BTC-USD');
        await new Promise(r => setTimeout(r, 1500));

        // 2. Move to Analyze Button
        await moveCursorTo('analyze-btn');
        document.getElementById('analyze-btn')?.click();

        // 3. Wait for AI (Let cursor stay near title)
        setCursorPos({ x: 400, y: 300 });
        await new Promise(r => setTimeout(r, 12000));

        // 4. Scroll and move to Auto Toggle
        window.scrollTo({ top: 800, behavior: 'smooth' });
        await new Promise(r => setTimeout(r, 2000));

        // 5. Toggle Auto Trading ON
        await moveCursorTo('auto-trading-toggle');
        setAutoTrading(true);
        await new Promise(r => setTimeout(r, 6000));

        // 6. Toggle Auto Trading OFF (Show Manual Override)
        await moveCursorTo('auto-trading-toggle');
        setAutoTrading(false);
        await new Promise(r => setTimeout(r, 2000));

        // 7. Move to FORCE LONG
        window.scrollTo({ top: 400, behavior: 'smooth' }); // Scroll up a bit to see the buttons
        await new Promise(r => setTimeout(r, 1500));
        await moveCursorTo('force-long-btn');
        // We won't trigger .click() here to avoid accidental transactions during recording, 
        // OR we can trigger it if you're ready to sign in MetaMask.
        console.log("👉 User can now click FORCE LONG or SHORT");

        await new Promise(r => setTimeout(r, 4000));
        setCursorPos({ x: -100, y: -100 }); // Hide cursor
        console.log("✅ EXTENDED CINEMATIC DEMO COMPLETE!");
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [symbol, autoTrading]);

  return (
    <main className="flex-1 p-4 md:p-6 max-w-7xl mx-auto w-full relative">
      {/* VIRTUAL CURSOR */}
      <div
        className={`fixed z-[9999] pointer-events-none transition-all duration-700 ease-in-out bg-accent rounded-full border-2 border-white shadow-[0_0_20px_rgba(249,115,22,0.6)] ${isClicking ? 'scale-75' : 'scale-100'}`}
        style={{
          left: cursorPos.x,
          top: cursorPos.y,
          width: '20px',
          height: '20px',
          opacity: cursorPos.x < 0 ? 0 : 1,
          transform: 'translate(-50%, -50%)'
        }}
      />
      {/* Header with Wallet (Compact) */}
      <header className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-black tracking-tighter mb-1 flex items-center gap-2 italic">
            <Zap className="w-8 h-8 fill-accent text-black" />
            SODEX <span className="text-accent underline decoration-4 decoration-black">AI</span>
          </h1>
          <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Non-Custodial Intelligence</p>
        </div>
        <div className="neobrutal-card p-2 flex items-center gap-4 bg-slate-900/50 border-slate-800 scale-90 origin-right">
          <ConnectButton />
        </div>
      </header>

      {/* Position HUD (Replacement for Table) */}
      <div className="mb-6">
        {stats?.positions && stats.positions.length > 0 ? (
          stats.positions.map((pos: any, idx: number) => (
            <div key={idx} className="neobrutal-card bg-slate-900 border-l-8 border-l-success overflow-hidden animate-in fade-in slide-in-from-top-2 duration-300">
              <div className="flex flex-col md:flex-row items-stretch">
                {/* Left: Asset Info */}
                <div className="bg-black/40 p-4 border-r border-slate-800 flex flex-col justify-center min-w-[140px]">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">LIVE TRADE</span>
                    <div className="w-2 h-2 bg-success rounded-full animate-ping"></div>
                  </div>
                  <h3 className="text-2xl font-black italic text-white tracking-tighter leading-none">{pos.symbol}</h3>
                  <div className="mt-2 flex items-center gap-2">
                    <span className={`text-[9px] font-black px-1.5 py-0.5 ${pos.side === 'LONG' ? 'bg-success text-black' : 'bg-danger text-white'}`}>
                      {pos.side}
                    </span>
                    <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">x{pos.leverage} LEVERAGE</span>
                  </div>
                </div>

                {/* Middle: Live PnL */}
                <div className="flex-1 p-4 flex flex-col justify-center items-center md:items-start border-r border-slate-800 bg-gradient-to-r from-transparent to-success/5">
                  <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">UNREALIZED PNL</span>
                  <div className={`text-4xl font-black italic tracking-tighter ${(parseFloat(pos.unrealized_pnl) || 0) >= 0 ? 'text-success' : 'text-danger'
                    }`}>
                    {(parseFloat(pos.unrealized_pnl) || 0) >= 0 ? '+' : ''}
                    {(parseFloat(pos.unrealized_pnl) || 0).toFixed(2)}
                    <span className="text-sm ml-1 not-italic opacity-50">vUSDC</span>
                  </div>
                </div>

                {/* Right: Price Details Grid */}
                <div className="p-4 bg-black/20 grid grid-cols-2 gap-x-8 gap-y-2 min-w-[300px]">
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase">Entry Price</span>
                    <span className="text-xs font-mono text-white">
                      {pos.entry_price && pos.entry_price !== "0" ? `$${formatPrice(pos.entry_price)}` : '---'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase">Mark Price</span>
                    <span className="text-xs font-mono text-accent animate-pulse">
                      {pos.mark_price && pos.mark_price !== "0" ? `$${formatPrice(pos.mark_price)}` : '---'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase text-success">Take Profit</span>
                    <span className="text-[10px] font-black text-success italic">
                      {pos.tp_price && pos.tp_price !== "---" ? `$${formatPrice(pos.tp_price)}` : 'NOT SET'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase text-danger">Stop Loss</span>
                    <span className="text-[10px] font-black text-danger italic">
                      {pos.sl_price && pos.sl_price !== "---" ? `$${formatPrice(pos.sl_price)}` : 'NOT SET'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase">Initial Margin</span>
                    <span className="text-[10px] font-bold text-accent">
                      {pos.margin && pos.margin !== "0" ? `$${formatPrice(pos.margin)}` : '---'}
                    </span>
                  </div>
                  <div className="flex flex-col">
                    <span className="text-[8px] font-black text-slate-500 uppercase">Last Update</span>
                    <span className="text-[10px] font-bold text-slate-400">{new Date().toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            </div>
          ))
        ) : (
          <div className="neobrutal-card p-2 bg-slate-900/50 border-slate-800 flex items-center justify-between px-4">
            <div className="flex items-center gap-2">
              <div className="w-1.5 h-1.5 bg-slate-700 rounded-full"></div>
              <span className="text-[9px] font-black text-slate-600 uppercase tracking-[0.3em]">PORTFOLIO STATUS: FLAT</span>
            </div>
            <span className="text-[8px] font-bold text-slate-700 uppercase italic">Waiting for AI Momentum...</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">

        {/* Left Column: Asset Selection & Controls */}
        <div className="lg:col-span-4 space-y-4">
          <section className="neobrutal-card p-4 bg-slate-900 border-slate-800">
            <h2 className="text-sm font-black mb-4 flex items-center gap-2 uppercase tracking-widest">
              <Search className="w-4 h-4 text-accent" /> ASSET
            </h2>

            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 bg-black border border-slate-800">
                <div className="flex items-center gap-2">
                  <BrainCircuit className={`w-4 h-4 ${autoTrading ? 'text-accent animate-pulse' : 'text-slate-600'}`} />
                  <div>
                    <span className="block text-[10px] font-black text-white leading-none uppercase">AUTO-TRADING</span>
                    <span className={`text-[9px] font-bold uppercase ${isToggling ? 'text-accent animate-pulse' : 'text-slate-500'}`}>
                      {isToggling ? 'Wait...' : autoTrading ? 'Active' : 'Manual'}
                    </span>
                  </div>
                </div>
                <button
                  id="auto-trading-toggle"
                  onClick={toggleAutoTrading}
                  disabled={isToggling}
                  className={`w-10 h-5 rounded-none border-2 flex items-center transition-all ${isToggling ? 'opacity-50 cursor-wait' : ''} ${autoTrading ? 'border-accent bg-accent/20 justify-end' : 'border-slate-700 bg-slate-800 justify-start'}`}
                >
                  <div className={`w-3 h-3 m-0.5 ${isToggling ? 'bg-slate-500 animate-spin' : autoTrading ? 'bg-accent' : 'bg-slate-500'}`}></div>
                </button>
              </div>

              <select
                id="token-select"
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                className="w-full p-3 bg-black border border-slate-700 text-white font-bold text-xs focus:border-accent outline-none appearance-none cursor-pointer"
              >
                {availableMarkets.length > 0 ? (
                  availableMarkets.map((m) => (
                    <option key={m} value={m}>{m}</option>
                  ))
                ) : (
                  <>
                    <option value="BTC-USD">BTC-USD</option>
                    <option value="ETH-USD">ETH-USD</option>
                    <option value="SOL-USD">SOL-USD</option>
                  </>
                )}
              </select>

              {/* Risk Profile Selector */}
              <div className="mb-4">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-2">Analysis Risk Profile</span>
                <div className="grid grid-cols-3 gap-2 p-1 bg-black border border-slate-800">
                  {(['SAFETY', 'MODERATE', 'AGGRESSIVE'] as const).map((profile) => (
                    <button
                      key={profile}
                      onClick={() => setRiskProfile(profile)}
                      className={`py-2 text-[9px] font-black uppercase transition-all border ${riskProfile === profile
                          ? profile === 'AGGRESSIVE' ? 'bg-danger/20 border-danger text-danger'
                            : profile === 'MODERATE' ? 'bg-warning/20 border-warning text-warning'
                              : 'bg-success/20 border-success text-success'
                          : 'border-transparent text-slate-600 hover:text-slate-400'
                        }`}
                    >
                      {profile}
                    </button>
                  ))}
                </div>
              </div>

              {/* Trading Strategy Mode - Positioned Here */}
              <div className="mb-4">
                <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-2">Execution Strategy</span>
                <select
                  value={tradingMode}
                  onChange={(e) => setTradingMode(e.target.value)}
                  className="w-full bg-black border border-slate-700 p-3 text-[10px] text-white font-black uppercase outline-none focus:border-accent appearance-none cursor-pointer"
                >
                  <option value="MOMENTUM">⚡ MOMENTUM (Trend Following)</option>
                  <option value="CONTRARIAN">🔄 CONTRARIAN (Mean Reversion)</option>
                  <option value="SMART_MONEY">🏦 SMART MONEY (ETF Flow)</option>
                </select>
              </div>

              <button
                id="analyze-btn"
                onClick={handleAnalyze}
                disabled={loading || autoTrading}
                className={`w-full neobrutal-button p-3 flex items-center justify-center gap-2 text-xs disabled:opacity-50 ${autoTrading ? 'bg-slate-800 text-slate-500' : ''}`}
              >
                {loading ? <BrainCircuit className="animate-spin w-4 h-4" /> : <Zap className="w-4 h-4" />}
                {loading ? 'ANALYZING...' : autoTrading ? 'AUTO-MODE ACTIVE' : 'ANALYZE MARKET'}
              </button>
            </div>
          </section>

          {/* Session Private Key Section (MOVED UP & COMPACT) */}
          <section className="neobrutal-card p-4 bg-slate-900 border-warning/20">
            <h2 className="text-sm font-black mb-3 flex items-center gap-2 uppercase tracking-widest text-warning">
              <ShieldCheck className="w-4 h-4" /> SESSION AUTH
            </h2>

            {/* Safety Guide Alert */}
            <div className="mb-4 p-3 bg-warning/5 border-l-4 border-warning text-[10px] space-y-2">
              <p className="text-warning font-black uppercase">⚠️ SAFETY & SETUP GUIDE:</p>
              <ol className="list-decimal list-inside text-slate-400 font-bold space-y-1">
                <li>Register a <span className="text-white">NEW WALLET</span> on <a href="https://testnet.sodex.com" target="_blank" rel="noopener noreferrer" className="text-accent underline hover:text-white">SoDEX Testnet</a>.</li>
                <li>Backup that specific <span className="text-white">EVM Private Key</span>.</li>
                <li>Claim <span className="text-white">vUSDC Faucet</span> and transfer to <span className="text-success font-black">FUTURE BALANCE</span> (not Spot).</li>
              </ol>
              <p className="text-slate-500 italic mt-2">
                Note: Your key is stored locally in RAM for high-frequency signing and never leaves your browser.
              </p>
            </div>
            
            <div className="space-y-3">
              <div className="relative">
                <label className="block text-[8px] font-black text-slate-500 uppercase mb-1">EVM Wallet Private Key</label>
                <input
                  type={showPK ? "text" : "password"}
                  placeholder="0x..."
                  value={userPrivateKey}
                  onChange={(e) => setUserPrivateKey(e.target.value)}
                  className="w-full bg-black border border-slate-700 p-2 pr-8 text-[10px] text-white font-mono outline-none focus:border-warning"
                />
                <button onClick={() => setShowPK(!showPK)} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-600">
                  {showPK ? <ShieldCheck className="w-3 h-3" /> : <Zap className="w-3 h-3" />}
                </button>
              </div>

              {/* BYOK: AI Keys */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="relative">
                  <label className="block text-[8px] font-black text-slate-500 uppercase mb-1">Gemini API Key (Optional)</label>
                  <input
                    type="password"
                    placeholder="AIza..."
                    value={geminiKey}
                    onChange={(e) => setGeminiKey(e.target.value)}
                    className="w-full bg-black border border-slate-700 p-2 text-[10px] text-white font-mono outline-none focus:border-accent"
                  />
                </div>
                <div className="relative">
                  <label className="block text-[8px] font-black text-slate-500 uppercase mb-1">OpenRouter Key (Optional)</label>
                  <input
                    type="password"
                    placeholder="sk-or-..."
                    value={openrouterKey}
                    onChange={(e) => setOpenrouterKey(e.target.value)}
                    className="w-full bg-black border border-slate-700 p-2 text-[10px] text-white font-mono outline-none focus:border-accent"
                  />
                </div>
              </div>

              <button
                onClick={saveSettings}
                disabled={!userPrivateKey}
                className="w-full neobrutal-button bg-warning/20 text-warning p-2 font-black uppercase text-[10px] border-warning/30 hover:bg-warning hover:text-black disabled:opacity-30"
              >
                SAVE TO DATABASE
              </button>

              {userPrivateKey && (
                <div className="flex items-center gap-1 text-[9px] text-success font-black italic uppercase">
                  <ShieldCheck className="w-3 h-3" /> Key Active
                </div>
              )}
            </div>
          </section>

          {/* Wallet Status Card (COMPACT) */}
          <section className="neobrutal-card p-4 bg-slate-900 border-slate-800">
            <h2 className="text-sm font-black mb-3 flex items-center gap-2 uppercase tracking-widest text-slate-400">
              <ShieldCheck className="w-4 h-4 text-accent" /> STATUS
            </h2>
            <div className="space-y-2">
              <div className="flex justify-between items-center p-2 bg-black/30 border border-slate-800 text-[10px]">
                <span className="text-slate-500 font-bold">NETWORK</span>
                <span className="text-success font-black">{isConnected ? 'VALUECHAIN' : 'OFFLINE'}</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-black/30 border border-slate-800 text-[10px]">
                <span className="text-slate-500 font-bold">ACCOUNT ID</span>
                <span className="text-white font-black">{accountInfo?.account_id || '---'}</span>
              </div>
              <div className="flex justify-between items-center p-2 bg-success/5 border border-success/10 text-[10px]">
                <span className="text-success font-bold">SODEX BAL</span>
                <span className="text-success font-black">{accountInfo?.balance ? `${parseFloat(accountInfo.balance).toFixed(2)} vUSDC` : '0.00'}</span>
              </div>
            </div>
          </section>

          {/* Market Intelligence Widgets (NEW) */}
          <section className="neobrutal-card p-4 bg-slate-900 border-slate-800">
            <h2 className="text-sm font-black mb-4 flex items-center gap-2 uppercase tracking-widest text-slate-400">
              <BarChart3 className="w-4 h-4 text-accent" /> MARKET INTEL
            </h2>
            
            <div className="grid grid-cols-1 gap-3">
              {/* ETF Flow Card */}
              <div className="p-3 bg-black/40 border border-slate-800 flex flex-col justify-between min-h-[80px]">
                <div className="flex justify-between items-center mb-2">
                  <span className="text-[8px] font-black text-slate-500 uppercase">ETF Net Inflow</span>
                  <span className="text-[8px] font-black text-slate-600 uppercase">US Market</span>
                </div>
                {marketIntel?.etf ? (
                  <div className="mt-auto">
                    <span className={`text-xl font-black italic tracking-tighter ${marketIntel.etf.net_inflow >= 0 ? 'text-success' : 'text-danger'}`}>
                      {marketIntel.etf.net_inflow >= 0 ? '+' : ''}
                      {(marketIntel.etf.net_inflow / 1000000).toFixed(1)}M
                    </span>
                    <span className="block text-[8px] text-slate-500 font-bold uppercase mt-1">
                      {marketIntel.etf.date || 'LATEST'} • vUSDC
                    </span>
                  </div>
                ) : (
                  <div className="animate-pulse flex flex-col gap-2 mt-auto">
                    <div className="h-4 w-20 bg-slate-800 rounded"></div>
                    <div className="h-2 w-12 bg-slate-800 rounded"></div>
                  </div>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* Right Column: AI Analysis & Chart */}
        <div className="lg:col-span-8 space-y-6">

          {loading ? (
            <div className="neobrutal-card p-8 flex flex-col items-center justify-center bg-slate-900 min-h-[300px]">
              <div className="relative mb-6">
                <div className="w-16 h-16 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
                <BrainCircuit className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-8 h-8 text-accent" />
              </div>
              <h3 className="text-2xl font-black text-white italic mb-2 tracking-tighter">PROCESSING MACRO DATA</h3>
              <p className="text-slate-500 font-bold uppercase tracking-widest text-sm animate-pulse">
                Fetching SoSoValue news & querying MiniMax M2.7...
              </p>
            </div>
          ) : autoTrading ? (
            <div className="space-y-6">
              <div className="neobrutal-card p-8 bg-accent/10 border-accent/30 animate-in fade-in slide-in-from-top-4 duration-500">
                <div className="flex items-center gap-4 mb-4">
                  <div className="relative">
                    <BrainCircuit className="w-10 h-10 text-accent animate-pulse" />
                    <div className="absolute -top-1 -right-1 w-3 h-3 bg-success rounded-full border-2 border-slate-900 animate-ping"></div>
                  </div>
                  <div>
                    <h3 className="text-xl font-black italic text-white uppercase tracking-tighter">Autonomous Monitor Active</h3>
                    <p className="text-xs font-bold text-accent uppercase tracking-widest">Scanning {symbol} every 30s</p>
                  </div>
                </div>
                <div className="bg-black/40 p-6 border-l-4 border-accent italic text-slate-400">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse"></div>
                    <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">REAL-TIME AUTONOMOUS ENGINE LOG</span>
                  </div>
                  <p className="text-sm leading-relaxed text-slate-200">
                    "{lastAutoLog || "Bot is currently monitoring global news and technical indicators. Waiting for next scan..."}"
                  </p>
                  <p className="mt-4 text-[10px] text-slate-600 font-bold uppercase tracking-widest border-t border-slate-800 pt-2">
                    The system will automatically execute orders when the AI Signal Score exceeds the threshold.
                  </p>
                </div>
                <div className="mt-6 flex gap-4">
                  <div className="flex-1 p-3 bg-slate-900 border border-slate-800 text-[10px] font-black uppercase text-slate-500">
                    Last Check: <span className="text-white ml-2">{new Date().toLocaleTimeString()}</span>
                  </div>
                  <div className="flex-1 p-3 bg-slate-900 border border-slate-800 text-[10px] font-black uppercase text-slate-500">
                    Engine: <span className="text-white ml-2">Hybrid Ensemble (Gemini + Llama)</span>
                  </div>
                </div>
              </div>

              {/* Keep the chart visible but maybe show an 'Auto' badge */}
              <div className="neobrutal-card p-12 flex flex-col items-center justify-center bg-slate-900 border-dashed border-slate-700 opacity-50 flex-1 min-h-[300px]">
                <BarChart3 className="w-16 h-16 text-slate-700 mb-4" />
                <p className="text-slate-500 font-bold uppercase tracking-widest text-center">
                  Autonomous Engine is Controlling the Market.
                </p>
              </div>
            </div>
          ) : analysis ? (
            <div className="space-y-6">
              {/* Analysis Result */}
              <div className="neobrutal-card bg-slate-900 overflow-hidden">
                <div className="bg-black p-4 border-b-2 border-slate-800 flex justify-between items-center">
                  <div className="flex items-center gap-3">
                    <span className="text-accent font-black italic tracking-widest uppercase text-sm">AI SENTIMENT ANALYSIS</span>
                    <span className="px-2 py-0.5 bg-accent text-black text-[10px] font-black uppercase rounded-sm">
                      {analysis.symbol || symbol}
                    </span>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-slate-500 text-xs font-bold uppercase tracking-tighter">RELIABILITY: HIGH</span>
                    <span className="text-[10px] font-black bg-accent/20 text-accent px-2 py-1 uppercase tracking-widest border border-accent/30">
                      {analysis.analysis?.analysis_model || analysis.analysis?.model_name || 'HYBRID ENGINE'}
                    </span>
                  </div>
                </div>

                <div className="p-4">
                  <div className="flex flex-col md:flex-row gap-4 mb-4">
                    <div className={`p-4 rounded-none border-2 ${analysis.analysis?.decision === 'LONG' ? 'border-success bg-success/5' :
                        analysis.analysis?.decision === 'SHORT' ? 'border-danger bg-danger/5' :
                          'border-slate-700 bg-slate-800/50'
                      } flex-1 flex flex-col items-center justify-center text-center`}>
                      <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-1">Recommendation</span>
                      <h3 className={`text-4xl font-black italic tracking-tighter ${analysis.analysis?.decision === 'LONG' ? 'text-success' :
                          analysis.analysis?.decision === 'SHORT' ? 'text-danger' :
                            'text-slate-400'
                        }`}>
                        {analysis.analysis?.decision}
                      </h3>
                    </div>

                    <div className="flex-2 space-y-2">
                      <div className="flex items-center gap-2">
                        <MessageSquareQuote className="w-4 h-4 text-accent" />
                        <h4 className="text-sm font-black italic">AI REASONING</h4>
                      </div>
                      <div className="space-y-2">
                        <div className="bg-black/40 p-3 border-l-2 border-accent">
                          <span className="block text-[8px] font-black text-accent uppercase mb-1">FUNDAMENTAL & INSTITUTIONAL</span>
                          <p className="text-[10px] text-slate-300 leading-tight italic">
                            {analysis.analysis?.fundamental_analysis || "No fundamental analysis."}
                          </p>
                        </div>
                        <div className="bg-black/40 p-3 border-l-2 border-success">
                          <span className="block text-[8px] font-black text-success uppercase mb-1">TECHNICAL ANALYSIS (EMA/RSI/VOL)</span>
                          <p className="text-[10px] text-slate-300 leading-tight italic">
                            {analysis.analysis?.technical_analysis || "No technical analysis."}
                          </p>
                        </div>
                        <div className="bg-black/40 p-3 border-l-2 border-slate-500">
                          <span className="block text-[8px] font-black text-slate-400 uppercase mb-1">OVERALL STRATEGY</span>
                          <p className="text-[10px] text-slate-300 leading-tight italic">
                            {analysis.analysis?.reasoning || "No strategy provided."}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Execution Plan Card (Compact) */}
                  <div className="neobrutal-card p-4 bg-black border-slate-700">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="p-2 border border-slate-800 text-center">
                        <span className="block text-[8px] font-black text-slate-500 uppercase mb-1">ENTRY</span>
                        <span className="text-lg font-black text-white italic tracking-tighter">${formatPrice(analysis.current_price)}</span>
                      </div>
                      <div className="p-2 border border-slate-800 text-center flex flex-col justify-center min-h-[60px]">
                        <span className="block text-[8px] font-black text-slate-500 uppercase mb-1 text-success">TAKE PROFIT</span>
                        <span className="text-lg font-black text-success italic tracking-tighter">
                          {analysis.analysis.params?.tp_price ? `$${formatPrice(analysis.analysis.params.tp_price)}` : '---'}
                        </span>
                        {analysis.analysis.params?.tp_desc && (
                          <span className="text-[7px] text-slate-500 font-bold leading-tight mt-1">
                            {analysis.analysis.params.tp_desc}
                          </span>
                        )}
                      </div>
                      <div className="p-2 border border-slate-800 text-center flex flex-col justify-center min-h-[60px]">
                        <span className="block text-[8px] font-black text-slate-500 uppercase mb-1 text-danger">STOP LOSS</span>
                        <span className="text-lg font-black text-danger italic tracking-tighter">
                          {analysis.analysis.params?.sl_price ? `$${formatPrice(analysis.analysis.params.sl_price)}` : '---'}
                        </span>
                        {analysis.analysis.params?.sl_desc && (
                          <span className="text-[7px] text-slate-500 font-bold leading-tight mt-1">
                            {analysis.analysis.params.sl_desc}
                          </span>
                        )}
                      </div>
                    </div>

                    {analysis.analysis.decision === 'HOLD' ? (
                      <div className="mt-8 space-y-4">
                        <div className="flex items-center gap-2 mb-2">
                          <div className="h-[1px] flex-1 bg-slate-800"></div>
                          <span className="text-[10px] font-black text-warning uppercase italic tracking-widest">Manual Override</span>
                          <div className="h-[1px] flex-1 bg-slate-800"></div>
                        </div>
                        <div className="flex gap-4">
                          <button
                            id="force-long-btn"
                            onClick={() => handleExecute('LONG')}
                            disabled={!isConnected || isRegistered === false}
                            className="flex-1 neobrutal-button bg-success/20 hover:bg-success text-success hover:text-black p-4 font-black italic flex items-center justify-center gap-2 border-success/30 disabled:opacity-30"
                          >
                            <TrendingUp className="w-5 h-5" /> FORCE LONG
                          </button>
                          <button
                            onClick={() => handleExecute('SHORT')}
                            disabled={!isConnected || isRegistered === false}
                            className="flex-1 neobrutal-button bg-danger/20 hover:bg-danger text-danger hover:text-black p-4 font-black italic flex items-center justify-center gap-2 border-danger/30 disabled:opacity-30"
                          >
                            <TrendingDown className="w-5 h-5" /> FORCE SHORT
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        className={`w-full mt-8 neobrutal-button p-6 text-xl flex items-center justify-center gap-4 disabled:opacity-50 ${(!isConnected || chainId !== valueChain.id || !isRegistered) ? 'bg-slate-800 cursor-not-allowed text-slate-600' :
                            isConfirmed ? 'bg-success' : 'bg-success hover:bg-success/90'
                          }`}
                        onClick={() => {
                          if (chainId !== valueChain.id) switchChain({ chainId: valueChain.id });
                          else handleExecute();
                        }}
                        disabled={isExecuting || isSigning || !isConnected || (isConnected && isRegistered === false)}
                      >
                        {!isConnected ? (
                          <>
                            <Wallet className="w-6 h-6" />
                            CONNECT WALLET
                          </>
                        ) : chainId !== valueChain.id ? (
                          <>
                            <AlertTriangle className="w-6 h-6 text-danger" />
                            SWITCH TO VALUECHAIN
                          </>
                        ) : isRegistered === false ? (
                          <>
                            <AlertTriangle className="w-6 h-6 text-danger" />
                            NOT REGISTERED ON SODEX
                          </>
                        ) : isExecuting || isSigning ? (
                          <>
                            <BrainCircuit className="animate-spin w-6 h-6" />
                            {isSigning ? 'SIGNING MESSAGE...' : 'EXECUTING...'}
                          </>
                        ) : (
                          <>
                            <Zap className="w-6 h-6 fill-white" />
                            EXECUTE ON-CHAIN
                          </>
                        )}
                      </button>
                    )}

                    {hash && (
                      <div className="mt-4 p-3 bg-slate-800 border border-slate-700 text-xs font-mono break-all">
                        <span className="text-slate-500 font-black mr-2">SIGNATURE:</span>
                        <span className="text-accent">
                          {hash.substring(0, 40)}...
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="neobrutal-card p-12 flex flex-col items-center justify-center text-center bg-slate-900/50 border-dashed border-slate-800 flex-1 min-h-[400px]">
              <div className="w-20 h-20 bg-slate-800/50 rounded-full flex items-center justify-center mb-6">
                <BrainCircuit className="w-10 h-10 text-slate-600" />
              </div>
              <h3 className="text-2xl font-black text-slate-500 uppercase tracking-tighter mb-2">No Active Analysis</h3>
              <p className="text-slate-600 font-bold uppercase text-xs tracking-widest max-w-xs">
                Select an asset and click "Analyze" to generate AI insights
              </p>
            </div>
          )}

          {/* TRADING CHART SECTION (MOVED DOWN) */}
          <section className="neobrutal-card p-0 bg-slate-900 border-slate-800 overflow-hidden min-h-[400px] flex flex-col">
            <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-black/20">
              <h2 className="text-sm font-black flex items-center gap-2 uppercase tracking-widest text-slate-300">
                <BarChart3 className="w-4 h-4 text-accent" /> MARKET CHART
              </h2>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 bg-slate-800 text-[10px] font-bold text-slate-400">15M</span>
                <span className="px-2 py-0.5 bg-accent/20 text-[10px] font-bold text-accent">LIVE</span>
              </div>
            </div>
            <div className="flex-1 min-h-[350px]">
              {chartLoading ? (
                <div className="w-full h-[350px] flex items-center justify-center bg-black/20">
                  <BrainCircuit className="w-8 h-8 text-accent animate-spin" />
                </div>
              ) : (
                <DynamicTradingChart data={klines} symbol={symbol} />
              )}
            </div>
          </section>

          {/* AI DISCOVERY LOGS (NEW) */}
          <section className="neobrutal-card p-4 bg-slate-900 border-slate-800">
            <h2 className="text-sm font-black mb-4 flex items-center gap-2 uppercase tracking-widest text-slate-400">
              <BrainCircuit className="w-4 h-4 text-accent" /> AI & NEWS DISCOVERY LOGS
            </h2>

            <div className="space-y-3">
              {analysis ? (
                <div className="neobrutal-card bg-slate-950 border-slate-800 overflow-hidden">
                  <div className="bg-black p-3 border-b-2 border-slate-800 flex items-center gap-2">
                    <BrainCircuit className="w-4 h-4 text-accent" />
                    <h3 className="text-sm font-black italic tracking-widest uppercase text-white">AI & NEWS DISCOVERY LOGS</h3>
                  </div>

                  <div className="p-4 space-y-4">
                    {/* STAGE 1: TECHNICAL ENGINE */}
                    <div className="flex gap-4 items-start border-l-4 border-orange-500 bg-orange-500/5 p-4 relative group">
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-2">
                          <div className="flex items-center gap-2">
                            <Zap className="w-3 h-3 text-orange-500 fill-orange-500" />
                            <span className="text-[10px] font-black text-white uppercase tracking-widest">STAGE 1: TECHNICAL RULE-BASED ENGINE</span>
                          </div>
                          <span className="text-[8px] font-black bg-slate-800 text-slate-400 px-2 py-0.5 rounded-sm uppercase tracking-widest">
                            Indicator Engine
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 font-medium leading-relaxed italic mb-3">
                          "{analysis.analysis?.technical_analysis || "Processing technical indicators..."}"
                        </p>
                        <div className="flex gap-4">
                          <div className="text-[9px] font-bold uppercase text-slate-500">
                            Signal: <span className={analysis.analysis?.decision !== 'HOLD' ? 'text-success' : 'text-warning'}>
                              {analysis.analysis?.decision || '---'}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* STAGE 2: AI VALIDATION */}
                    <div className="flex gap-4 items-start border-l-4 border-green-500 bg-green-500/5 p-4 relative group">
                      <div className="flex-1">
                        <div className="flex justify-between items-center mb-2">
                          <div className="flex items-center gap-2">
                            <ShieldCheck className="w-3 h-3 text-green-500 fill-green-500" />
                            <span className="text-[10px] font-black text-white uppercase tracking-widest">STAGE 2: AI RISK VALIDATION</span>
                          </div>
                          <span className="text-[8px] font-black bg-slate-800 text-slate-400 px-2 py-0.5 rounded-sm uppercase tracking-widest">
                            {analysis.analysis?.analysis_model || 'Gemini 3.1'}
                          </span>
                        </div>
                        <p className="text-xs text-slate-300 font-medium leading-relaxed italic mb-3">
                          "{analysis.analysis?.reasoning || "AI is validating technical signal..."}"
                        </p>
                        <div className="flex gap-4">
                          <div className="text-[9px] font-bold uppercase text-slate-500">
                            Validation: <span className="text-white">{analysis.analysis?.decision !== 'HOLD' ? 'PASSED' : 'SAFE HOLD'}</span>
                          </div>
                          <div className="text-[9px] font-bold uppercase text-slate-500">
                            Confidence: <span className="text-white">{analysis.analysis?.confidence || '0'}</span>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* LATEST NEWS */}
                    <div className="p-4 bg-black/40 border border-slate-800">
                      <div className="flex items-center gap-2 mb-4">
                        <MessageSquareQuote className="w-4 h-4 text-slate-500" />
                        <span className="text-[10px] font-black text-white uppercase tracking-widest">LATEST NEWS AGGREGATION</span>
                      </div>
                      <div className="space-y-3 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                        {analysis.news && analysis.news.length > 0 ? (
                          analysis.news.map((item: any, idx: number) => (
                            <div key={idx} className="flex gap-3 items-start group border-b border-slate-800/50 pb-2">
                              <ChevronRight className="w-3 h-3 text-accent mt-1 flex-shrink-0 group-hover:translate-x-1 transition-transform" />
                              <p className="text-[11px] text-slate-400 leading-relaxed font-medium group-hover:text-slate-200 transition-colors" 
                                 dangerouslySetInnerHTML={{ __html: item.title }} />
                            </div>
                          ))
                        ) : (
                          <div className="text-[11px] text-slate-600 italic">No recent news discovered for this symbol.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="py-8 text-center border border-dashed border-slate-800 bg-black/20">
                  <BrainCircuit className="w-8 h-8 text-slate-800 mx-auto mb-2" />
                  <p className="text-[10px] text-slate-600 font-bold uppercase tracking-widest">Waiting for analysis trigger...</p>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>

      {/* Trade Confirmation Modal */}
      {showModal && analysis && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="neobrutal-card bg-slate-900 w-full max-w-lg border-4 border-black overflow-hidden animate-in fade-in zoom-in duration-200">
            <div className="bg-accent p-4 border-b-4 border-black flex justify-between items-center">
              <h3 className="text-black font-black italic tracking-tighter text-2xl uppercase">Confirm Order</h3>
              <button onClick={() => setShowModal(false)} className="text-black font-black text-xl hover:scale-125 transition-transform">✕</button>
            </div>

            <div className="p-8 space-y-6">
              {/* Order Summary Header */}
              <div className={`p-4 border-2 border-black flex justify-between items-center ${(overrideSide || analysis.analysis?.decision) === 'LONG' ? 'bg-success/20 border-success' : 'bg-danger/20 border-danger'
                }`}>
                <div className="flex flex-col">
                  <span className="text-[10px] font-black text-slate-400 uppercase">Target Asset</span>
                  <span className="text-xl font-black italic">{symbol}</span>
                </div>
                <div className="text-right">
                  <span className="text-[10px] font-black text-slate-400 uppercase">Direction</span>
                  <span className={`block text-2xl font-black italic ${(overrideSide || analysis.analysis?.decision) === 'LONG' ? 'text-success' : 'text-danger'
                    }`}>{overrideSide || analysis.analysis?.decision}</span>
                </div>
              </div>

              {/* Order Type Selector */}
              <div className="flex gap-2 p-1 bg-black border-2 border-slate-700">
                <button
                  onClick={() => setExecOrderType(2)}
                  className={`flex-1 p-2 text-[10px] font-black uppercase transition-all ${execOrderType === 2 ? 'bg-accent text-black' : 'text-slate-500 hover:text-white'}`}
                >
                  Market Price
                </button>
                <button
                  onClick={() => setExecOrderType(1)}
                  className={`flex-1 p-2 text-[10px] font-black uppercase transition-all ${execOrderType === 1 ? 'bg-accent text-black' : 'text-slate-500 hover:text-white'}`}
                >
                  Limit Order
                </button>
              </div>

              {/* Editable Inputs */}
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-black text-slate-500 uppercase">Margin (vUSDC)</label>
                  <input
                    type="text"
                    value={marginUSD}
                    onChange={(e) => setMarginUSD(e.target.value)}
                    className="w-full bg-black border-2 border-slate-700 p-3 text-white font-black focus:border-accent outline-none"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-black text-slate-500 uppercase">Leverage (x)</label>
                  <input
                    type="number"
                    value={execLeverage}
                    onChange={(e) => setExecLeverage(parseInt(e.target.value))}
                    className="w-full bg-black border-2 border-slate-700 p-3 text-white font-black focus:border-accent outline-none"
                  />
                </div>

                {execOrderType === 1 && (
                  <div className="col-span-2 space-y-2 animate-in slide-in-from-top-2 duration-200">
                    <label className="text-xs font-black text-warning uppercase italic">Entry Price (Limit)</label>
                    <input
                      type="text"
                      value={execPrice}
                      onChange={(e) => setExecPrice(e.target.value)}
                      className="w-full bg-black border-4 border-warning p-3 text-white font-black focus:border-accent outline-none"
                    />
                  </div>
                )}

                <div className="space-y-2">
                  <label className="text-xs font-black text-slate-500 uppercase text-success">Take Profit ($)</label>
                  <input
                    type="text"
                    value={execTP}
                    onChange={(e) => setExecTP(e.target.value)}
                    placeholder="Auto-suggested"
                    className="w-full bg-black border-2 border-slate-700 p-3 text-success font-black focus:border-success outline-none"
                  />
                  {execTPDesc && <p className="text-[9px] text-slate-500 font-bold italic leading-tight">{execTPDesc}</p>}
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-black text-slate-500 uppercase text-danger">Stop Loss ($)</label>
                  <input
                    type="text"
                    value={execSL}
                    onChange={(e) => setExecSL(e.target.value)}
                    placeholder="Auto-suggested"
                    className="w-full bg-black border-2 border-slate-700 p-3 text-danger font-black focus:border-danger outline-none"
                  />
                  {execSLDesc && <p className="text-[9px] text-slate-500 font-bold italic leading-tight">{execSLDesc}</p>}
                </div>
              </div>

              {/* Quantity Estimate */}
              <div className="p-4 bg-slate-800 border-2 border-black flex justify-between items-center">
                <div className="flex items-center gap-2">
                  <BarChart3 className="w-4 h-4 text-accent" />
                  <span className="text-xs font-bold text-slate-400 uppercase">Est. Quantity ({symbol.split('-')[0]})</span>
                </div>
                <span className="text-lg font-black text-white italic">
                  {((parseFloat(marginUSD) * execLeverage) / parseFloat(analysis.current_price)).toFixed(4)}
                </span>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-3 pt-4">
                <div className="flex gap-4">
                  {/* Classic Order Hidden as requested */}
                  <button
                    onClick={() => confirmExecute((overrideSide || analysis.analysis.decision) as 'LONG' | 'SHORT')}
                    className="w-full p-4 border-2 border-black bg-success text-black font-black hover:bg-success/90 transition-colors uppercase tracking-widest text-xs flex items-center justify-center gap-2"
                  >
                    <ShieldCheck className="w-4 h-4" />
                    UNIFIED EXECUTE (SYNC LEVERAGE + ORDER)
                  </button>
                </div>
                <button
                  onClick={() => setShowModal(false)}
                  className="w-full p-2 border-2 border-black bg-black text-slate-500 font-black hover:text-white transition-colors uppercase tracking-widest text-[10px]"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
