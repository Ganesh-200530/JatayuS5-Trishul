import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider, useAuth } from "./auth";
import Layout from "./components/Layout";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import PatientsPage from "./pages/PatientsPage";
import PriorAuthListPage from "./pages/PriorAuthListPage";
import PriorAuthDetailPage from "./pages/PriorAuthDetailPage";
import PoliciesPage from "./pages/PoliciesPage";
import AppealsPage from "./pages/AppealsPage";
import AuditLogPage from "./pages/AuditLogPage";
import EligibilityPage from "./pages/EligibilityPage";
import PatientIntakePage from './pages/PatientIntakePage';
import PatientDetailPage from "./pages/PatientDetailPage";
import { Spinner } from "./components/ui";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 5000 } },
});

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/intake/:token" element={<PatientIntakePage />} />
            <Route
              element={
                <ProtectedRoute>
                  <Layout />
                </ProtectedRoute>
              }
            >
              <Route path="/" element={<DashboardPage />} />
              <Route path="/patients" element={<PatientsPage />} />
              <Route path="/patients/:id" element={<PatientDetailPage />} />
              <Route path="/prior-auth" element={<PriorAuthListPage />} />
              <Route path="/prior-auth/:id" element={<PriorAuthDetailPage />} />
              <Route path="/policies" element={<PoliciesPage />} />
              <Route path="/appeals" element={<AppealsPage />} />
              <Route path="/eligibility" element={<EligibilityPage />} />
              <Route path="/audit-log" element={<AuditLogPage />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
