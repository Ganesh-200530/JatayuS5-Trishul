import type { PAStatus } from '../types';
import clsx from 'clsx';

/* ── Status Badge ─────────────────────────────────────────── */

const STATUS_STYLE: Record<string, { bg: string; text: string; dot: string; darkBg: string; darkText: string }> = {
  initiated:          { bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400', darkBg: 'dark:bg-gray-800', darkText: 'dark:text-gray-300' },
  clinical_review:    { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', darkBg: 'dark:bg-emerald-500/10', darkText: 'dark:text-emerald-400' },
  policy_check:       { bg: 'bg-violet-50', text: 'text-violet-700', dot: 'bg-violet-500', darkBg: 'dark:bg-violet-500/10', darkText: 'dark:text-violet-400' },
  submission_ready:   { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500', darkBg: 'dark:bg-amber-500/10', darkText: 'dark:text-amber-400' },
  submitted:          { bg: 'bg-indigo-50', text: 'text-indigo-700', dot: 'bg-indigo-500', darkBg: 'dark:bg-indigo-500/10', darkText: 'dark:text-indigo-400' },
  pending_decision:   { bg: 'bg-orange-50', text: 'text-orange-700', dot: 'bg-orange-500', darkBg: 'dark:bg-orange-500/10', darkText: 'dark:text-orange-400' },
  approved:           { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', darkBg: 'dark:bg-emerald-500/15', darkText: 'dark:text-emerald-400' },
  denied:             { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-500', darkBg: 'dark:bg-red-500/10', darkText: 'dark:text-red-400' },
  appeal_in_progress: { bg: 'bg-purple-50', text: 'text-purple-700', dot: 'bg-purple-500', darkBg: 'dark:bg-purple-500/10', darkText: 'dark:text-purple-400' },
  appeal_submitted:   { bg: 'bg-purple-50', text: 'text-purple-700', dot: 'bg-purple-500', darkBg: 'dark:bg-purple-500/10', darkText: 'dark:text-purple-400' },
  appeal_approved:    { bg: 'bg-emerald-50', text: 'text-emerald-700', dot: 'bg-emerald-500', darkBg: 'dark:bg-emerald-500/15', darkText: 'dark:text-emerald-400' },
  appeal_denied:      { bg: 'bg-rose-50', text: 'text-rose-700', dot: 'bg-rose-500', darkBg: 'dark:bg-rose-500/10', darkText: 'dark:text-rose-400' },
  escalated:          { bg: 'bg-amber-50', text: 'text-amber-700', dot: 'bg-amber-500', darkBg: 'dark:bg-amber-500/10', darkText: 'dark:text-amber-400' },
  cancelled:          { bg: 'bg-gray-100', text: 'text-gray-500', dot: 'bg-gray-400', darkBg: 'dark:bg-gray-800', darkText: 'dark:text-gray-400' },
  intake_received:    { bg: 'bg-indigo-50', text: 'text-indigo-700', dot: 'bg-indigo-500', darkBg: 'dark:bg-indigo-500/10', darkText: 'dark:text-indigo-400' },
};

export function StatusBadge({ status }: { status: PAStatus }) {
  const style = STATUS_STYLE[status] ?? { bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400', darkBg: 'dark:bg-gray-800', darkText: 'dark:text-gray-300' };
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold capitalize',
      style.bg, style.text, style.darkBg, style.darkText,
    )}>
      <span className={clsx('h-1.5 w-1.5 rounded-full', style.dot)} />
      {status.replace(/_/g, ' ')}
    </span>
  );
}

/* ── Urgency Badge ────────────────────────────────────────── */

const URGENCY_STYLE: Record<string, string> = {
  standard: 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300',
  urgent: 'bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400',
  emergent: 'bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-400',
};

export function UrgencyBadge({ urgency }: { urgency: string }) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold capitalize', URGENCY_STYLE[urgency] ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300')}>
      {urgency}
    </span>
  );
}

/* ── Confidence Meter ─────────────────────────────────────── */

export function ConfidenceMeter({ score }: { score: number | null }) {
  if (score == null) return <span className="text-gray-300 dark:text-gray-600 text-[10px]">—</span>;
  const pct = Math.round(score * 100);
  const color = pct >= 90 ? 'bg-emerald-500' : pct >= 70 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = pct >= 90 ? 'text-emerald-600 dark:text-emerald-400' : pct >= 70 ? 'text-amber-600 dark:text-amber-400' : 'text-red-600 dark:text-red-400';
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-2 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <div className={clsx('h-full rounded-full transition-all duration-500', color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={clsx('text-[11px] font-bold font-mono', textColor)}>{pct}%</span>
    </div>
  );
}

/* ── Spinner ──────────────────────────────────────────────── */

export function Spinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-[3px] border-gray-200 dark:border-gray-700 border-t-emerald-500" />
    </div>
  );
}

/* ── Skeleton ─────────────────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={clsx('rounded-lg bg-gray-200 dark:bg-gray-800 animate-shimmer', className)} />
  );
}

/* ── Empty State ──────────────────────────────────────────── */

export function Empty({ message = 'Nothing here yet' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-gray-300 dark:text-gray-600">
      <svg className="h-12 w-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p className="text-[13px] font-medium">{message}</p>
    </div>
  );
}

/* ── Badge ────────────────────────────────────────────────── */

export function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={clsx('inline-flex items-center rounded-full px-2.5 py-1 text-[10px] font-semibold', className ?? 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300')}>
      {children}
    </span>
  );
}

/* ── Card ─────────────────────────────────────────────────── */

export function Card({ children, className, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={clsx(
      'rounded-xl border transition-all duration-200',
      'bg-white border-gray-200 shadow-sm',
      'dark:bg-[#161b22] dark:border-white/5 dark:shadow-none',
      className,
    )} {...rest}>
      {children}
    </div>
  );
}

/* ── Metric Card ──────────────────────────────────────────── */

export function MetricCard({
  label,
  value,
  icon: Icon,
  trend,
  color = 'emerald',
  onClick,
  alert,
}: {
  label: string;
  value: string | number;
  icon: React.ComponentType<{ className?: string }>;
  trend?: { value: number; positive: boolean };
  color?: 'emerald' | 'violet' | 'amber' | 'red' | 'indigo' | 'teal';
  onClick?: () => void;
  alert?: boolean;
}) {
  const colorMap = {
    emerald: 'from-emerald-500/10 to-teal-500/10 border-emerald-500/20',
    violet: 'from-violet-500/10 to-purple-500/10 border-violet-500/20',
    amber: 'from-amber-500/10 to-orange-500/10 border-amber-500/20',
    red: 'from-red-500/10 to-rose-500/10 border-red-500/20',
    indigo: 'from-indigo-500/10 to-blue-500/10 border-indigo-500/20',
    teal: 'from-teal-500/10 to-cyan-500/10 border-teal-500/20',
  };
  const iconColorMap = {
    emerald: 'text-emerald-500',
    violet: 'text-violet-500',
    amber: 'text-amber-500',
    red: 'text-red-500',
    indigo: 'text-indigo-500',
    teal: 'text-teal-500',
  };

  return (
    <div
      onClick={onClick}
      className={clsx(
        'relative overflow-hidden rounded-xl border p-4 transition-all duration-200',
        'bg-white dark:bg-[#161b22]',
        alert
          ? 'border-orange-300 dark:border-orange-500/30 bg-orange-50/50 dark:bg-orange-500/5'
          : 'border-gray-200 dark:border-white/8 hover:border-gray-300 dark:hover:border-white/15',
        onClick && 'cursor-pointer hover:shadow-md dark:hover:shadow-none hover:scale-[1.02]',
      )}
    >
      {/* Gradient accent */}
      <div className={clsx('absolute inset-0 bg-gradient-to-br opacity-20 dark:opacity-10', colorMap[color])} />

      <div className="relative flex items-start justify-between">
        <div>
          <p className="text-[11px] font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wide">{label}</p>
          <p className="text-[26px] font-bold text-gray-900 dark:text-white mt-1 font-mono leading-none">{value}</p>
          {trend && (
            <div className={clsx('flex items-center gap-1 mt-2 text-[10px] font-semibold', trend.positive ? 'text-emerald-600 dark:text-emerald-400' : 'text-red-600 dark:text-red-400')}>
              <span>{trend.positive ? '↑' : '↓'}</span>
              <span>{Math.abs(trend.value)}%</span>
            </div>
          )}
        </div>
        <div className={clsx('h-10 w-10 rounded-xl flex items-center justify-center bg-gradient-to-br', colorMap[color])}>
          <Icon className={clsx('h-5 w-5', iconColorMap[color])} />
        </div>
      </div>
    </div>
  );
}
