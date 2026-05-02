'use client';

import * as React from 'react';
import {
  RainbowKitProvider,
  getDefaultWallets,
  getDefaultConfig,
  darkTheme,
} from '@rainbow-me/rainbowkit';
import {
  argentWallet,
  trustWallet,
  ledgerWallet,
} from '@rainbow-me/rainbowkit/wallets';
import { mainnet, polygon, optimism, arbitrum, base, sepolia } from 'wagmi/chains';
import { defineChain } from 'viem';

export const valueChain = defineChain({
  id: 138565,
  name: 'ValueChain Testnet',
  nativeCurrency: { name: 'Ethereum', symbol: 'ETH', decimals: 18 },
  rpcUrls: {
    default: { http: ['https://testnet-rpc.valuechain.com'] }, // Placeholder RPC
  },
  blockExplorers: {
    default: { name: 'Explorer', url: 'https://explorer.valuechain.com' },
  },
  testnet: true,
});
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { WagmiProvider } from 'wagmi';
import '@rainbow-me/rainbowkit/styles.css';

const projectId = process.env.NEXT_PUBLIC_REOWN_PROJECT_ID || '8fc161f38e079717d23d9a101e483582'; // Sample ID for local dev

const { wallets } = getDefaultWallets({
  appName: 'SoDEX AI',
  projectId,
});

const config = getDefaultConfig({
  appName: 'SoDEX AI',
  projectId,
  wallets: [
    ...wallets,
    {
      groupName: 'Other',
      wallets: [argentWallet, trustWallet, ledgerWallet],
    },
  ],
  chains: [valueChain],
  ssr: true,
});

const queryClient = new QueryClient();

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <WagmiProvider config={config}>
      <QueryClientProvider client={queryClient}>
        <RainbowKitProvider 
          theme={darkTheme({
            accentColor: '#f97316', // Cyberpunk Orange
            accentColorForeground: 'white',
            borderRadius: 'small',
            fontStack: 'system',
            overlayBlur: 'small',
          })}
        >
          {children}
        </RainbowKitProvider>
      </QueryClientProvider>
    </WagmiProvider>
  );
}
