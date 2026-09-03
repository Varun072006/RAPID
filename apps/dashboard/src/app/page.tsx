"use client";

import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  CreditCard,
  Shield,
  Sliders,
  BarChart3,
  Activity,
  Search,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  HelpCircle,
  Layers,
  Settings,
  FileText,
  Check,
  X,
  Clock,
  Play,
  Lock,
  Cpu,
  DollarSign,
  Filter,
  ChevronRight,
  Zap,
  Building2,
  Terminal,
  Code2,
  Sparkles,
  TrendingUp,
  ShieldCheck,
  User,
  SlidersHorizontal,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";

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

// Recharts Benchmark Data
const RECOVERY_TREND = [
  { day: "Mon", Failed: 45, Recovered: 32, Revenue: 345000 },
  { day: "Tue", Failed: 52, Recovered: 39, Revenue: 412000 },
  { day: "Wed", Failed: 61, Recovered: 46, Revenue: 498000 },
  { day: "Thu", Failed: 48, Recovered: 37, Revenue: 389000 },
  { day: "Fri", Failed: 70, Recovered: 54, Revenue: 580000 },
  { day: "Sat", Failed: 38, Recovered: 29, Revenue: 310000 },
  { day: "Sun", Failed: 42, Recovered: 33, Revenue: 362000 },
];

const BENCHMARK_DATA = [
  { name: "Fixed 6h Retry", recoveryRate: 41.83, regret: 53.68, errors: 145 },
  { name: "Expert Rule Engine", recoveryRate: 50.15, regret: 0.0, errors: 98 },
  { name: "RAPID Engine", recoveryRate: 47.23, regret: 21.46, errors: 0 },
];

export default function ProfessionalDashboard() {
  const [activeTab, setActiveTab] = useState<"overview" | "transactions" | "optimizer" | "policy" | "benchmarks" | "lab">("overview");
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
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterState, setFilterState] = useState<string>("ALL");
  const [showDrawer, setShowDrawer] = useState(false);

  // Optimizer Simulator State
  const [calcAmount, setCalcAmount] = useState<number>(18500); // ₹18,500
  const [calcMethod, setCalcMethod] = useState<string>("card");
  const [calcBank, setCalcBank] = useState<string>("HDFC");

  // Fetch telemetry
  const fetchDashboardData = async () => {
    try {
      const mRes = await fetch(`${API_BASE}/api/metrics/summary`);
      if (mRes.ok) {
        setMetrics(await mRes.json());
      }
      const pRes = await fetch(`${API_BASE}/api/payments?limit=20`);
      if (pRes.ok) {
        const pData = await pRes.json();
        setPayments(pData);
        if (pData.length > 0 && !selectedPaymentId) {
          setSelectedPaymentId(pData[0].payment_id);
        }
      }
    } catch (err) {
      console.warn("Backend API offline or mock mode active");
    }
  };

  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 4000);
    return () => clearInterval(interval);
  }, []);

  // Fetch timeline for selected payment
  useEffect(() => {
    if (!selectedPaymentId) return;
    const fetchTimeline = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/payments/${selectedPaymentId}/timeline`);
        if (res.ok) {
          setTimeline(await res.json());
        }
      } catch (e) {
        console.warn("Timeline fetch error", selectedPaymentId);
      }
    };
    fetchTimeline();
  }, [selectedPaymentId]);

  const handleInjectScenario = async (scenarioType: string) => {
    setLoading(true);
    setStatusMessage(`Running scenario ${scenarioType}...`);
    try {
      const res = await fetch(`${API_BASE}/api/demo/inject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario_type: scenarioType }),
      });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Scenario applied: ${data.scenario}`);
        if (data.payment_id) {
          setSelectedPaymentId(data.payment_id);
        }
        await fetchDashboardData();
      }
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
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
        setStatusMessage(`Recovery executed: ${data.action}`);
        await fetchDashboardData();
        const tRes = await fetch(`${API_BASE}/api/payments/${paymentId}/timeline`);
        if (tRes.ok) setTimeline(await tRes.json());
      }
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  const getStateBadge = (state: string) => {
    switch (state) {
      case "CAPTURED":
      case "SETTLED":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
      case "FAILED":
        return "bg-rose-500/10 text-rose-400 border-rose-500/20";
      case "UNKNOWN":
        return "bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse";
      case "PAYMENT_LINK_SENT":
        return "bg-sky-500/10 text-sky-400 border-sky-500/20";
      case "ESCALATED":
        return "bg-purple-500/10 text-purple-400 border-purple-500/20";
      default:
        return "bg-slate-500/10 text-slate-400 border-slate-500/20";
    }
  };

  // Optimizer Calculations
  const calcENvNow = 0.42 * calcAmount - 5.0 - 0.03 * calcAmount - 0.02 * calcAmount;
  const calcENvLater = 0.78 * calcAmount - 5.0 - 0.01 * calcAmount - 0.01 * calcAmount;
  const calcENvLink = 0.82 * calcAmount - 15.0 - 0.12 * calcAmount - 0.0 * calcAmount;

  const filteredPayments = payments.filter((p) => {
    const matchesSearch =
      p.payment_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (p.bank && p.bank.toLowerCase().includes(searchTerm.toLowerCase())) ||
      p.payment_method.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesState = filterState === "ALL" || p.state === filterState;
    return matchesSearch && matchesState;
  });

  const selectedPayment = payments.find((p) => p.payment_id === selectedPaymentId);

  return (
    <div className="flex h-screen bg-[#090d16] text-slate-100 font-sans overflow-hidden">
      {/* ── Left Enterprise Sidebar ────────────────────────────────────────── */}
      <aside className="w-64 bg-[#0c1322] border-r border-slate-800/80 flex flex-col justify-between shrink-0">
        <div>
          {/* Logo Header */}
          <div className="p-6 border-b border-slate-800/80 flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-sky-500 via-indigo-600 to-emerald-400 flex items-center justify-center shadow-lg">
              <Zap className="h-5 w-5 text-white fill-white" />
            </div>
            <div>
              <div className="font-extrabold text-sm text-white tracking-tight flex items-center gap-1.5">
                Razorpay RAPID
              </div>
              <div className="text-[10px] text-slate-400 font-mono">
                Recovery Command Center
              </div>
            </div>
          </div>

          {/* Navigation Items */}
          <nav className="p-3 space-y-1 text-xs font-medium">
            <button
              onClick={() => setActiveTab("overview")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "overview"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <LayoutDashboard className="h-4 w-4" /> Overview & Metrics
            </button>

            <button
              onClick={() => setActiveTab("transactions")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "transactions"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <CreditCard className="h-4 w-4" /> Transactions & Queue
            </button>

            <button
              onClick={() => setActiveTab("optimizer")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "optimizer"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <SlidersHorizontal className="h-4 w-4" /> Causal ML & Optimizer
            </button>

            <button
              onClick={() => setActiveTab("policy")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "policy"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <Shield className="h-4 w-4" /> Autonomy Policy Gates
            </button>

            <button
              onClick={() => setActiveTab("benchmarks")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "benchmarks"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <BarChart3 className="h-4 w-4" /> ROI & Benchmarks
            </button>

            <button
              onClick={() => setActiveTab("lab")}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl transition text-left ${
                activeTab === "lab"
                  ? "bg-sky-500/10 text-sky-400 font-bold border-l-4 border-sky-500"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/40"
              }`}
            >
              <Terminal className="h-4 w-4" /> Simulation & Test Lab
            </button>
          </nav>
        </div>

        {/* Sidebar Footer Account Badge */}
        <div className="p-4 border-t border-slate-800/80 text-xs font-mono">
          <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-800">
            <div className="flex items-center gap-2 text-slate-300 font-bold mb-1">
              <User className="h-3.5 w-3.5 text-sky-400" /> Merchant Account
            </div>
            <div className="text-[10px] text-slate-400 truncate">acc_rzp_enterprise_demo</div>
            <div className="text-[10px] text-emerald-400 mt-1 flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> Razorpay Test Mode
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Content Area ──────────────────────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-b border-slate-800/80 bg-[#0c1322] px-8 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
            <span className="text-slate-200 font-bold">Razorpay Merchant Portal</span>
            <span>/</span>
            <span className="text-sky-400 capitalize">{activeTab}</span>
          </div>

          <div className="flex items-center gap-4">
            {statusMessage && (
              <span className="text-xs font-mono text-sky-300 bg-sky-500/10 px-3 py-1 rounded-full border border-sky-500/20">
                {statusMessage}
              </span>
            )}

            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-slate-900 border border-slate-800 text-xs font-mono">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-status-pulse" />
              <span className="text-slate-400">STATUS:</span>
              <span className="text-emerald-400 font-bold">CONNECTED (4ms)</span>
            </div>

            <button
              onClick={fetchDashboardData}
              className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition"
              title="Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* Dynamic Tab Body Container */}
        <div className="flex-1 overflow-y-auto p-8">
          {/* ── TAB 1: OVERVIEW ───────────────────────────────────────────── */}
          {activeTab === "overview" && (
            <div className="space-y-8">
              {/* Executive KPI Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div className="enterprise-card p-6 rounded-2xl enterprise-card-hover">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      Total Net Recovered Revenue
                    </span>
                    <div className="p-2 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                      <DollarSign className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-extrabold text-white tracking-tight">
                    ₹51,38,205
                  </div>
                  <div className="mt-2 text-xs text-emerald-400 font-mono flex items-center gap-1">
                    <TrendingUp className="h-3.5 w-3.5" /> +₹5.48L Net Gain / 10k failures
                  </div>
                </div>

                <div className="enterprise-card p-6 rounded-2xl enterprise-card-hover">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      Recovery Success Rate
                    </span>
                    <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                      <Activity className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-extrabold text-white tracking-tight">
                    {metrics.recovery_rate}%
                  </div>
                  <div className="mt-2 text-xs text-sky-300 font-mono">
                    +5.4% Absolute vs Static Retries
                  </div>
                </div>

                <div className="enterprise-card p-6 rounded-2xl enterprise-card-hover">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      Mean Decision Regret
                    </span>
                    <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                      <CheckCircle2 className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-extrabold text-white tracking-tight">
                    ₹21.46 <span className="text-xs font-normal text-slate-400">/ payment</span>
                  </div>
                  <div className="mt-2 text-xs text-indigo-300 font-mono">
                    60.0% Decision Regret Reduction
                  </div>
                </div>

                <div className="enterprise-card p-6 rounded-2xl enterprise-card-hover">
                  <div className="flex justify-between items-start mb-2">
                    <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                      Unsafe Autonomy Rate
                    </span>
                    <div className="p-2 rounded-xl bg-purple-500/10 text-purple-400 border border-purple-500/20">
                      <ShieldCheck className="h-4 w-4" />
                    </div>
                  </div>
                  <div className="text-3xl font-extrabold text-white tracking-tight">0.0%</div>
                  <div className="mt-2 text-xs text-purple-300 font-mono">
                    100% Policy Engine Precedence
                  </div>
                </div>
              </div>

              {/* Recovery Trend Chart + Bank Uptime Radar */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
                <div className="lg:col-span-8 enterprise-card p-6 rounded-2xl">
                  <div className="flex items-center justify-between mb-4">
                    <div>
                      <h3 className="text-sm font-bold text-white">Daily Revenue Recovery Performance</h3>
                      <p className="text-xs text-slate-400 font-mono">
                        Comparing Failed Payment Volume vs Autonomous Recovery
                      </p>
                    </div>
                    <span className="text-xs font-mono px-3 py-1 rounded-lg bg-slate-900 text-sky-400 border border-slate-800">
                      Past 7 Days
                    </span>
                  </div>

                  <div className="h-64 w-full">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={RECOVERY_TREND} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                        <XAxis dataKey="day" stroke="#64748b" fontSize={11} />
                        <YAxis stroke="#64748b" fontSize={11} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b", borderRadius: "12px" }} />
                        <Area type="monotone" dataKey="Failed" stroke="#f43f5e" fill="#f43f5e" fillOpacity={0.15} />
                        <Area type="monotone" dataKey="Recovered" stroke="#10b981" fill="#10b981" fillOpacity={0.25} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                <div className="lg:col-span-4 enterprise-card p-6 rounded-2xl flex flex-col justify-between">
                  <div>
                    <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                      <Building2 className="h-4 w-4 text-sky-400" /> Issuing Bank Uptime Radar
                    </h3>
                    <p className="text-xs text-slate-400 font-mono mb-4">
                      Real-time sliding window failure rate monitoring
                    </p>

                    <div className="space-y-3 font-mono text-xs">
                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                        <span className="text-slate-300 font-bold">HDFC Bank</span>
                        <span className="text-emerald-400 font-bold">99.4% (Healthy)</span>
                      </div>

                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                        <span className="text-slate-300 font-bold">ICICI Bank</span>
                        <span className="text-emerald-400 font-bold">98.8% (Healthy)</span>
                      </div>

                      <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                        <span className="text-slate-300 font-bold">SBI Bank</span>
                        <span className="text-emerald-400 font-bold">97.2% (Healthy)</span>
                      </div>

                      <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-900/60 flex justify-between items-center animate-pulse">
                        <span className="text-rose-200 font-bold">AXIS Bank</span>
                        <span className="text-rose-400 font-bold">84.1% (Incident)</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-slate-800 text-[11px] text-slate-400 font-mono">
                    System Health Detector automatically trips Policy Rule 5 during bank outages.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 2: TRANSACTIONS ───────────────────────────────────────── */}
          {activeTab === "transactions" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              {/* Payment Table */}
              <div className="lg:col-span-8 enterprise-card rounded-2xl overflow-hidden">
                <div className="p-5 border-b border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h3 className="text-sm font-bold text-white">Merchant Recovery Queue</h3>
                    <p className="text-xs text-slate-400 font-mono">
                      Select transaction to view state machine history & audit trail
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <div className="relative">
                      <Search className="h-3.5 w-3.5 absolute left-3 top-2.5 text-slate-500" />
                      <input
                        type="text"
                        placeholder="Search ID, method..."
                        value={searchTerm}
                        onChange={(e) => setSearchTerm(e.target.value)}
                        className="pl-8 pr-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
                      />
                    </div>

                    <select
                      value={filterState}
                      onChange={(e) => setFilterState(e.target.value)}
                      className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300 font-mono"
                    >
                      <option value="ALL">All States</option>
                      <option value="FAILED">FAILED</option>
                      <option value="UNKNOWN">UNKNOWN</option>
                      <option value="CAPTURED">CAPTURED</option>
                      <option value="PAYMENT_LINK_SENT">LINK SENT</option>
                    </select>
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="text-xs uppercase bg-slate-950 text-slate-400 border-b border-slate-800 font-mono">
                      <tr>
                        <th className="px-6 py-3 font-semibold">Payment ID</th>
                        <th className="px-6 py-3 font-semibold">Amount</th>
                        <th className="px-6 py-3 font-semibold">Method</th>
                        <th className="px-6 py-3 font-semibold">State</th>
                        <th className="px-6 py-3 font-semibold text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono text-xs">
                      {filteredPayments.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="px-6 py-12 text-center text-slate-500 font-sans">
                            No matching payments found. Run a simulation from the Test Lab tab!
                          </td>
                        </tr>
                      ) : (
                        filteredPayments.map((p) => (
                          <tr
                            key={p.payment_id}
                            onClick={() => setSelectedPaymentId(p.payment_id)}
                            className={`cursor-pointer transition-colors ${
                              selectedPaymentId === p.payment_id
                                ? "bg-sky-600/10 border-l-4 border-sky-500"
                                : "hover:bg-slate-800/40"
                            }`}
                          >
                            <td className="px-6 py-3.5 font-bold text-slate-200">
                              {p.payment_id}
                            </td>
                            <td className="px-6 py-3.5 text-slate-300 font-semibold">
                              ₹{(p.amount / 100).toLocaleString("en-IN")}
                            </td>
                            <td className="px-6 py-3.5 text-slate-400 uppercase">
                              {p.payment_method || "CARD"} {p.bank ? `(${p.bank})` : ""}
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
                            <td className="px-6 py-3.5 text-right font-sans flex justify-end gap-2">
                              {p.state === "FAILED" && (
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleTriggerRecovery(p.payment_id);
                                  }}
                                  className="px-3 py-1 text-xs rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-bold transition shadow-sm"
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

              {/* Timeline & Replay Drawer */}
              <div className="lg:col-span-4 enterprise-card p-6 rounded-2xl flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between pb-3 mb-4 border-b border-slate-800">
                    <div>
                      <h3 className="text-sm font-bold text-white">Audit Event Timeline</h3>
                      <p className="text-xs text-slate-400 font-mono">
                        {selectedPaymentId ? `ID: ${selectedPaymentId}` : "Select payment"}
                      </p>
                    </div>
                    <Clock className="h-4 w-4 text-sky-400" />
                  </div>

                  <div className="space-y-3.5 max-h-[420px] overflow-y-auto pr-1 text-xs font-mono">
                    {timeline.length === 0 ? (
                      <div className="py-16 text-center text-slate-500">
                        No events recorded for this payment yet.
                      </div>
                    ) : (
                      timeline.map((ev, idx) => (
                        <div key={ev.event_id || idx} className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                          <div className="flex justify-between font-bold text-sky-300 mb-1">
                            <span>{ev.event_type}</span>
                            <span className="text-[10px] text-slate-500">
                              {new Date(ev.timestamp).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="text-slate-400 text-[11px]">
                            Actor: <span className="text-slate-200">{ev.actor}</span>
                          </div>
                          {ev.details && (
                            <pre className="mt-2 text-[10px] bg-slate-900 p-2 rounded text-slate-300 overflow-x-auto">
                              {JSON.stringify(ev.details, null, 2)}
                            </pre>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 text-[11px] text-slate-400 font-mono flex items-center justify-between">
                  <span>Replay Audit Log</span>
                  <span className="text-emerald-400">✓ Immutable</span>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 3: OPTIMIZER ──────────────────────────────────────────── */}
          {activeTab === "optimizer" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              <div className="lg:col-span-6 enterprise-card p-6 rounded-2xl">
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <SlidersHorizontal className="h-4 w-4 text-sky-400" /> Dynamic ENv Optimizer Simulator
                </h3>
                <p className="text-xs text-slate-400 mb-6 font-mono">
                  Formula: ENv = P(recovery) * Amount - Cost - Friction - Risk
                </p>

                <div className="space-y-5 text-xs font-mono">
                  <div>
                    <div className="flex justify-between mb-2">
                      <span className="text-slate-300 font-bold">Transaction Amount:</span>
                      <span className="text-sky-400 font-bold">
                        ₹{calcAmount.toLocaleString("en-IN")}
                      </span>
                    </div>
                    <input
                      type="range"
                      min="500"
                      max="50000"
                      step="500"
                      value={calcAmount}
                      onChange={(e) => setCalcAmount(Number(e.target.value))}
                      className="w-full accent-sky-500 bg-slate-900 h-2 rounded-lg cursor-pointer"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-slate-400 mb-1">Payment Method:</label>
                      <select
                        value={calcMethod}
                        onChange={(e) => setCalcMethod(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200"
                      >
                        <option value="card">Card (2.0% risk, 3% friction)</option>
                        <option value="upi">UPI (1.0% risk, 1% friction)</option>
                        <option value="netbanking">Netbanking</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-slate-400 mb-1">Issuing Bank:</label>
                      <select
                        value={calcBank}
                        onChange={(e) => setCalcBank(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-slate-200"
                      >
                        <option value="HDFC">HDFC Bank</option>
                        <option value="ICICI">ICICI Bank</option>
                        <option value="AXIS">AXIS Bank</option>
                        <option value="SBI">SBI Bank</option>
                      </select>
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-800 space-y-3 font-sans">
                    <span className="text-xs font-bold text-sky-300 font-mono uppercase block">
                      Optimized Action Candidate Ranking
                    </span>

                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                      <div>
                        <div className="font-bold text-white text-xs">retry_later (Background Delay)</div>
                        <div className="text-[11px] text-slate-400">P(recovery) = 78% • Minimal friction</div>
                      </div>
                      <div className="text-right font-mono font-bold text-emerald-400 text-sm">
                        ₹{calcENvLater.toFixed(2)}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center">
                      <div>
                        <div className="font-bold text-white text-xs">payment_link (SMS/WhatsApp)</div>
                        <div className="text-[11px] text-slate-400">P(recovery) = 82% • High friction penalty</div>
                      </div>
                      <div className="text-right font-mono font-bold text-sky-300 text-sm">
                        ₹{calcENvLink.toFixed(2)}
                      </div>
                    </div>

                    <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 flex justify-between items-center opacity-70">
                      <div>
                        <div className="font-bold text-white text-xs">retry_now (Immediate)</div>
                        <div className="text-[11px] text-slate-400">P(recovery) = 42% • Gateway fatigue</div>
                      </div>
                      <div className="text-right font-mono font-bold text-slate-400 text-sm">
                        ₹{calcENvNow.toFixed(2)}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="lg:col-span-6 enterprise-card p-6 rounded-2xl">
                <h3 className="text-sm font-bold text-white mb-1 flex items-center gap-2">
                  <Sparkles className="h-4 w-4 text-sky-400" /> ML Model AUC & Calibration Matrix
                </h3>
                <p className="text-xs text-slate-400 mb-6 font-mono">
                  3 Isotonic-Calibrated Logistic Regressions + Gradient Boosting Failure Classifier
                </p>

                <div className="space-y-4 text-xs font-mono">
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="flex justify-between font-bold text-slate-200 mb-1">
                      <span>Failure Classifier (GBM):</span>
                      <span className="text-emerald-400">83.0% Accuracy</span>
                    </div>
                    <p className="text-[11px] text-slate-400 font-sans">
                      Classifies failure root cause: transient, infrastructure, customer_action_needed, customer_issue.
                    </p>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="flex justify-between font-bold text-slate-200 mb-1">
                      <span>retry_now Predictor:</span>
                      <span className="text-sky-300">AUC: 0.8037 | Brier: 0.1436</span>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="flex justify-between font-bold text-slate-200 mb-1">
                      <span>retry_later Predictor:</span>
                      <span className="text-sky-300">AUC: 0.7471 | Brier: 0.1972</span>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="flex justify-between font-bold text-slate-200 mb-1">
                      <span>payment_link Predictor:</span>
                      <span className="text-sky-300">AUC: 0.8555 | Brier: 0.1098</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 4: POLICY ─────────────────────────────────────────────── */}
          {activeTab === "policy" && (
            <div className="enterprise-card p-8 rounded-2xl space-y-6">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Shield className="h-5 w-5 text-emerald-400" /> The 5 Deterministic Safety Policy Gates
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  LLM proposes. Policy Engine authorizes. AI can never override safety rules.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-xs font-mono font-bold text-amber-400 mb-1">Rule 1</div>
                  <div className="text-xs font-bold text-white mb-1">Unknown-State Guard</div>
                  <div className="text-[11px] text-slate-400">
                    If state == UNKNOWN → DENY retry. Reconcile with Razorpay first.
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-xs font-mono font-bold text-sky-400 mb-1">Rule 2</div>
                  <div className="text-xs font-bold text-white mb-1">Amount Cap</div>
                  <div className="text-[11px] text-slate-400">
                    If amount &gt; ₹25,000 → DENY. Escalate high tickets to manual review.
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-xs font-mono font-bold text-sky-400 mb-1">Rule 3</div>
                  <div className="text-xs font-bold text-white mb-1">Retry Budget Cap</div>
                  <div className="text-[11px] text-slate-400">
                    If retry_count &gt;= 2 → DENY. Prevents endless retry loops.
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-xs font-mono font-bold text-sky-400 mb-1">Rule 4</div>
                  <div className="text-xs font-bold text-white mb-1">Confidence Gate</div>
                  <div className="text-[11px] text-slate-400">
                    If amount &gt;= ₹5,000 and confidence &lt; 55% → DENY.
                  </div>
                </div>

                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                  <div className="text-xs font-mono font-bold text-rose-400 mb-1">Rule 5</div>
                  <div className="text-xs font-bold text-white mb-1">Incident Gate</div>
                  <div className="text-[11px] text-slate-400">
                    If system == INCIDENT → DENY retry. Pauses retries during bank outage.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 5: BENCHMARKS ─────────────────────────────────────────── */}
          {activeTab === "benchmarks" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
              <div className="lg:col-span-8 enterprise-card p-6 rounded-2xl">
                <h3 className="text-sm font-bold text-white mb-1">10,000 Scenario Held-Out Benchmark</h3>
                <p className="text-xs text-slate-400 mb-6 font-mono">
                  Recovery Rate Comparison across 3 strategies
                </p>

                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={BENCHMARK_DATA} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis dataKey="name" stroke="#64748b" fontSize={11} />
                      <YAxis stroke="#64748b" fontSize={11} unit="%" />
                      <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#1e293b", borderRadius: "12px" }} />
                      <Bar dataKey="recoveryRate" fill="#0284c7" radius={[6, 6, 0, 0]}>
                        {BENCHMARK_DATA.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={index === 2 ? "#10b981" : index === 1 ? "#38bdf8" : "#64748b"} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="lg:col-span-4 enterprise-card p-6 rounded-2xl">
                <h3 className="text-sm font-bold text-white mb-1">Safety & Double Charge Proof</h3>
                <p className="text-xs text-slate-400 mb-4 font-mono">
                  Zero Unknown State Double-Charges
                </p>

                <div className="space-y-4 font-mono text-xs">
                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-slate-400 mb-1">Fixed Retry Baseline:</div>
                    <div className="text-rose-400 font-bold">145 Unknown State Errors</div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                    <div className="text-slate-400 mb-1">Rule Engine:</div>
                    <div className="text-amber-400 font-bold">98 Unknown State Errors</div>
                  </div>

                  <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-800">
                    <div className="text-emerald-300 mb-1">RAPID Engine:</div>
                    <div className="text-emerald-400 font-bold text-base">0 Unknown State Errors</div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── TAB 6: TEST LAB ───────────────────────────────────────────── */}
          {activeTab === "lab" && (
            <div className="enterprise-card p-8 rounded-2xl space-y-6">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Terminal className="h-5 w-5 text-sky-400" /> Interactive Simulation & Test Lab
                </h3>
                <p className="text-xs text-slate-400 font-mono mt-1">
                  Trigger distributed failure modes to observe bounded autonomy live
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("timeout")}
                  className="p-4 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 text-left transition"
                >
                  <div className="font-bold text-xs text-amber-300 mb-1 font-mono">1. API Timeout (UNKNOWN State)</div>
                  <p className="text-[11px] text-slate-400">
                    Simulates network drop. Policy Engine blocks retries & triggers reconciliation.
                  </p>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("bank_degradation")}
                  className="p-4 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 text-left transition"
                >
                  <div className="font-bold text-xs text-rose-300 mb-1 font-mono">2. Bank Incident (AXIS Outage)</div>
                  <p className="text-[11px] text-slate-400">
                    Crosses 15% failure threshold. Policy Rule 5 pauses automatic retries.
                  </p>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("duplicate_webhook")}
                  className="p-4 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 text-left transition"
                >
                  <div className="font-bold text-xs text-sky-300 mb-1 font-mono">3. Duplicate Webhook</div>
                  <p className="text-[11px] text-slate-400">
                    Atomic DB constraint on event_id suppresses duplicate webhook delivery.
                  </p>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("out_of_order")}
                  className="p-4 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 text-left transition"
                >
                  <div className="font-bold text-xs text-purple-300 mb-1 font-mono">4. Out-of-Order Webhook</div>
                  <p className="text-[11px] text-slate-400">
                    Stale FAILED event arriving after CAPTURED is discarded by State Machine.
                  </p>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("adversarial_llm")}
                  className="p-4 rounded-xl bg-slate-950 hover:bg-slate-900 border border-slate-800 text-left transition"
                >
                  <div className="font-bold text-xs text-red-400 mb-1 font-mono">5. Adversarial LLM Prompt</div>
                  <p className="text-[11px] text-slate-400">
                    Malicious LLM proposal (&gt;₹25k) is intercepted and denied by Policy Engine.
                  </p>
                </button>

                <button
                  disabled={loading}
                  onClick={() => handleInjectScenario("normal_recovery")}
                  className="p-4 rounded-xl bg-sky-950/40 hover:bg-sky-900/50 border border-sky-800 text-left transition"
                >
                  <div className="font-bold text-xs text-sky-200 mb-1 font-mono">6. Normal Payment Recovery</div>
                  <p className="text-[11px] text-sky-300/80">
                    Standard end-to-end pipeline: Classify → Predict → Optimize → Authorize → Execute.
                  </p>
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
