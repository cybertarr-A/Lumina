"use client";

import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Rocket, Shield, CheckCircle2, XCircle, Loader2, Globe,
  AlertTriangle, ExternalLink, Copy, ChevronDown, Info
} from "lucide-react";
import { useAccount, useChainId } from "wagmi";
import { Sidebar } from "@/components/Layout/Sidebar";
import { WalletConnect } from "@/components/Wallet/WalletConnect";
import { contractsApi, deployApi } from "@/lib/api";
import { useContractsStore, useUIStore } from "@/lib/store";
import { getExplorerUrl } from "@/lib/wagmi";
import { Contract } from "@/lib/store";

const NETWORKS = [
  { name: "Ethereum Mainnet", chain_id: 1, network: "ETH_MAINNET", color: "text-blue-400", testnet: false },
  { name: "Ethereum Sepolia", chain_id: 11155111, network: "ETH_SEPOLIA", color: "text-blue-300", testnet: true },
  { name: "Polygon Mainnet", chain_id: 137, network: "POLYGON_MAINNET", color: "text-purple-400", testnet: false },
  { name: "Polygon Mumbai", chain_id: 80001, network: "POLYGON_MUMBAI", color: "text-purple-300", testnet: true },
  { name: "BSC Mainnet", chain_id: 56, network: "BSC_MAINNET", color: "text-yellow-400", testnet: false },
  { name: "BSC Testnet", chain_id: 97, network: "BSC_TESTNET", color: "text-yellow-300", testnet: true },
  { name: "Local (Hardhat)", chain_id: 31337, network: "LOCAL", color: "text-green-400", testnet: true },
];

interface Deployment {
  id: string;
  status: string;
  contract_address?: string;
  transaction_hash?: string;
  network: string;
  chain_id?: number;
}

export default function DeployPage() {
  const { address, isConnected } = useAccount();
  const chainId = useChainId();
  const { contracts } = useContractsStore();
  const { addNotification } = useUIStore();

  const [selectedContract, setSelectedContract] = useState<Contract | null>(null);
  const [selectedNetwork, setSelectedNetwork] = useState(NETWORKS[1]); // Default: Sepolia
  const [constructorArgs, setConstructorArgs] = useState("");
  const [deployment, setDeployment] = useState<Deployment | null>(null);
  const [deploying, setDeploying] = useState(false);
  const [polling, setPolling] = useState(false);
  const [deployHistory, setDeployHistory] = useState<Deployment[]>([]);

  const compiledContracts = contracts.filter((c) => c.is_compiled);

  useEffect(() => {
    deployApi.history().then((res) => setDeployHistory(res.data)).catch(() => {});
  }, []);

  const handleDeploy = async () => {
    if (!selectedContract || !isConnected || !address) {
      addNotification("error", "Connect your wallet and select a compiled contract");
      return;
    }

    setDeploying(true);
    try {
      // Parse constructor args
      let args: unknown[] = [];
      if (constructorArgs.trim()) {
        try { args = JSON.parse(constructorArgs); } catch {
          addNotification("error", "Invalid constructor args JSON");
          return;
        }
      }

      // Initiate deployment record in backend
      const res = await deployApi.initiate({
        contract_id: selectedContract.id,
        network: selectedNetwork.network,
        deployer_address: address,
        constructor_args: args,
      });

      setDeployment({ id: res.data.deployment_id, status: "PENDING", network: selectedNetwork.network });
      addNotification("info", "Deployment initiated! Sign the transaction in MetaMask.");

      // In production: trigger MetaMask transaction here using ethers.js + ABI + bytecode
      // The user would sign the deployment tx and we get the tx hash
      // For this platform, we prompt the user to manually confirm with the tx hash
      addNotification("info", "After signing in MetaMask, copy the tx hash and confirm deployment");

    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      addNotification("error", error.response?.data?.detail || "Deployment failed");
    } finally {
      setDeploying(false);
    }
  };

  const handleConfirmDeployment = async (txHash: string) => {
    if (!deployment) return;
    setPolling(true);
    try {
      await deployApi.confirm(deployment.id, txHash);
      setDeployment({ ...deployment, status: "DEPLOYING", transaction_hash: txHash });
      addNotification("info", "Polling for confirmation...");
      // Poll status
      const poll = setInterval(async () => {
        const res = await deployApi.status(deployment.id);
        const d = res.data;
        setDeployment({ ...deployment, status: d.status, contract_address: d.contract_address, transaction_hash: txHash });
        if (d.status === "SUCCESS" || d.status === "FAILED") {
          clearInterval(poll);
          setPolling(false);
          if (d.status === "SUCCESS") {
            addNotification("success", `Contract deployed at ${d.contract_address}`);
            deployApi.history().then((res) => setDeployHistory(res.data));
          } else {
            addNotification("error", "Deployment transaction failed");
          }
        }
      }, 4000);
    } catch {
      addNotification("error", "Failed to confirm deployment");
      setPolling(false);
    }
  };

  return (
    <div className="flex min-h-screen bg-[hsl(222,47%,6%)]">
      <Sidebar />
      <main className="flex-1 ml-[240px] overflow-y-auto">
        {/* Top bar */}
        <div className="sticky top-0 z-30 flex items-center justify-between px-8 py-4 border-b border-white/10 backdrop-blur-xl bg-black/20">
          <div className="flex items-center gap-3">
            <Rocket className="w-5 h-5 text-green-400" />
            <h1 className="text-xl font-bold text-white">Deploy Contract</h1>
          </div>
          <WalletConnect showNetworkSwitcher />
        </div>

        <div className="p-8 grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main deploy form */}
          <div className="lg:col-span-2 space-y-6">
            {/* Wallet status */}
            {!isConnected && (
              <div className="glass-card border border-yellow-500/30 p-5 flex items-center gap-4">
                <AlertTriangle className="w-6 h-6 text-yellow-400 shrink-0" />
                <div>
                  <p className="text-yellow-300 font-semibold">Wallet not connected</p>
                  <p className="text-slate-400 text-sm">Connect MetaMask to sign and deploy contracts</p>
                </div>
              </div>
            )}

            {/* Contract selection */}
            <div className="glass-card border border-white/10 p-6 space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Shield className="w-5 h-5 text-purple-400" />
                Select Contract
              </h2>
              {compiledContracts.length === 0 ? (
                <div className="text-center py-8 text-slate-500">
                  <p>No compiled contracts available.</p>
                  <a href="/builder" className="text-purple-400 text-sm mt-1 inline-block hover:underline">
                    Go compile a contract →
                  </a>
                </div>
              ) : (
                <div className="space-y-2">
                  {compiledContracts.map((contract) => (
                    <button
                      key={contract.id}
                      onClick={() => setSelectedContract(contract)}
                      className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
                        selectedContract?.id === contract.id
                          ? "bg-purple-500/15 border-purple-500/40 text-white"
                          : "glass border-white/10 text-slate-300 hover:border-white/25"
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-lg bg-purple-500/20 flex items-center justify-center">
                          <Shield className="w-4 h-4 text-purple-400" />
                        </div>
                        <div className="text-left">
                          <p className="font-medium text-sm">{contract.name}</p>
                          <p className="text-xs text-slate-500">{contract.contract_type}</p>
                        </div>
                      </div>
                      <span className="badge-success">Compiled</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Network selection */}
            <div className="glass-card border border-white/10 p-6 space-y-4">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Globe className="w-5 h-5 text-cyan-400" />
                Target Network
              </h2>
              <div className="grid grid-cols-2 gap-3">
                {NETWORKS.map((network) => (
                  <button
                    key={network.chain_id}
                    onClick={() => setSelectedNetwork(network)}
                    className={`p-4 rounded-xl border text-left transition-all ${
                      selectedNetwork.chain_id === network.chain_id
                        ? "bg-cyan-500/15 border-cyan-500/40"
                        : "glass border-white/10 hover:border-white/25"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <p className={`font-medium text-sm ${network.color}`}>{network.name}</p>
                      {network.testnet && (
                        <span className="text-xs badge-info">Testnet</span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500">Chain ID: {network.chain_id}</p>
                  </button>
                ))}
              </div>
            </div>

            {/* Constructor args */}
            {selectedContract && (
              <div className="glass-card border border-white/10 p-6">
                <h2 className="text-lg font-bold text-white mb-2">Constructor Arguments</h2>
                <p className="text-slate-400 text-sm mb-3">
                  Enter arguments as JSON array, e.g. <code className="mono bg-black/30 px-1 rounded">["0xAddress", 1000000]</code>
                </p>
                <textarea
                  value={constructorArgs}
                  onChange={(e) => setConstructorArgs(e.target.value)}
                  placeholder='["0x...", 1000000]'
                  rows={3}
                  className="input-field text-sm mono"
                />
              </div>
            )}

            {/* Deploy button */}
            <button
              onClick={handleDeploy}
              disabled={deploying || !selectedContract || !isConnected}
              className="btn-primary w-full justify-center text-base py-4 disabled:opacity-40"
            >
              {deploying ? (
                <><Loader2 className="w-5 h-5 animate-spin" /> Initiating Deployment…</>
              ) : (
                <><Rocket className="w-5 h-5" /> Deploy to {selectedNetwork.name}</>
              )}
            </button>

            {/* Confirm with tx hash */}
            {deployment && deployment.status === "PENDING" && (
              <div className="glass-card border border-yellow-500/30 p-5 space-y-3">
                <p className="text-yellow-300 font-semibold">Confirm Deployment</p>
                <p className="text-slate-400 text-sm">After signing in MetaMask, paste the transaction hash:</p>
                <div className="flex gap-3">
                  <input
                    type="text"
                    placeholder="0x..."
                    className="input-field text-sm flex-1"
                    onKeyDown={(e) => {
                      if (e.key === "Enter") handleConfirmDeployment((e.target as HTMLInputElement).value);
                    }}
                  />
                  <button
                    className="btn-primary px-4 py-2 text-sm"
                    onClick={(e) => {
                      const input = (e.currentTarget.previousSibling as HTMLInputElement);
                      handleConfirmDeployment(input.value);
                    }}
                  >
                    {polling ? <Loader2 className="w-4 h-4 animate-spin" /> : "Confirm"}
                  </button>
                </div>
              </div>
            )}

            {/* Deployment result */}
            {deployment && (deployment.status === "SUCCESS" || deployment.status === "FAILED") && (
              <div className={`glass-card border p-5 space-y-3 ${
                deployment.status === "SUCCESS" ? "border-green-500/30" : "border-red-500/30"
              }`}>
                <div className="flex items-center gap-3">
                  {deployment.status === "SUCCESS" ? (
                    <CheckCircle2 className="w-6 h-6 text-green-400" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-400" />
                  )}
                  <p className="font-semibold text-white">
                    {deployment.status === "SUCCESS" ? "Deployment Successful!" : "Deployment Failed"}
                  </p>
                </div>
                {deployment.contract_address && (
                  <div className="space-y-1">
                    <p className="text-xs text-slate-400">Contract Address</p>
                    <div className="flex items-center gap-2">
                      <p className="text-sm mono text-green-300">{deployment.contract_address}</p>
                      <button onClick={() => navigator.clipboard.writeText(deployment.contract_address!)}>
                        <Copy className="w-3.5 h-3.5 text-slate-400 hover:text-white" />
                      </button>
                      <a
                        href={getExplorerUrl(selectedNetwork.chain_id, deployment.contract_address, "address")}
                        target="_blank"
                        className="text-slate-400 hover:text-white"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                )}
                {deployment.transaction_hash && (
                  <div className="space-y-1">
                    <p className="text-xs text-slate-400">Transaction Hash</p>
                    <div className="flex items-center gap-2">
                      <p className="text-xs mono text-slate-300">
                        {deployment.transaction_hash.slice(0, 24)}…{deployment.transaction_hash.slice(-8)}
                      </p>
                      <a
                        href={getExplorerUrl(selectedNetwork.chain_id, deployment.transaction_hash)}
                        target="_blank"
                        className="text-slate-400 hover:text-white"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sidebar — deployment history */}
          <div className="space-y-4">
            <div className="glass-card border border-white/10 p-5">
              <h3 className="font-bold text-white mb-4">Deployment History</h3>
              {deployHistory.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-6">No deployments yet</p>
              ) : (
                <div className="space-y-2">
                  {deployHistory.slice(0, 8).map((d) => (
                    <div key={d.id} className="flex items-start justify-between py-2 border-b border-white/5 last:border-0">
                      <div>
                        <p className="text-sm text-slate-300">{d.network}</p>
                        {d.contract_address && (
                          <p className="text-xs mono text-slate-500">
                            {d.contract_address.slice(0, 8)}…
                          </p>
                        )}
                      </div>
                      <span className={`text-xs ${
                        d.status === "SUCCESS" ? "badge-success" :
                        d.status === "FAILED" ? "badge-danger" :
                        "badge-warning"
                      }`}>
                        {d.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="glass-card border border-blue-500/20 p-5 space-y-2">
              <div className="flex items-center gap-2 text-blue-400 mb-3">
                <Info className="w-4 h-4" />
                <p className="font-semibold text-sm">Deployment Tips</p>
              </div>
              {[
                "Always test on testnet first",
                "Audit your contract before mainnet",
                "Keep deployment tx hash safe",
                "Verify source code on Etherscan",
              ].map((tip) => (
                <p key={tip} className="text-xs text-slate-400 flex items-start gap-2">
                  <span className="text-blue-400 mt-0.5">•</span> {tip}
                </p>
              ))}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
