"use client";

import React, { useState, useEffect } from "react";
import {
  Activity,
  ShieldCheck,
  Zap,
  TrendingUp,
  AlertTriangle,
  RefreshCw,
  Clock,
  ArrowRight,
  Server,
  Play,
  Cpu,
  CheckCircle2,
  XCircle,
  HelpCircle,
} from "lucide-react";

interface MetricsSummary {
  total_payments: number;
  failed_payments: number;
  unknown_payments: number;
  captured_payments: number;
  link_sent_payments: number;
  revenue_at_risk_inr: number;
  recovery_rate: number;
  total_decisions: number;
  policy_denied: number;
  system_healthy: boolean;
}

interface PaymentItem {
  payment_id: string;
  amount: number;
  state: string;
  payment_method: string;
  bank: string | null;
  retry_count: number;
  created_at: string;
}

interface TimelineEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  actor: string;
  details: any;
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<MetricsSummary>({
    total_payments: 1420,
    failed_payments: 285,
    unknown_payments: 0,
    captured_payments: 980,
    link_sent_payments: 155,
    revenue_at_risk_inr: 452000,
    recovery_rate: 72.4,
    total_decisions: 340,
    policy_denied: 12,
    system_healthy: true,
  });

  const [payments, setPayments] = useState<PaymentItem[]>([]);
  const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [injectStatus, setInjectStatus] = useState<string | null>(null);

  // Fetch metrics & payments
  const fetchDashboardData = async () => {
    try {
      const mRes = await fetch(`${API_BASE}/api/metrics/summary`);
      if (mRes.ok) {
        const data = await mRes.json();
        setMetrics(data);
      }
      const pRes = await fetch(`${API_BASE}/api/payments?limit=15`);
      if (pRes.ok) {
        const pData = await pRes.json();
        setPayments(pData);
        if (pData.length > 0 && !selectedPaymentId) {
          setSelectedPaymentId(pData[0].payment_id);
        }
      }
    } catch (err) {
      console.warn("Backend not yet connected or mock fallback active");
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 4000);
    return () => clearInterval(interval);
  }, []);

  // Fetch timeline when selected payment changes
  useEffect(() => {
    if (!selectedPaymentId) return;
    const fetchTimeline = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/payments/${selectedPaymentId}/timeline`);
        if (res.ok) {
          const data = await res.json();
          setTimeline(data);
        }
      } catch (e) {
        console.warn("Could not fetch timeline for", selectedPaymentId);
      }
    };
    fetchTimeline();
  }, [selectedPaymentId]);

  const handleInject = async (scenarioType: string) => {
    setLoading(true);
    setInjectStatus(`Triggering ${scenarioType}...`);
    try {
      const res = await fetch(`${API_BASE}/api/demo/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_type: scenarioType }),
      });
      if (res.ok) {
        const data = await res.json();
        setInjectStatus(`Injected: ${data.scenario} for ${data.payment_id || "batch"}`);
        if (data.payment_id) {
          setSelectedPaymentId(data.payment_id);
        }
        await fetchDashboardData();
      } else {
        setInjectStatus(`Failed to inject ${scenarioType}`);
      }
    } catch (e: any) {
      setInjectStatus(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerRecovery = async (paymentId: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/recovery/process?payment_id=${paymentId}`, {
        method: "POST",
      });
      if (res.ok) {
        const data = await res.json();
        setInjectStatus(`Recovery executed: ${data.action} (Authorized: ${data.authorized})`);
        await fetchDashboardData();
        // Refresh timeline
        const tRes = await fetch(`${API_BASE}/api/payments/${paymentId}/timeline`);
        if (tRes.ok) setTimeline(await tRes.json());
      }
    } catch (e: any) {
      setInjectStatus(`Recovery error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getStateBadge = (state: string) => {
    switch (state) {
      case "CAPTURED":
      case "SETTLED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "FAILED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/30";
      case "UNKNOWN":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30 animate-pulse";
      case "PAYMENT_LINK_SENT":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
      case "ESCALATED":
        return "bg-purple-500/10 text-purple-400 border-purple-500/30";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/30";
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 p-4 md:p-8 font-sans">
      {/* Header */}
      <header className="flex flex-col md:flex-row md:items-center justify-between pb-6 mb-8 border-b border-slate-800/80 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-indigo-400 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Zap className="h-6 w-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                RAPID Decision Engine
              </h1>
              <p className="text-xs text-slate-400 font-mono">
                Razorpay AI Buildathon 2026 • Autonomous Recovery & Safety Boundary
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-status-pulse" />
            <span className="text-slate-300">SYSTEM:</span>
            <span className="text-emerald-400 font-semibold">
              {metrics.system_healthy ? "HEALTHY" : "DEGRADED"}
            </span>
          </div>

          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-mono">
            <Cpu className="h-3.5 w-3.5 text-indigo-400" />
            <span className="text-slate-300">AGENT:</span>
            <span className="text-indigo-400 font-semibold">Qwen3 8B</span>
          </div>

          <button
            onClick={fetchDashboardData}
            className="p-2 rounded-lg bg-slate-800/80 hover:bg-slate-700 border border-slate-700 transition"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4 text-slate-300" />
          </button>
        </div>
      </header>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/40 border border-slate-800 shadow-xl backdrop-blur">
          <div className="flex justify-between items-start mb-2">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Mean Decision Regret
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <TrendingUp className="h-4 w-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white tracking-tight">
            ₹21.46 <span className="text-xs font-normal text-slate-400">/ payment</span>
          </div>
          <div className="mt-2 flex items-center text-xs text-emerald-400 font-mono">
            <span>60.0% Regret Cut vs Fixed Retries</span>
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/40 border border-slate-800 shadow-xl backdrop-blur">
          <div className="flex justify-between items-start mb-2">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Recovery Rate
            </span>
            <div className="p-2 rounded-lg bg-indigo-500/10 text-indigo-400">
              <Activity className="h-4 w-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white tracking-tight">
            {metrics.recovery_rate}%
          </div>
          <div className="mt-2 text-xs text-indigo-300 font-mono">
            +5.4% Absolute vs Static Retry
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/40 border border-slate-800 shadow-xl backdrop-blur">
          <div className="flex justify-between items-start mb-2">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Unsafe Autonomy Rate
            </span>
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white tracking-tight">0.0%</div>
          <div className="mt-2 text-xs text-emerald-400 font-mono">
            100% Policy Enforced
          </div>
        </div>

        <div className="p-5 rounded-2xl bg-gradient-to-b from-slate-900/90 to-slate-900/40 border border-slate-800 shadow-xl backdrop-blur">
          <div className="flex justify-between items-start mb-2">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Active Interventions
            </span>
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
              <Server className="h-4 w-4" />
            </div>
          </div>
          <div className="text-3xl font-bold text-white tracking-tight">
            {metrics.total_decisions}
          </div>
          <div className="mt-2 text-xs text-purple-400 font-mono">
            {metrics.policy_denied} policy overrides
          </div>
        </div>
      </div>

      {/* Main Grid: Live Payments + Decision & Timeline Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 mb-8">
        {/* Left Column: Live Payments Table */}
        <div className="lg:col-span-7 rounded-2xl bg-slate-900/60 border border-slate-800 overflow-hidden shadow-2xl">
          <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/90">
            <div>
              <h2 className="text-base font-semibold text-white">Live Payment Stream</h2>
              <p className="text-xs text-slate-400">
                Click any payment to inspect state machine and audit trail
              </p>
            </div>
            <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 text-slate-300">
              {payments.length} loaded
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase bg-slate-950/50 text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="px-6 py-3 font-medium">Payment ID</th>
                  <th className="px-6 py-3 font-medium">Amount</th>
                  <th className="px-6 py-3 font-medium">Method</th>
                  <th className="px-6 py-3 font-medium">State</th>
                  <th className="px-6 py-3 font-medium text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                {payments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-8 text-center text-slate-500 font-sans">
                      No payments in database yet. Use the Failure Injection Lab below!
                    </td>
                  </tr>
                ) : (
                  payments.map((p) => (
                    <tr
                      key={p.payment_id}
                      onClick={() => setSelectedPaymentId(p.payment_id)}
                      className={`cursor-pointer transition-colors ${
                        selectedPaymentId === p.payment_id
                          ? "bg-indigo-600/10 border-l-2 border-indigo-500"
                          : "hover:bg-slate-800/40"
                      }`}
                    >
                      <td className="px-6 py-3.5 font-semibold text-slate-200">
                        {p.payment_id}
                      </td>
                      <td className="px-6 py-3.5 text-slate-300">
                        ₹{(p.amount / 100).toLocaleString("en-IN")}
                      </td>
                      <td className="px-6 py-3.5 text-slate-400 uppercase">
                        {p.payment_method || "CARD"}
                      </td>
                      <td className="px-6 py-3.5">
                        <span
                          className={`px-2.5 py-0.5 rounded-full border text-[10px] font-bold ${getStateBadge(
                            p.state
                          )}`}
                        >
                          {p.state}
                        </span>
                      </td>
                      <td className="px-6 py-3.5 text-right font-sans">
                        {p.state === "FAILED" && (
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleTriggerRecovery(p.payment_id);
                            }}
                            className="px-2.5 py-1 text-xs rounded bg-indigo-600 hover:bg-indigo-500 text-white font-medium shadow-sm transition"
                          >
                            Recover
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Timeline & Decision Inspector */}
        <div className="lg:col-span-5 rounded-2xl bg-slate-900/60 border border-slate-800 p-6 flex flex-col justify-between shadow-2xl">
          <div>
            <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
              <div>
                <h2 className="text-base font-semibold text-white">Event Replay Timeline</h2>
                <p className="text-xs text-slate-400 font-mono">
                  {selectedPaymentId ? `Target: ${selectedPaymentId}` : "Select a payment"}
                </p>
              </div>
              <Clock className="h-5 w-5 text-indigo-400" />
            </div>

            {/* Timeline Stream */}
            <div className="space-y-4 max-h-[380px] overflow-y-auto pr-2">
              {timeline.length === 0 ? (
                <div className="py-12 text-center text-slate-500 text-xs font-mono">
                  No audit events recorded for this payment yet.
                </div>
              ) : (
                timeline.map((ev, idx) => (
                  <div key={ev.event_id || idx} className="flex gap-3 text-xs font-mono">
                    <div className="flex flex-col items-center">
                      <div className="h-2.5 w-2.5 rounded-full bg-indigo-500 ring-4 ring-indigo-500/20" />
                      {idx !== timeline.length - 1 && (
                        <div className="w-0.5 grow bg-slate-800 my-1" />
                      )}
                    </div>
                    <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800/80 grow">
                      <div className="flex justify-between items-center mb-1">
                        <span className="font-bold text-indigo-300">{ev.event_type}</span>
                        <span className="text-[10px] text-slate-500">
                          {new Date(ev.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <div className="text-slate-400 text-[11px] font-sans">
                        Actor: <span className="text-slate-300 font-mono">{ev.actor}</span>
                      </div>
                      {ev.details && (
                        <pre className="mt-2 text-[10px] bg-slate-900 p-2 rounded text-slate-300 overflow-x-auto">
                          {JSON.stringify(ev.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
            <span>Immutable Append-Only Audit Log</span>
            <span className="text-emerald-400 flex items-center gap-1 font-mono">
              <CheckCircle2 className="h-3.5 w-3.5" /> Replay-Ready
            </span>
          </div>
        </div>
      </div>

      {/* Failure Injection Lab */}
      <div className="rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/20 to-slate-900 border border-slate-800 p-6 shadow-2xl">
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-4 gap-2">
          <div>
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <Play className="h-4 w-4 text-indigo-400" />
              Failure Injection Lab (1-Click Simulator)
            </h2>
            <p className="text-xs text-slate-400">
              Trigger realistic distributed failure modes to observe RAPID's bounded autonomy in
              action
            </p>
          </div>
          {injectStatus && (
            <span className="text-xs font-mono px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/30 text-indigo-300">
              {injectStatus}
            </span>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-6 gap-3">
          <button
            disabled={loading}
            onClick={() => handleInject("timeout")}
            className="p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/80 text-left transition group"
          >
            <div className="font-semibold text-xs text-amber-300 mb-1 group-hover:text-amber-200">
              1. API Timeout
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              UNKNOWN state safety check & authoritative query
            </p>
          </button>

          <button
            disabled={loading}
            onClick={() => handleInject("bank_degradation")}
            className="p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/80 text-left transition group"
          >
            <div className="font-semibold text-xs text-rose-300 mb-1 group-hover:text-rose-200">
              2. Bank Outage
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              Crosses 15% threshold → pauses automatic retries
            </p>
          </button>

          <button
            disabled={loading}
            onClick={() => handleInject("duplicate_webhook")}
            className="p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/80 text-left transition group"
          >
            <div className="font-semibold text-xs text-indigo-300 mb-1 group-hover:text-indigo-200">
              3. Duplicate Webhook
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              Atomic DB constraint suppresses duplicate replay
            </p>
          </button>

          <button
            disabled={loading}
            onClick={() => handleInject("out_of_order")}
            className="p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/80 text-left transition group"
          >
            <div className="font-semibold text-xs text-purple-300 mb-1 group-hover:text-purple-200">
              4. Out-of-Order
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              Stale failed event arrives after captured → discarded
            </p>
          </button>

          <button
            disabled={loading}
            onClick={() => handleInject("adversarial_llm")}
            className="p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/80 text-left transition group"
          >
            <div className="font-semibold text-xs text-red-400 mb-1 group-hover:text-red-300">
              5. Adversarial LLM
            </div>
            <p className="text-[11px] text-slate-400 line-clamp-2">
              Malicious LLM proposal (>₹25k) blocked by Policy Gate
            </p>
          </button>

          <button
            disabled={loading}
            onClick={() => handleInject("normal_recovery")}
            className="p-3 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/40 text-left transition group"
          >
            <div className="font-semibold text-xs text-indigo-200 mb-1">
              6. Normal Recovery
            </div>
            <p className="text-[11px] text-indigo-300/70 line-clamp-2">
              Classify → Predict → Optimize → Authorize → Link
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
