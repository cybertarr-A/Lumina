/**
 * Wagmi + RainbowKit configuration for multi-chain Web3.
 */
"use client";

import { connectorsForWallets } from "@rainbow-me/rainbowkit";
import { metaMaskWallet, injectedWallet } from "@rainbow-me/rainbowkit/wallets";
import { createConfig, http } from "wagmi";
import { mainnet, polygon, bsc, sepolia } from "wagmi/chains";

export const SUPPORTED_CHAINS = [
  mainnet,
  sepolia,
  polygon,
  bsc,
] as const;

const projectId = process.env.NEXT_PUBLIC_WALLETCONNECT_PROJECT_ID || "demo-project-id";

const connectors = connectorsForWallets(
  [
    {
      groupName: "Popular",
      wallets: [metaMaskWallet, injectedWallet],
    },
  ],
  { appName: "Lumina", projectId }
);

export const wagmiConfig = createConfig({
  chains: SUPPORTED_CHAINS,
  connectors,
  transports: {
    [mainnet.id]: http(),
    [sepolia.id]: http(),
    [polygon.id]: http(),
    [bsc.id]: http(),
  },
  ssr: true,
});

export const CHAIN_EXPLORER: Record<number, string> = {
  1: "https://etherscan.io",
  11155111: "https://sepolia.etherscan.io",
  137: "https://polygonscan.com",
  56: "https://bscscan.com",
};

export function getExplorerUrl(chainId: number, txOrAddress: string, type: "tx" | "address" = "tx") {
  const base = CHAIN_EXPLORER[chainId] || "https://etherscan.io";
  return `${base}/${type}/${txOrAddress}`;
}
