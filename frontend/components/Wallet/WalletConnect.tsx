"use client";

import { ConnectButton } from "@rainbow-me/rainbowkit";
import { useAccount, useChainId, useSwitchChain } from "wagmi";
import { Globe, ChevronDown } from "lucide-react";

interface WalletConnectProps {
  showNetworkSwitcher?: boolean;
}

export function WalletConnect({ showNetworkSwitcher = false }: WalletConnectProps) {
  const { isConnected, address } = useAccount();
  const chainId = useChainId();
  const { switchChain } = useSwitchChain();

  const NETWORKS = [
    { id: 1, name: "Ethereum" },
    { id: 11155111, name: "Sepolia" },
    { id: 137, name: "Polygon" },
    { id: 80001, name: "Mumbai" },
    { id: 56, name: "BSC" },
    { id: 97, name: "BSC Testnet" },
  ];

  return (
    <div className="flex items-center gap-3">
      {showNetworkSwitcher && isConnected && (
        <div className="relative group">
          <button className="flex items-center gap-2 px-3 py-2 rounded-xl glass border border-white/15 text-sm text-slate-300 hover:text-white transition-colors">
            <Globe className="w-4 h-4" />
            {NETWORKS.find((n) => n.id === chainId)?.name || "Unknown Network"}
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <div className="absolute right-0 mt-2 w-44 glass-card border border-white/15 rounded-xl overflow-hidden opacity-0 group-hover:opacity-100 transition-opacity z-50">
            {NETWORKS.filter(n => [1, 11155111, 137, 56].includes(n.id)).map((network) => (
              <button
                key={network.id}
                onClick={() => switchChain?.({ chainId: network.id as 1 | 11155111 | 137 | 56 })}
                className={`w-full px-4 py-2.5 text-left text-sm hover:bg-white/10 transition-colors flex items-center gap-2 ${
                  chainId === network.id ? "text-purple-400" : "text-slate-300"
                }`}
              >
                {chainId === network.id && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                )}
                {network.name}
              </button>
            ))}
          </div>
        </div>
      )}
      <ConnectButton
        showBalance={false}
        chainStatus="icon"
        accountStatus="avatar"
      />
    </div>
  );
}
