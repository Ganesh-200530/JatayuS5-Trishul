import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { Card, Spinner, Badge } from '../components/ui';
import type { EligibilityCheck, Patient } from '../types';

export default function EligibilityPage() {
  const queryClient = useQueryClient();
  const [patientId, setPatientId] = useState('');
  const [payerId, setPayerId] = useState('');
  const [cptCode, setCptCode] = useState('');

  const { data: patients } = useQuery({
    queryKey: ['patients-list'],
    queryFn: async () => {
      const res = await api.get('/patients/');
      return res.data as Patient[];
    },
  });

  const { data: checks, isLoading } = useQuery({
    queryKey: ['eligibility-checks'],
    queryFn: async () => {
      const res = await api.get('/eligibility/');
      return res.data as EligibilityCheck[];
    },
  });

  const checkMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post('/eligibility/check', {
        patient_id: patientId,
        payer_id: payerId,
        cpt_code: cptCode || undefined,
      });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['eligibility-checks'] });
      setPatientId('');
      setPayerId('');
      setCptCode('');
    },
  });

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-[22px] font-bold text-gray-900 dark:text-white">Coverage Check</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Check if a patient's insurance covers a procedure
        </p>
      </div>

      {/* Check Form */}
      <Card className="mb-6 p-5">
        <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-200 mb-3">
          Run a Check
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Patient</label>
            <select
              value={patientId}
              onChange={(e) => setPatientId(e.target.value)}
              className="w-full border border-gray-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm bg-white dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500"
            >
              <option value="">Select patient...</option>
              {patients?.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.last_name}, {p.first_name} ({p.mrn})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Insurance</label>
            <input
              type="text"
              value={payerId}
              onChange={(e) => setPayerId(e.target.value)}
              placeholder="e.g., BCBS"
              className="w-full border border-gray-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm bg-white dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
              Procedure Code (optional)
            </label>
            <input
              type="text"
              value={cptCode}
              onChange={(e) => setCptCode(e.target.value)}
              placeholder="e.g., 70553"
              className="w-full border border-gray-200 dark:border-white/10 rounded-lg px-3 py-2 text-sm bg-white dark:bg-[#0d1117] dark:text-white dark:placeholder:text-gray-500"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={() => checkMutation.mutate()}
              disabled={!patientId || !payerId || checkMutation.isPending}
              className="w-full px-4 py-2 bg-gradient-to-r from-emerald-600 to-emerald-500 text-white rounded-lg text-sm font-medium hover:from-emerald-500 hover:to-emerald-400 disabled:opacity-50 transition-all shadow-sm"
            >
              {checkMutation.isPending ? 'Checking...' : 'Check Now'}
            </button>
          </div>
        </div>
        {checkMutation.isError && (
          <p className="mt-2 text-sm text-red-600 dark:text-red-400">
            Error: {(checkMutation.error as Error).message}
          </p>
        )}
      </Card>

      {/* Results */}
      {isLoading ? (
        <Spinner />
      ) : !checks?.length ? (
        <Card className="p-5">
          <p className="text-gray-500 dark:text-gray-400 text-center py-8">
            No checks done yet
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {checks.map((check) => (
            <Card key={check.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      Payer: {check.payer_id}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Patient: {check.patient_id.slice(0, 8)}...
                      {check.checked_cpt_code &&
                        ` | CPT: ${check.checked_cpt_code}`}
                    </p>
                  </div>
                  <Badge
                    className={
                      check.is_active
                        ? 'bg-green-100 dark:bg-green-900/20 text-green-800 dark:text-green-400'
                        : check.status === 'error'
                          ? 'bg-red-100 dark:bg-red-900/20 text-red-800 dark:text-red-400'
                          : 'bg-gray-100 dark:bg-white/5 text-gray-800 dark:text-gray-300'
                    }
                  >
                    {check.is_active ? 'Active' : check.status}
                  </Badge>
                </div>
                <div className="text-right text-xs text-gray-500 dark:text-gray-400">
                  <p>{new Date(check.checked_at).toLocaleString()}</p>
                  {check.plan_name && <p>{check.plan_name}</p>}
                  {check.pa_required_for_cpt !== null && (
                    <p>
                      PA Required:{' '}
                      <span
                        className={
                          check.pa_required_for_cpt
                            ? 'text-red-600 dark:text-red-400 font-medium'
                            : 'text-green-600 dark:text-green-400 font-medium'
                        }
                      >
                        {check.pa_required_for_cpt ? 'Yes' : 'No'}
                      </span>
                    </p>
                  )}
                </div>
              </div>
              {check.error_message && (
                <p className="mt-2 text-xs text-red-600 dark:text-red-400">
                  {check.error_message}
                </p>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
