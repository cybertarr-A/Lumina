import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Web3Providers } from "./providers";
import { Toaster } from "@/components/ui/Toaster";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "SmartContractGen — AI-Powered Smart Contract Platform",
  description:
    "Generate, compile, audit, and deploy production-grade Solidity smart contracts with AI. Supports ERC-20, ERC-721, ERC-1155, DAO, Staking, and DeFi contracts.",
  keywords: ["smart contract", "solidity", "blockchain", "ethereum", "web3", "AI", "DeFi"],
  openGraph: {
    title: "SmartContractGen — AI-Powered Smart Contract Platform",
    description: "Generate and deploy Solidity smart contracts with AI assistance",
    type: "website",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans bg-background text-foreground antialiased`}>
        <Web3Providers>
          {children}
          <Toaster />
        </Web3Providers>
      </body>
    </html>
  );
}
