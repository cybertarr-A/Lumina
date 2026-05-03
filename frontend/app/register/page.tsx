"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { FileCode2, Loader2, Eye, EyeOff, CheckCircle2 } from "lucide-react";
import { authApi } from "@/lib/api";
import { useUIStore } from "@/lib/store";
import { useRouter } from "next/navigation";

const PASSWORD_REQUIREMENTS = [
  { label: "At least 8 characters", test: (p: string) => p.length >= 8 },
  { label: "Contains a letter", test: (p: string) => /[a-zA-Z]/.test(p) },
  { label: "Contains a number", test: (p: string) => /\d/.test(p) },
];

export default function RegisterPage() {
  const router = useRouter();
  const { addNotification } = useUIStore();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await authApi.register({ email, username, password });
      addNotification("success", "Account created! Please sign in.");
      router.push("/login");
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      addNotification("error", error.response?.data?.detail || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[hsl(222,47%,6%)] relative overflow-hidden">
      <div className="absolute top-1/4 right-1/4 w-72 h-72 bg-purple-600/15 rounded-full blur-3xl" />
      <div className="absolute bottom-1/4 left-1/4 w-72 h-72 bg-cyan-600/15 rounded-full blur-3xl" />

      <motion.div
        className="w-full max-w-md p-8 glass-card border border-white/15 mx-4"
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center">
            <FileCode2 className="w-6 h-6 text-white" />
          </div>
          <div>
            <p className="font-bold text-white">Lumina</p>
            <p className="text-xs text-slate-400">Create your account</p>
          </div>
        </div>

        <form onSubmit={handleRegister} className="space-y-4">
          <div>
            <label className="text-sm text-slate-400 block mb-1.5">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="input-field"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 block mb-1.5">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="web3dev"
              required
              minLength={3}
              maxLength={50}
              pattern="[a-zA-Z0-9_-]+"
              className="input-field"
            />
          </div>
          <div>
            <label className="text-sm text-slate-400 block mb-1.5">Password</label>
            <div className="relative">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={8}
                className="input-field pr-12"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {password && (
              <div className="mt-2 space-y-1">
                {PASSWORD_REQUIREMENTS.map((req) => (
                  <div key={req.label} className={`flex items-center gap-2 text-xs ${req.test(password) ? "text-green-400" : "text-slate-500"}`}>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    {req.label}
                  </div>
                ))}
              </div>
            )}
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full justify-center py-3 mt-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Create Account"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-6">
          Already have an account?{" "}
          <Link href="/login" className="text-purple-400 hover:text-purple-300 font-medium">
            Sign in
          </Link>
        </p>
      </motion.div>
    </div>
  );
}
