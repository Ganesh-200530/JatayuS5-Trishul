import {
  FileText,
  Brain,
  ShieldCheck,
  Send,
  CheckCircle,
  type LucideIcon,
} from 'lucide-react';
import clsx from 'clsx';

interface AgentStep {
  icon: LucideIcon;
  label: string;
  agent: string;
  color: string;
  statusKey: string;
}

const AGENT_STEPS: AgentStep[] = [
  { icon: FileText, label: 'Reading records', agent: 'Clinical Reader', color: 'text-blue-500', statusKey: 'initiated' },
  { icon: Brain, label: 'Extracting evidence', agent: 'AI Engine', color: 'text-purple-500', statusKey: 'clinical_review' },
  { icon: ShieldCheck, label: 'Matching payer rules', agent: 'Policy Agent', color: 'text-indigo-500', statusKey: 'policy_check' },
  { icon: Send, label: 'Preparing submission', agent: 'Submission Agent', color: 'text-cyan-500', statusKey: 'submission_ready' },
  { icon: Send, label: 'Submitted to payer', agent: 'Submission Agent', color: 'text-amber-500', statusKey: 'submitted' },
  { icon: CheckCircle, label: 'Decision', agent: 'Complete', color: 'text-green-500', statusKey: 'complete' },
];

const PROCESSING_STATUSES = new Set([
  'initiated', 'clinical_review', 'policy_check', 'submission_ready', 'pending_decision',
]);

function statusToStep(status: string): number {
  // Terminal statuses map past the last step
  if (['approved', 'denied', 'appeal_in_progress', 'appeal_submitted', 'appeal_approved', 'appeal_denied', 'escalated', 'cancelled'].includes(status)) {
    return AGENT_STEPS.length;
  }
  const idx = AGENT_STEPS.findIndex((s) => s.statusKey === status);
  if (idx >= 0) return idx;
  return AGENT_STEPS.length;
}

export function isProcessing(status: string): boolean {
  return PROCESSING_STATUSES.has(status);
}

/** Real status-driven agent pipeline for PA detail page. */
export function LiveAgentPipeline({ status }: { status: string }) {
  const active = statusToStep(status);
  const processing = isProcessing(status);

  return (
    <div className="relative">
      <div className="flex items-center gap-2 mb-3">
        {processing ? (
          <>
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-emerald-600 uppercase tracking-wider">AI Agents Working</span>
          </>
        ) : (
          <>
            <div className="h-1.5 w-1.5 rounded-full bg-gray-400" />
            <span className="text-xs font-medium text-gray-500 uppercase tracking-wider">Pipeline Complete</span>
          </>
        )}
      </div>

      <div className="space-y-1">
        {AGENT_STEPS.map((step, i) => {
          const Icon = step.icon;
          const isDone = i < active;
          const isActive = i === active && processing;
          const isPending = i > active || (i === active && !processing && i < AGENT_STEPS.length);

          return (
            <div
              key={step.label}
              className={clsx(
                'flex items-center gap-3 px-3 py-2 rounded-md transition-all duration-300',
                isActive && 'bg-white shadow-sm',
                isDone && 'opacity-60',
                isPending && 'opacity-25',
              )}
            >
              <div
                className={clsx(
                  'h-7 w-7 rounded-full flex items-center justify-center transition-all duration-300',
                  isActive && 'bg-blue-50',
                  isDone && 'bg-emerald-50',
                  isPending && 'bg-gray-100',
                )}
              >
                {isDone ? (
                  <CheckCircle className="h-3.5 w-3.5 text-emerald-500" />
                ) : (
                  <Icon className={clsx('h-3.5 w-3.5 transition-colors duration-300', isActive ? step.color : 'text-gray-400')} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className={clsx('text-sm font-medium transition-colors duration-300', isActive ? 'text-gray-900' : isDone ? 'text-gray-600' : 'text-gray-400')}>
                  {step.label}
                </p>
                {isActive && <p className="text-xs text-blue-500 animate-in">{step.agent} is processing...</p>}
                {isDone && <p className="text-xs text-emerald-500">{step.agent} done</p>}
              </div>
              {isActive && (
                <div className="flex gap-0.5">
                  <span className="h-1 w-1 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="h-1 w-1 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="h-1 w-1 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-2 h-1 bg-gray-100 rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-blue-400 to-emerald-400 rounded-full transition-all duration-700 ease-out"
          style={{ width: `${(Math.min(active + (processing ? 0.5 : 1), AGENT_STEPS.length) / AGENT_STEPS.length) * 100}%` }}
        />
      </div>
    </div>
  );
}

/** @deprecated No longer used — kept for backwards compat. */
export default function AgentPipelineAnimation() {
  return null;
}
