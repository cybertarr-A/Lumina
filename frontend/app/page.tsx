"use client";

import { useEffect, useRef } from "react";
import { ConnectButton } from "@rainbow-me/rainbowkit";
import { motion } from "framer-motion";
import Link from "next/link";
import {
  Code2, Cpu, Shield, Zap, ArrowRight, ExternalLink,
  FileCode2, Layers, Rocket, Activity, Lock, Globe
} from "lucide-react";

const FEATURES = [
  {
    icon: Cpu,
    title: "AI Contract Generation",
    description: "Describe your contract in plain English. Our Groq-powered AI generates production-ready Solidity instantly.",
    gradient: "from-purple-500/20 to-blue-500/20",
    border: "border-purple-500/30",
  },
  {
    icon: Code2,
    title: "Monaco Code Editor",
    description: "Full-featured editor with Solidity IntelliSense, syntax highlighting, and real-time error detection.",
    gradient: "from-blue-500/20 to-cyan-500/20",
    border: "border-blue-500/30",
  },
  {
    icon: Shield,
    title: "Security Audit Engine",
    description: "Automated Slither + Mythril analysis. Detects reentrancy, overflow, access control flaws with fix suggestions.",
    gradient: "from-red-500/20 to-orange-500/20",
    border: "border-red-500/30",
  },
  {
    icon: Rocket,
    title: "One-Click Deployment",
    description: "Deploy to Ethereum, Polygon, or BSC with MetaMask. Real-time status, transaction hash, contract address.",
    gradient: "from-green-500/20 to-emerald-500/20",
    border: "border-green-500/30",
  },
  {
    icon: Layers,
    title: "Multi-Standard Support",
    description: "ERC-20, ERC-721, ERC-1155, DAO governance, Staking rewards, DeFi liquidity pools — all production-grade.",
    gradient: "from-yellow-500/20 to-orange-500/20",
    border: "border-yellow-500/30",
  },
  {
    icon: Activity,
    title: "Testing Sandbox",
    description: "Local Hardhat blockchain simulation, gas estimation, transaction tracing, and unit test runner.",
    gradient: "from-pink-500/20 to-purple-500/20",
    border: "border-pink-500/30",
  },
];

const STATS = [
  { value: "6+", label: "Contract Standards" },
  { value: "3", label: "Supported Chains" },
  { value: "100%", label: "OpenZeppelin Based" },
  { value: "AI", label: "Powered Generation" },
];

const CONTRACT_TYPES = ["ERC-20", "ERC-721", "ERC-1155", "DAO", "Staking", "DeFi"];

export default function HomePage() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;

    // Particle system for blockchain visualization
    const particles: Array<{
      x: number; y: number; vx: number; vy: number; size: number; opacity: number; color: string;
    }> = [];

    const COLORS = ["#9333ea", "#06b6d4", "#8b5cf6", "#0ea5e9"];
    for (let i = 0; i < 60; i++) {
      particles.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        vx: (Math.random() - 0.5) * 0.5,
        vy: (Math.random() - 0.5) * 0.5,
        size: Math.random() * 2 + 1,
        opacity: Math.random() * 0.6 + 0.2,
        color: COLORS[Math.floor(Math.random() * COLORS.length)],
      });
    }

    let animId: number;
    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Draw connections
      particles.forEach((p, i) => {
        particles.slice(i + 1).forEach((q) => {
          const dx = p.x - q.x;
          const dy = p.y - q.y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 150) {
            ctx.beginPath();
            ctx.moveTo(p.x, p.y);
            ctx.lineTo(q.x, q.y);
            ctx.strokeStyle = `rgba(147, 51, 234, ${0.15 * (1 - dist / 150)})`;
            ctx.lineWidth = 0.5;
            ctx.stroke();
          }
        });
      });

      // Draw particles
      particles.forEach((p) => {
        p.x += p.vx;
        p.y += p.vy;
        if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
        if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color + Math.floor(p.opacity * 255).toString(16).padStart(2, "0");
        ctx.fill();
      });

      animId = requestAnimationFrame(animate);
    };

    animate();
    const handleResize = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);
    return () => { cancelAnimationFrame(animId); window.removeEventListener("resize", handleResize); };
  }, []);

  return (
    <main className="relative min-h-screen overflow-hidden">
      {/* Animated background */}
      <canvas ref={canvasRef} className="fixed inset-0 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-br from-[hsl(222,47%,6%)] via-[hsl(240,30%,8%)] to-[hsl(222,47%,6%)] z-0" />

      {/* Glow orbs */}
      <div className="fixed top-1/4 left-1/4 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl pointer-events-none z-0" />
      <div className="fixed bottom-1/4 right-1/4 w-96 h-96 bg-cyan-600/10 rounded-full blur-3xl pointer-events-none z-0" />

      {/* ── Navigation ─────────────────────────────────────────────────── */}
      <nav className="relative z-50 flex items-center justify-between px-6 py-4 border-b border-white/10 backdrop-blur-xl bg-black/20">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <FileCode2 className="w-5 h-5 text-white" />
          </div>
          <span className="text-xl font-bold gradient-text">Lumina</span>
        </div>
        <div className="hidden md:flex items-center gap-6">
          {["Features", "Docs", "Pricing"].map((item) => (
            <a key={item} href="#" className="text-sm text-slate-400 hover:text-white transition-colors">
              {item}
            </a>
          ))}
        </div>
        <div className="flex items-center gap-3">
          <ConnectButton />
          <Link href="/login" className="btn-ghost text-sm">Sign In</Link>
          <Link href="/register" className="btn-primary text-sm px-4 py-2">Get Started</Link>
        </div>
      </nav>

      {/* ── Hero ───────────────────────────────────────────────────────── */}
      <section className="relative z-10 flex flex-col items-center justify-center text-center px-6 pt-32 pb-24">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-purple-500/15 border border-purple-500/30 text-purple-300 text-sm mb-8">
            <Zap className="w-3.5 h-3.5" />
            AI-Powered Smart Contract Generator — Production Ready
          </div>

          <h1 className="text-5xl md:text-7xl font-black leading-tight mb-6">
            <span className="text-white">Build Smarter</span>
            <br />
            <span className="gradient-text">Contracts Faster</span>
          </h1>

          <p className="text-lg md:text-xl text-slate-400 max-w-2xl mb-10 leading-relaxed">
            Generate, audit, and deploy production-grade Solidity smart contracts
            with AI. From ERC-20 tokens to complex DAO governance — in minutes, not days.
          </p>

          <div className="flex flex-wrap items-center justify-center gap-4 mb-16">
            <Link href="/dashboard" className="btn-primary text-base px-8 py-4">
              Launch App
              <ArrowRight className="w-5 h-5" />
            </Link>
            <a
              href="https://github.com"
              target="_blank"
              className="btn-ghost text-base px-8 py-4 glass border border-white/15"
            >
              <ExternalLink className="w-5 h-5" />
              View on GitHub
            </a>
          </div>

          {/* Contract type pills */}
          <div className="flex flex-wrap items-center justify-center gap-2">
            {CONTRACT_TYPES.map((type) => (
              <span
                key={type}
                className="px-4 py-1.5 rounded-full text-sm font-medium glass border border-white/10 text-slate-300"
              >
                {type}
              </span>
            ))}
          </div>
        </motion.div>

        {/* Stats */}
        <motion.div
          className="grid grid-cols-2 md:grid-cols-4 gap-6 mt-20 w-full max-w-3xl"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3, duration: 0.6 }}
        >
          {STATS.map((stat) => (
            <div key={stat.label} className="glass-card p-6 text-center">
              <div className="text-3xl font-black gradient-text mb-1">{stat.value}</div>
              <div className="text-sm text-slate-400">{stat.label}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* ── Features Grid ──────────────────────────────────────────────── */}
      <section className="relative z-10 px-6 py-24 max-w-7xl mx-auto" id="features">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-black text-white mb-4">
            Everything you need to build
            <span className="gradient-text"> Web3 contracts</span>
          </h2>
          <p className="text-slate-400 text-lg max-w-xl mx-auto">
            A complete platform from idea to deployed contract, with enterprise-grade security and tooling.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.title}
              className={`glass-card p-6 glow-ring border ${f.border}`}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.1, duration: 0.5 }}
            >
              <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${f.gradient} flex items-center justify-center mb-4 border ${f.border}`}>
                <f.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-lg font-bold text-white mb-2">{f.title}</h3>
              <p className="text-slate-400 text-sm leading-relaxed">{f.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────────────────────────── */}
      <section className="relative z-10 px-6 py-24">
        <div className="max-w-4xl mx-auto glass-card p-12 text-center glow-ring" style={{ borderColor: "rgba(147, 51, 234, 0.4)" }}>
          <div className="flex justify-center mb-6">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center animate-pulse-glow">
              <Lock className="w-8 h-8 text-white" />
            </div>
          </div>
          <h2 className="text-4xl font-black text-white mb-4">
            Ready to build your <span className="gradient-text">smart contract</span>?
          </h2>
          <p className="text-slate-400 mb-8 text-lg">
            Join developers building the future of Web3 with AI-assisted smart contract generation.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4">
            <Link href="/register" className="btn-primary text-base px-10 py-4">
              Start Building Free
              <ArrowRight className="w-5 h-5" />
            </Link>
            <Link href="/dashboard" className="btn-ghost text-base px-8 py-4 glass border border-white/15">
              <Globe className="w-5 h-5" />
              Explore Dashboard
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/10 px-6 py-8 text-center text-slate-500 text-sm">
        <p>© 2025 SmartContractGen · Built with ❤️ for Web3 developers</p>
      </footer>
    </main>
  );
}
