import { useQuery } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import api from '../api';
import type { DashboardStats, PriorAuthList } from '../types';
import { Card, Spinner, StatusBadge, ConfidenceMeter, Empty, MetricCard } from '../components/ui';
import {
  FileCheck,
  CheckCircle,
  AlertTriangle,
  TrendingUp,
  Scale,
  Clock,
  ArrowUpRight,
} from 'lucide-react';
import { useAuth } from '../auth';
import clsx from 'clsx';

export default function DashboardPage() {
  const navigate = useNavigate();
  const { user } = useAuth();

  const { data: stats, isLoading } = useQuery<DashboardStats>({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/dashboard/stats').then((r) => r.data),
    refetchInterval: 30000,
  });

  const { data: recentPAs } = useQuery<PriorAuthList[]>({
    queryKey: ['prior-auth-recent'],
    queryFn: () => api.get('/prior-auth/?limit=5').then((r) => r.data),
    refetchInterval: 30000,
  });

  const { data: analytics } = useQuery<any>({
    queryKey: ['analytics'],
    queryFn: () => api.get('/dashboard/analytics').then((r) => r.data),
    refetchInterval: 60000,
  });

  if (isLoading) return <Spinner />;
  if (!stats) return null;

  const metrics: Array<{
    label: string;
    value: string | number;
    icon: React.ComponentType<{ className?: string }>;
    color: 'emerald' | 'violet' | 'amber' | 'red' | 'indigo' | 'teal';
    onClick?: () => void;
    alert?: boolean;
  }> = [
    { label: 'Total Requests', value: stats.total_requests, icon: FileCheck, color: 'indigo', onClick: () => navigate('/prior-auth') },
    { label: 'Approval Rate', value: `${Math.round(stats.approval_rate * 100)}%`, icon: CheckCircle, color: 'emerald', onClick: () => navigate('/prior-auth?status=approved') },
    { label: 'Avg Confidence', value: `${Math.round(stats.average_confidence_score * 100)}%`, icon: TrendingUp, color: 'teal' },
    { label: 'Needs Review', value: stats.pending_human_review, icon: AlertTriangle, color: 'amber', onClick: () => navigate('/prior-auth?review=true'), alert: stats.pending_human_review > 0 },
    { label: 'Active Appeals', value: stats.total_appeals, icon: Scale, color: 'violet', onClick: () => navigate('/appeals') },
    { label: 'Appeal Success', value: `${Math.round(stats.appeal_success_rate * 100)}%`, icon: Clock, color: 'emerald', onClick: () => navigate('/appeals') },
  ];

  return (
    <div className="space-y-6 animate-in">
      {/* Header */}
      <div>
        <h1 className="text-[22px] font-bold text-gray-900 dark:text-white">
          Welcome back 👋
        </h1>
        <p className="text-[13px] text-gray-500 dark:text-gray-400 mt-1">
          {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })} •{' '}
          {stats.total_requests} requests, {Math.round(stats.approval_rate * 100)}% approval rate
        </p>
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 stagger-children">
        {metrics.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Status Breakdown */}
        <Card className="p-5">
          <h2 className="text-[13px] font-bold text-gray-900 dark:text-white mb-4">Status Breakdown</h2>
          {Object.keys(stats.status_breakdown).length > 0 ? (
            <div className="space-y-2">
              {Object.entries(stats.status_breakdown).map(([status, count]) => (
                <button
                  key={status}
                  onClick={() => navigate(`/prior-auth?status=${status.toLowerCase()}`)}
                  className="flex items-center justify-between w-full px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-white/5 transition-colors text-left group"
                >
                  <StatusBadge status={status as any} />
                  <span className="text-[12px] font-bold text-gray-600 dark:text-gray-300 font-mono group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">{count}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-[12px] text-gray-400 dark:text-gray-500">No data</p>
          )}
        </Card>

        {/* Recent Requests */}
        <Card className="lg:col-span-2 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100 dark:border-white/5">
            <h2 className="text-[13px] font-bold text-gray-900 dark:text-white">Recent Requests</h2>
            <Link to="/prior-auth" className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1 hover:underline">
              View all <ArrowUpRight className="h-3 w-3" />
            </Link>
          </div>
          {recentPAs && recentPAs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-[10px] text-gray-400 dark:text-gray-500 uppercase tracking-wider border-b border-gray-50 dark:border-white/5">
                    <th className="px-5 py-3 font-semibold">ID</th>
                    <th className="px-5 py-3 font-semibold">CPT</th>
                    <th className="px-5 py-3 font-semibold">Status</th>
                    <th className="px-5 py-3 font-semibold">Score</th>
                    <th className="px-5 py-3 font-semibold">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {recentPAs.map((pa, i) => (
                    <tr
                      key={pa.id}
                      className={clsx(
                        'hover:bg-gray-50 dark:hover:bg-white/[0.02] cursor-pointer transition-colors',
                        i % 2 === 0 ? 'bg-gray-50/50 dark:bg-white/[0.01]' : '',
                      )}
                      onClick={() => navigate(`/prior-auth/${pa.id}`)}
                    >
                      <td className="px-5 py-3 font-mono text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">{pa.id.slice(0, 8)}</td>
                      <td className="px-5 py-3 text-[12px] font-semibold text-gray-700 dark:text-gray-200">{pa.cpt_code}</td>
                      <td className="px-5 py-3"><StatusBadge status={pa.status} /></td>
                      <td className="px-5 py-3"><ConfidenceMeter score={pa.confidence_score} /></td>
                      <td className="px-5 py-3 text-[11px] text-gray-400 dark:text-gray-500">{new Date(pa.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty message="No requests yet" />
          )}
        </Card>
      </div>

      {/* Analytics Section */}
      {analytics && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Payer Performance */}
          <Card className="lg:col-span-2 p-5">
            <h2 className="text-[13px] font-bold text-gray-900 dark:text-white mb-4">Payer Performance</h2>
            {analytics.payer_breakdown?.length > 0 ? (
              <div className="space-y-3">
                {analytics.payer_breakdown.map((p: any) => (
                  <div key={p.payer} className="flex items-center gap-3">
                    <span className="text-[11px] font-medium text-gray-600 dark:text-gray-300 w-36 truncate">{p.payer}</span>
                    <div className="flex-1 h-3 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden flex">
                      <div className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-l-full transition-all duration-500" style={{ width: `${p.approval_rate * 100}%` }} />
                      <div className="h-full bg-gradient-to-r from-red-400 to-red-500" style={{ width: `${(p.denied / (p.total || 1)) * 100}%` }} />
                    </div>
                    <span className="text-[11px] font-mono font-bold text-gray-700 dark:text-gray-200 w-12 text-right">{Math.round(p.approval_rate * 100)}%</span>
                    <span className="text-[10px] text-gray-400 dark:text-gray-500 w-14 text-right">{p.total} total</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[12px] text-gray-400 dark:text-gray-500">No data yet</p>
            )}
          </Card>

          {/* Insights */}
          <Card className="p-5 space-y-4">
            <h2 className="text-[13px] font-bold text-gray-900 dark:text-white">Insights</h2>
            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-50 to-teal-50 dark:from-emerald-500/5 dark:to-teal-500/5 border border-emerald-100 dark:border-emerald-500/10">
              <p className="text-[10px] text-emerald-600 dark:text-emerald-400 uppercase tracking-wider font-semibold">Avg Processing Time</p>
              <p className="text-[24px] font-bold font-mono text-emerald-700 dark:text-emerald-300 mt-1">{analytics.avg_processing_hours || 0}h</p>
            </div>
            <div className="p-4 rounded-xl bg-gradient-to-br from-violet-50 to-purple-50 dark:from-violet-500/5 dark:to-purple-500/5 border border-violet-100 dark:border-violet-500/10">
              <p className="text-[10px] text-violet-600 dark:text-violet-400 uppercase tracking-wider font-semibold">Total Decided</p>
              <p className="text-[24px] font-bold font-mono text-violet-700 dark:text-violet-300 mt-1">{analytics.total_decided || 0}</p>
            </div>
            {analytics.top_denial_reasons?.length > 0 && (
              <div>
                <p className="text-[10px] text-gray-500 dark:text-gray-400 uppercase tracking-wider font-semibold mb-2">Top Denial Reasons</p>
                {analytics.top_denial_reasons.map((r: any, i: number) => (
                  <div key={i} className="flex items-center justify-between py-1.5">
                    <span className="text-[11px] text-gray-600 dark:text-gray-300 capitalize">{r.reason}</span>
                    <span className="text-[11px] font-mono font-bold text-red-600 dark:text-red-400">{r.count}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
