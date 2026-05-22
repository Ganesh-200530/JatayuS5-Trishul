import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth';

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [remember, setRemember] = useState(false);
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'signup') {
        if (!fullName.trim()) {
          setError('Full name is required');
          setLoading(false);
          return;
        }
        await register(email, password, fullName);
      } else {
        await login(email, password);
      }
      navigate('/');
    } catch (err: any) {
      const d = err.response?.data?.detail;
      setError(
        typeof d === 'string'
          ? d
          : mode === 'signup'
          ? 'Could not create account'
          : 'Invalid credentials',
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="h-screen w-screen overflow-hidden bg-[#0a0d0b] bg-cover bg-center bg-no-repeat relative"
      style={{ backgroundImage: "url('/Back.png')" }}
    >
      {/* Subtle vignette so the eagle stays visible like the reference */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/55 via-transparent to-black/40 pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-b from-black/20 via-transparent to-black/40 pointer-events-none" />

      {/* Top-left brand image */}
      <div className="absolute top-5 left-8 z-20 flex items-center gap-2">
        <img
          src="/Topleft1.png"
          alt="MEDIX"
          className="h-16 w-auto object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.6)] -mt-5"
        />
        <img
          src="/Topleft2.png"
          alt=""
          className="h-16 w-auto object-contain drop-shadow-[0_2px_8px_rgba(0,0,0,0.6)]"
        />
      </div>

      {/* Footer */}
      <p className="absolute bottom-3 left-1/2 -translate-x-1/2 z-20 text-[10px] text-white/45 tracking-wide">
        © 2025 MEDIX. All rights reserved.
      </p>

      {/* Main grid */}
      <div className="relative z-10 h-full w-full grid grid-cols-1 lg:grid-cols-[1fr_460px] items-center px-6 lg:px-16 lg:pr-24 py-12 gap-10">
        {/* Left hero */}
        <div className="hidden lg:flex flex-col text-white max-w-[520px] justify-self-start">
          <p className="text-[11px] font-mono text-emerald-400 tracking-[0.22em] mb-4">
            // PRIOR AUTH AUTOMATION
          </p>
          <h1 className="text-[34px] leading-[1.1] font-extrabold mb-5">
            Automate the
            <br />
            entire <span className="text-emerald-400">PA lifecycle.</span>
          </h1>
          <p className="text-[13px] text-white/70 leading-relaxed mb-7 max-w-md">
            From clinical evidence extraction to
            <br />
            autonomous appeals. Multi-agent AI that
            <br />
            reduces turnaround from days to minutes.
          </p>

          <div className="grid grid-cols-2 gap-3 max-w-[440px]">
            <StatCard icon={<CheckIcon />} value="92%" label="approval rate" />
            <StatCard icon={<BoltIcon />} value="<5m" label="turnaround" />
            <StatCard icon={<ShieldIcon />} value="80%" label="zero-touch" />
            <StatCard icon={<BotIcon />} value="4" label="AI agents" />
          </div>
        </div>

        {/* Right login card */}
        <div className="w-full max-w-[420px] justify-self-center lg:justify-self-end relative">
          {/* Soft emerald glow halo (subtle) */}
          <div className="absolute -inset-2 rounded-[24px] bg-emerald-400/12 blur-[28px] pointer-events-none" />
          <div className="absolute -inset-5 rounded-[28px] bg-emerald-500/6 blur-[50px] pointer-events-none" />

          <div className="relative rounded-[20px] px-7 py-7 bg-[#070a09]/92 backdrop-blur-xl border border-emerald-400/20 shadow-[0_0_28px_-10px_rgba(16,185,129,0.35),0_25px_60px_-25px_rgba(0,0,0,0.85),inset_0_1px_0_0_rgba(255,255,255,0.04)]">
            {/* Logo (no circle) */}
            <div className="flex flex-col items-center mb-5">
              <img
                src="/logoo.png"
                alt="MEDIX"
                className="h-24 w-auto object-contain drop-shadow-[0_4px_18px_rgba(16,185,129,0.35)]"
              />
            </div>

            <h2 className="text-center text-white text-[22px] font-bold mb-0.5">
              {mode === 'signin' ? 'Welcome back' : 'Create account'}
            </h2>
            <p className="text-center text-white/55 text-[12px] mb-5">
              {mode === 'signin'
                ? 'Sign in to your account to continue'
                : 'Get started with MEDIX'}
            </p>

            {error && (
              <div className="mb-3 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2 text-[11px] text-red-300 font-medium animate-in">
                {error}
              </div>
            )}

            <form onSubmit={submit} className="space-y-3">
              {mode === 'signup' && (
                <Field label="Full name">
                  <UserIcon />
                  <input
                    type="text"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Dr. Jane Smith"
                    className="bg-transparent w-full pl-9 pr-3 py-2.5 text-[13px] text-white placeholder:text-white/30 outline-none"
                  />
                </Field>
              )}

              <Field label="Email">
                <MailIcon />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@hospital.org"
                  className="bg-transparent w-full pl-9 pr-3 py-2.5 text-[13px] text-gray-800 placeholder:text-gray-400 outline-none rounded-lg"
                />
              </Field>

              <Field label="Password">
                <LockIcon />
                <input
                  type={showPwd ? 'text' : 'password'}
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-transparent w-full pl-9 pr-9 py-2.5 text-[13px] text-gray-800 placeholder:text-gray-400 outline-none rounded-lg tracking-widest"
                />
                <button
                  type="button"
                  onClick={() => setShowPwd((s) => !s)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 transition"
                  tabIndex={-1}
                >
                  <EyeIcon open={showPwd} />
                </button>
              </Field>

              {mode === 'signin' && (
                <div className="flex items-center justify-between text-[11.5px] pt-0.5">
                  <label className="flex items-center gap-2 text-white/70 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                      className="h-3.5 w-3.5 accent-emerald-500"
                    />
                    Remember me
                  </label>
                  <button
                    type="button"
                    className="text-emerald-400 hover:text-emerald-300 font-medium"
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full h-10 mt-1 rounded-lg text-white text-[13px] font-semibold flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-emerald-500 hover:from-emerald-500 hover:to-emerald-400 transition-all shadow-[0_8px_24px_-6px_rgba(16,185,129,0.5)] disabled:opacity-60 active:scale-[0.99]"
              >
                {loading ? (
                  <span className="animate-pulse">Signing in…</span>
                ) : (
                  <>
                    {mode === 'signin' ? 'Sign in' : 'Create account'}
                    <ArrowRightIcon />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="flex items-center gap-3 my-3.5">
              <div className="flex-1 h-px bg-white/10" />
              <span className="text-[10px] text-white/40 tracking-widest">OR</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>

            <button
              type="button"
              onClick={() => setMode(mode === 'signin' ? 'signup' : 'signin')}
              className="w-full h-10 rounded-lg border border-white/15 bg-white/[0.03] text-white text-[13px] font-medium flex items-center justify-center gap-2 hover:bg-white/[0.06] transition"
            >
              <SsoIcon />
              {mode === 'signin' ? 'Sign in with SSO' : 'Already have an account?'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ---------- Helper components ---------- */

function StatCard({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3.5 px-4 py-3.5 rounded-xl bg-[#0d1411]/85 border border-emerald-500/20 backdrop-blur-sm shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)]">
      <div className="h-11 w-11 rounded-full bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center text-emerald-400 shrink-0">
        {icon}
      </div>
      <div className="leading-none">
        <p className="text-emerald-400 font-bold text-[26px] leading-none tracking-tight">{value}</p>
        <p className="text-white/65 text-[12px] mt-1.5">{label}</p>
      </div>
    </div>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="block text-[11.5px] font-medium text-white/75 mb-1">
        {label}
      </label>
      <div className="relative flex items-center bg-[#dfe6e9] border border-white/20 rounded-lg overflow-hidden focus-within:border-emerald-400/60 focus-within:bg-[#e8eef1] transition">
        {children}
      </div>
    </div>
  );
}

/* ---------- Icons ---------- */

function MailIcon() {
  return (
    <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l9 6 9-6M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}
function LockIcon() {
  return (
    <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 11v4m-6-4V8a6 6 0 1112 0v3M5 21h14a2 2 0 002-2v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2z" />
    </svg>
  );
}
function UserIcon() {
  return (
    <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M5.121 17.804A9 9 0 0112 15a9 9 0 016.879 2.804M15 9a3 3 0 11-6 0 3 3 0 016 0z" />
    </svg>
  );
}
function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M3 3l18 18M10.6 10.6a2 2 0 102.8 2.8M9.9 4.2A9.5 9.5 0 0112 4c5 0 9 4 10 8a10.4 10.4 0 01-3.2 4.6M6.5 6.5C4 8 2.5 10.5 2 12c1 4 5 8 10 8 1.4 0 2.7-.3 3.9-.8" />
    </svg>
  ) : (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M2 12s4-8 10-8 10 8 10 8-4 8-10 8S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
function ArrowRightIcon() {
  return (
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M14 5l7 7m0 0l-7 7m7-7H3" />
    </svg>
  );
}
function SsoIcon() {
  return (
    <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 11c0-3 2-5 5-5s5 2 5 5-2 5-5 5h-1m-2 0H7m0 0v3a2 2 0 002 2h6a2 2 0 002-2v-3m-2-3l-3-3m0 0l-3 3m3-3v9" />
    </svg>
  );
}
function CheckIcon() {
  return (
    <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}
function BoltIcon() {
  return (
    <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
    </svg>
  );
}
function ShieldIcon() {
  return (
    <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function BotIcon() {
  return (
    <svg width="22" height="22" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <rect x="4" y="8" width="16" height="12" rx="3" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v4M9 14h.01M15 14h.01M9 18h6" />
    </svg>
  );
}
