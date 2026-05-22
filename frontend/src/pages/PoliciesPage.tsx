import { useQuery } from '@tanstack/react-query';
import api from '../api';
import type { PayerPolicy } from '../types';
import { Card, Spinner, Empty } from '../components/ui';
import { ShieldCheck, CheckCircle, XCircle } from 'lucide-react';

export default function PoliciesPage() {
  const { data: policies, isLoading } = useQuery<PayerPolicy[]>({
    queryKey: ['policies'],
    queryFn: () => api.get('/policies/').then((r) => r.data),
  });

  if (isLoading) return <Spinner />;

  return (
    <div className="space-y-4 animate-in">
      <h1 className="text-[22px] font-bold text-[#111] dark:text-white">Payer Rules</h1>

      {!policies?.length ? (
        <Empty message="No policies configured" />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5">
          {policies.map((p) => (
            <Card key={p.id} className="p-3.5 space-y-2.5 hover:border-[#ddd] dark:hover:border-white/10 transition-all">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                  <h3 className="text-[11px] font-bold text-[#111] dark:text-white">{p.payer_name}</h3>
                </div>
                {p.pa_required ? (
                  <span className="inline-flex items-center gap-1 text-[9px] font-bold text-orange-700 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 px-1.5 py-0.5 rounded">
                    <CheckCircle className="h-2.5 w-2.5" /> PA Required
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-[9px] font-bold text-emerald-700 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-900/20 px-1.5 py-0.5 rounded">
                    <XCircle className="h-2.5 w-2.5" /> No PA
                  </span>
                )}
              </div>

              <dl className="space-y-1 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-[#999] dark:text-gray-500">Payer ID</span>
                  <span className="font-mono text-[10px] text-[#555] dark:text-gray-300">{p.payer_id}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#999] dark:text-gray-500">CPT Code</span>
                  <span className="font-mono font-bold text-[#111] dark:text-white">{p.cpt_code}</span>
                </div>
                {p.cpt_description && (
                  <div className="flex justify-between">
                    <span className="text-[#999] dark:text-gray-500">Description</span>
                    <span className="text-[#555] dark:text-gray-300 text-right max-w-[60%] text-[10px]">{p.cpt_description}</span>
                  </div>
                )}
                {p.effective_date && (
                  <div className="flex justify-between">
                    <span className="text-[#999] dark:text-gray-500">Effective</span>
                    <span className="text-[#555] dark:text-gray-300 text-[10px]">{new Date(p.effective_date).toLocaleDateString()}</span>
                  </div>
                )}
              </dl>

              {p.policy_document_url && (
                <a href={p.policy_document_url} target="_blank" rel="noopener noreferrer" className="inline-block text-emerald-600 text-[10px] font-semibold hover:underline">
                  View policy →
                </a>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
