"use client";

/**
 * TaskTracker — Real-time Celery job progress component.
 * Polls GET /tasks/{task_id} and renders live status with animated progress bar.
 *
 * Usage:
 *   <TaskTracker taskId={taskId} label="Generating contract..." onSuccess={handleResult} />
 */
import React, { useEffect, useRef, useState } from "react";
import { tasksApi, TaskResult } from "@/lib/api";

interface TaskTrackerProps {
  taskId: string | null;
  label?: string;
  onSuccess?: (result: unknown) => void;
  onError?: (error: string) => void;
  onComplete?: () => void;
  intervalMs?: number;
  timeoutMs?: number;
  className?: string;
}

type Phase = "idle" | "pending" | "running" | "success" | "error";

const STEP_LABELS: Record<string, string> = {
  generating: "Generating contract with AI...",
  scanning: "Scanning for vulnerabilities...",
  saving: "Saving contract...",
  compiling: "Compiling Solidity...",
  analyzing: "Running security analysis...",
  scoring: "Calculating risk score...",
  polling: "Waiting for on-chain confirmation...",
};

export default function TaskTracker({
  taskId,
  label = "Processing...",
  onSuccess,
  onError,
  onComplete,
  intervalMs = 2000,
  timeoutMs = 120000,
  className = "",
}: TaskTrackerProps) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState<string>("");
  const [errorMsg, setErrorMsg] = useState<string>("");
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const startRef = useRef<number>(Date.now());

  useEffect(() => {
    if (!taskId) {
      setPhase("idle");
      return;
    }

    setPhase("pending");
    setProgress(0);
    setErrorMsg("");
    startRef.current = Date.now();

    const poll = async () => {
      // Timeout guard
      if (Date.now() - startRef.current > timeoutMs) {
        clearInterval(intervalRef.current!);
        setPhase("error");
        setErrorMsg("Task timed out. Please try again.");
        onError?.("Timeout");
        onComplete?.();
        return;
      }

      try {
        const { data }: { data: TaskResult } = await tasksApi.getStatus(taskId);

        setProgress(data.progress ?? (data.status === "PENDING" ? 5 : progress));
        setStep(data.step ?? "");

        if (data.status === "STARTED") {
          setPhase("running");
        } else if (data.status === "SUCCESS") {
          clearInterval(intervalRef.current!);
          setPhase("success");
          setProgress(100);
          onSuccess?.(data.result);
          onComplete?.();
        } else if (data.status === "FAILURE" || data.status === "REVOKED") {
          clearInterval(intervalRef.current!);
          setPhase("error");
          setErrorMsg(data.error ?? "Task failed unexpectedly.");
          onError?.(data.error ?? "Unknown error");
          onComplete?.();
        }
      } catch {
        // Network error during polling — keep retrying until timeout
      }
    };

    poll(); // Immediate first check
    intervalRef.current = setInterval(poll, intervalMs);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId]);

  if (phase === "idle" || !taskId) return null;

  const stepLabel = step ? STEP_LABELS[step] || step : label;

  return (
    <div className={`task-tracker ${className}`} role="status" aria-live="polite">
      <div className="task-tracker__header">
        {phase === "running" || phase === "pending" ? (
          <span className="task-tracker__spinner" aria-hidden="true" />
        ) : phase === "success" ? (
          <span className="task-tracker__icon task-tracker__icon--success" aria-hidden="true">✓</span>
        ) : (
          <span className="task-tracker__icon task-tracker__icon--error" aria-hidden="true">✕</span>
        )}
        <span className="task-tracker__label">
          {phase === "success" ? "Complete!" : phase === "error" ? "Failed" : stepLabel}
        </span>
        <span className="task-tracker__progress-text">{phase !== "error" ? `${progress}%` : ""}</span>
      </div>

      <div className="task-tracker__bar-track" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
        <div
          className={`task-tracker__bar-fill task-tracker__bar-fill--${phase}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      {phase === "error" && (
        <p className="task-tracker__error">{errorMsg}</p>
      )}

      <style jsx>{`
        .task-tracker {
          width: 100%;
          padding: 1rem 1.25rem;
          background: rgba(255, 255, 255, 0.04);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 12px;
          backdrop-filter: blur(12px);
        }

        .task-tracker__header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.75rem;
          font-size: 0.875rem;
          color: rgba(255, 255, 255, 0.85);
        }

        .task-tracker__spinner {
          display: inline-block;
          width: 16px;
          height: 16px;
          border: 2px solid rgba(139, 92, 246, 0.3);
          border-top-color: #8b5cf6;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          flex-shrink: 0;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .task-tracker__icon {
          width: 16px;
          height: 16px;
          display: inline-flex;
          align-items: center;
          justify-content: center;
          border-radius: 50%;
          font-size: 10px;
          font-weight: 700;
          flex-shrink: 0;
        }

        .task-tracker__icon--success {
          background: rgba(34, 197, 94, 0.2);
          color: #22c55e;
          border: 1px solid rgba(34, 197, 94, 0.4);
        }

        .task-tracker__icon--error {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
          border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .task-tracker__label {
          flex: 1;
          font-weight: 500;
        }

        .task-tracker__progress-text {
          font-size: 0.75rem;
          color: rgba(255, 255, 255, 0.4);
          font-variant-numeric: tabular-nums;
        }

        .task-tracker__bar-track {
          width: 100%;
          height: 4px;
          background: rgba(255, 255, 255, 0.06);
          border-radius: 2px;
          overflow: hidden;
        }

        .task-tracker__bar-fill {
          height: 100%;
          border-radius: 2px;
          transition: width 0.4s ease;
        }

        .task-tracker__bar-fill--pending,
        .task-tracker__bar-fill--running {
          background: linear-gradient(90deg, #8b5cf6, #06b6d4);
          animation: shimmer 1.5s ease-in-out infinite;
          background-size: 200% 100%;
        }

        @keyframes shimmer {
          0%   { background-position: 200% center; }
          100% { background-position: -200% center; }
        }

        .task-tracker__bar-fill--success {
          background: linear-gradient(90deg, #22c55e, #10b981);
          animation: none;
        }

        .task-tracker__bar-fill--error {
          background: #ef4444;
          animation: none;
        }

        .task-tracker__error {
          margin-top: 0.5rem;
          font-size: 0.8rem;
          color: #f87171;
        }
      `}</style>
    </div>
  );
}
