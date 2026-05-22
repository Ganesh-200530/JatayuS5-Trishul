import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import api from '../api';
import { Card, Spinner, Empty } from '../components/ui';
import type { AuditLogList } from '../types';

export default function AuditLogPage() {
  const [entityType, setEntityType] = useState('');
  const [action, setAction] = useState('');
  const [page, setPage] = useState(0);
  const limit = 25;

  const { data, isLoading } = useQuery({
    queryKey: ['audit-logs', entityType, action, page],
    queryFn: async () => {
      const params: Record<string, string | number> = { limit, offset: page * limit };
      if (entityType) params.entity_type = entityType;
      if (action) params.action = action;
      const res = await api.get('/audit-logs/', { params });
      return res.data as AuditLogList;
    },
  });

  const inputCls = 'h-8 px-2.5 text-sm border border-gray-300 dark:border-white/10 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500';

  return (
    <div className="space-y-4 animate-in">
      <h1 className="text-[22px] font-bold text-[#111] dark:text-white">Activity Log</h1>

      {/* Filters */}
      <div className="flex items-end gap-3">
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Entity Type</label>
          <select value={entityType} onChange={(e) => { setEntityType(e.target.value); setPage(0); }} className={inputCls}>
            <option value="">All</option>
            <option value="prior_auth_request">Prior Auth</option>
            <option value="eligibility_check">Eligibility</option>
            <option value="patient">Patient</option>
          </select>
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Action</label>
          <input type="text" placeholder="e.g., created" value={action} onChange={(e) => { setAction(e.target.value); setPage(0); }} className={inputCls + ' w-36'} />
        </div>
      </div>

      {isLoading ? <Spinner /> : !data?.items?.length ? <Empty message="No activity found" /> : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50/80 dark:bg-white/[0.02] text-gray-500 dark:text-gray-400 text-left text-xs">
                <tr>
                  <th className="px-4 py-2 font-medium">Time</th>
                  <th className="px-4 py-2 font-medium">Entity</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Done By</th>
                  <th className="px-4 py-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-white/5">
                {data.items.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50/50 dark:hover:bg-white/[0.03] transition-colors">
                    <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="text-xs bg-gray-100 dark:bg-white/5 text-gray-700 dark:text-gray-300 px-1.5 py-0.5 rounded">{log.entity_type}</span>
                      <p className="text-[11px] text-gray-400 dark:text-gray-500 mt-0.5 font-mono">{log.entity_id.slice(0, 8)}…</p>
                    </td>
                    <td className="px-4 py-2.5 font-medium text-gray-700 dark:text-gray-200">{log.action.replace(/_/g, ' ')}</td>
                    <td className="px-4 py-2.5 text-gray-600 dark:text-gray-300">{log.actor}</td>
                    <td className="px-4 py-2.5">
                      {log.details && (
                        <pre className="text-xs text-gray-500 dark:text-gray-400 max-w-xs truncate">{JSON.stringify(log.details)}</pre>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 dark:border-white/5">
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {data.offset + 1}–{Math.min(data.offset + data.limit, data.total)} of {data.total}
              </p>
              <div className="flex gap-1.5">
                <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="h-7 px-2.5 text-xs rounded-md border dark:border-white/10 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-white/[0.03] dark:text-gray-300 transition-colors">
                  Previous
                </button>
                <button disabled={data.offset + data.limit >= data.total} onClick={() => setPage((p) => p + 1)} className="h-7 px-2.5 text-xs rounded-md border dark:border-white/10 disabled:opacity-40 hover:bg-gray-50 dark:hover:bg-white/[0.03] dark:text-gray-300 transition-colors">
                  Next
                </button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
