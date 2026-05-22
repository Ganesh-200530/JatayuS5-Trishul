import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { Card, Spinner } from '../components/ui';
import type { DashboardStats } from '../types';

const STATUS_COLORS: Record<string, string> = {
  approved: '#22c55e',
  denied: '#ef4444',
  submitted: '#3b82f6',
  pending_decision: '#f59e0b',
  escalated: '#a855f7',
  initiated: '#6b7280',
  clinical_review: '#06b6d4',
  policy_check: '#8b5cf6',
  appeal_in_progress: '#f97316',
  cancelled: '#9ca3af',
};

export default function AnalyticsPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: async () => {
      const res = await api.get('/dashboard/stats');
      return res.data as DashboardStats;
    },
  });

  if (isLoading) return <Spinner />;
  if (!stats) return null;

  const statusEntries = Object.entries(stats.status_breakdown).sort(
    (a, b) => b[1] - a[1],
  );
  const maxCount = Math.max(...statusEntries.map(([, v]) => v), 1);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Reports</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Numbers and trends at a glance
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard
          label="Total PA Requests"
          value={stats.total_requests}
          color="blue"
        />
        <MetricCard
          label="Approved"
          value={`${(stats.approval_rate * 100).toFixed(1)}%`}
          color="green"
        />
        <MetricCard
          label="Confidence"
          value={`${(stats.average_confidence_score * 100).toFixed(0)}%`}
          color="purple"
        />
        <MetricCard
          label="Needs Review"
          value={stats.pending_human_review}
          color="yellow"
        />
      </div>

      {/* Appeal Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
        <MetricCard
          label="Total Appeals"
          value={stats.total_appeals}
          color="orange"
        />
        <MetricCard
          label="Appeals Won"
          value={`${(stats.appeal_success_rate * 100).toFixed(1)}%`}
          color="green"
        />
      </div>

      {/* Status Breakdown Bar Chart */}
      <Card>
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          By Status
        </h2>
        <div className="space-y-3">
          {statusEntries.map(([status, count]) => (
            <div key={status} className="flex items-center gap-3">
              <span className="text-sm text-gray-600 dark:text-gray-300 w-40 truncate">
                {status.replace(/_/g, ' ')}
              </span>
              <div className="flex-1 bg-gray-100 dark:bg-white/5 rounded-full h-6 relative overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500"
                  style={{
                    width: `${(count / maxCount) * 100}%`,
                    backgroundColor:
                      STATUS_COLORS[status] || '#6b7280',
                  }}
                />
              </div>
              <span className="text-sm font-medium text-gray-700 dark:text-gray-200 w-10 text-right">
                {count}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function MetricCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string | number;
  color: string;
}) {
  const colorMap: Record<string, string> = {
    blue: 'border-blue-500 bg-blue-50 dark:bg-blue-900/20',
    green: 'border-green-500 bg-green-50 dark:bg-green-900/20',
    purple: 'border-purple-500 bg-purple-50 dark:bg-purple-900/20',
    yellow: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20',
    orange: 'border-orange-500 bg-orange-50 dark:bg-orange-900/20',
    red: 'border-red-500 bg-red-50 dark:bg-red-900/20',
  };

  return (
    <Card className={`border-l-4 ${colorMap[color] || colorMap.blue}`}>
      <p className="text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
        {label}
      </p>
      <p className="mt-1 text-3xl font-bold text-gray-900 dark:text-white">{value}</p>
    </Card>
  );
}
