"use client";

import { useUIStore } from "@/lib/store";
import { CheckCircle, XCircle, Info, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export function Toaster() {
  const { notifications, removeNotification } = useUIStore();

  const icons = {
    success: <CheckCircle className="w-5 h-5 text-green-400 shrink-0" />,
    error: <XCircle className="w-5 h-5 text-red-400 shrink-0" />,
    info: <Info className="w-5 h-5 text-blue-400 shrink-0" />,
  };

  const borderColors = {
    success: "border-green-500/30",
    error: "border-red-500/30",
    info: "border-blue-500/30",
  };

  return (
    <div className="fixed bottom-6 right-6 z-[100] flex flex-col gap-3 max-w-sm">
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.id}
            initial={{ opacity: 0, x: 50, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 50, scale: 0.95 }}
            className={`glass-card border ${borderColors[n.type]} p-4 flex items-start gap-3 min-w-[280px]`}
          >
            {icons[n.type]}
            <p className="text-sm text-slate-200 flex-1 leading-snug">{n.message}</p>
            <button
              onClick={() => removeNotification(n.id)}
              className="text-slate-500 hover:text-white transition-colors shrink-0"
            >
              <X className="w-4 h-4" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
