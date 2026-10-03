import { useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ScanLine } from "lucide-react";

/** Read authentication status. @returns Session state. @throws Backend connection error. */
async function sessionStatus(): Promise<{ authenticated: boolean }> {
  const response = await fetch("/api/auth/session", { cache: "no-store", signal: AbortSignal.timeout(10000) });
  if (!response.ok) throw new Error("Backend unavailable. Check your presentation connection.");
  return response.json();
}

/** Protect workspace pages. @param props Page content. @returns Content or login. @throws None. */
export function RequireSession({ children }: { children: ReactNode }) {
  const location = useLocation();
  const session = useQuery({ queryKey: ["session"], queryFn: sessionStatus, retry: false, staleTime: 0, refetchInterval: 60000 });
  if (session.isPending) return <main className="empty">Connecting to your workspace…</main>;
  if (session.isError) return <main className="empty"><h1>Backend unavailable</h1><button className="button" onClick={() => void session.refetch()}>Reconnect</button></main>;
  if (!session.data.authenticated) return <Navigate replace to={`/signin?next=${encodeURIComponent(location.pathname + location.search)}`} />;
  return children;
}

/** Render a dedicated login page. @returns Login form. @throws None. */
export default function SignInPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const cache = useQueryClient();
  /** Submit credentials. @param event Form event. @returns Completion. @throws None; errors displayed. */
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError("");
    try {
      const response = await fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password }), signal: AbortSignal.timeout(15000) });
      if (!response.ok) { const data = await response.json(); throw new Error(typeof data.detail === "string" ? data.detail : "Sign-in failed."); }
      setPassword(""); cache.clear();
      const next = new URLSearchParams(location.search).get("next") || "/extract";
      navigate(next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") && !next.startsWith("/signin") ? next : "/extract", { replace: true });
    } catch (failure) { setError(failure instanceof Error ? failure.message : "Backend unavailable."); }
    finally { setPending(false); }
  }
  return <main className="signin-page"><section className="signin-card"><div className="brand"><span className="brand-icon"><ScanLine /></span><span>IDPS<small>Intelligent workspace</small></span></div><h1>Sign in to your workspace</h1><p>Access your documents and start a new extraction.</p><form onSubmit={submit}><label htmlFor="username">Username</label><input id="username" autoComplete="username" required maxLength={128} value={username} onChange={e => setUsername(e.target.value)} /><label htmlFor="password">Password</label><input id="password" type="password" autoComplete="current-password" required maxLength={1024} value={password} onChange={e => setPassword(e.target.value)} />{error && <p role="alert">{error}</p>}<button className="button" disabled={pending}>{pending ? "Signing in…" : "Sign in"}</button></form><small>Sign in once for up to eight hours. Sign out when finished.</small></section></main>;
}

/** End the current session. @returns Logout button. @throws None. */
export function SignOutButton() {
  const navigate = useNavigate(); const cache = useQueryClient(); const [error, setError] = useState("");
  /** Revoke access and clear cached documents. @returns Completion. @throws None; error displayed. */
  async function logout() {
    try { const response = await fetch("/api/auth/logout", { method: "POST" }); if (!response.ok) throw new Error(); cache.clear(); navigate("/signin", { replace: true }); }
    catch { setError("Could not sign out. Try again."); }
  }
  return <div><button className="button secondary" onClick={() => void logout()}>Sign out</button>{error && <p role="alert">{error}</p>}</div>;
}
