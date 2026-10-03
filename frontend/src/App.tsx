import { Component, useState } from "react";
import type { ErrorInfo, ReactNode } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  Link,
  useLocation,
} from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
} from "@tanstack/react-query";
import {
  Activity,
  ArrowUpRight,
  FileText,
  LayoutDashboard,
  Menu,
  ScanLine,
} from "lucide-react";
import DashboardPage from "./pages/DashboardPage";
import ExtractPage from "./pages/ExtractPage";
import DocumentsPage from "./pages/DocumentsPage";
import DocumentPage from "./pages/DocumentPage";
import { Modal } from "./components/ui";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: true },
  },
});

/** Contain rendering errors. @param props Application children. @returns Boundary. @throws None. */
class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  /** Derive fallback state. @returns Failure state. @throws None. */
  static getDerivedStateFromError() {
    return { failed: true };
  }
  /** Log render metadata without payloads. @param error Render error. @param info React metadata. @returns Nothing. @throws None. */
  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application render failed", error.name, info.componentStack);
  }
  /** Render content or recovery. @returns Interface. @throws None. */
  render() {
    return this.state.failed ? (
      <main className="empty">
        <h1>The page could not load</h1>
        <button className="button" onClick={() => window.location.reload()}>
          Reload application
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}

/** Resolve legacy database URLs. @returns Redirect. @throws None. */
function LegacyDatabase() {
  const id = new URLSearchParams(useLocation().search).get("id");
  return (
    <Navigate
      replace
      to={id && /^\d+$/.test(id) ? `/documents/${id}` : "/documents"}
    />
  );
}

/** Render responsive navigation and routes. @returns App shell. @throws None. */
function AppShell() {
  const [open, setOpen] = useState(false);
  const health = useQuery({
    queryKey: ["health"],
    queryFn: async () => {
      const response = await fetch("/health", {
        signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) throw new Error("API unavailable");
      const data: unknown = await response.json();
      if (
        !data ||
        typeof data !== "object" ||
        !("status" in data) ||
        data.status !== "ok"
      )
        throw new Error("API unavailable");
      return true;
    },
    retry: false,
    refetchInterval: 30000,
  });
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/">
          <span className="brand-icon">
            <ScanLine />
          </span>
          <span>
            IDPS<small>Intelligent workspace</small>
          </span>
        </Link>
        <p className="nav-label">WORKSPACE</p>
        <nav aria-label="Main navigation">
          <NavLink end to="/">
            <LayoutDashboard size={19} />
            Overview
          </NavLink>
          <NavLink to="/extract">
            <ScanLine size={19} />
            Extract document
          </NavLink>
          <NavLink to="/documents">
            <FileText size={19} />
            Document library
          </NavLink>
        </nav>
        <div className="sidebar-note">
          <span className="eyebrow">BUILT FOR CLARITY</span>
          <h3>Documents to decisions.</h3>
          <p>Extract, review and organize your information in one place.</p>
          <Link to="/extract">
            Start an extraction <ArrowUpRight size={16} />
          </Link>
        </div>
        <div className="sidebar-footer">
          <span className="avatar">W</span>
          <div>
            My workspace<small>Document processing</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <div className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Open navigation"
            onClick={() => setOpen(true)}
          >
            <Menu />
          </button>
          <span>
            Workspace <span className="muted">/ Document intelligence</span>
          </span>
          <span className={`connection ${health.isError ? "offline" : ""}`}>
            <Activity size={14} />
            {health.isError
              ? "API unavailable"
              : health.isPending
                ? "Connecting"
                : "API connected"}
          </span>
        </div>
        {health.isError && (
          <div className="offline-banner" role="status">
            The API is unreachable. Check the backend connection.
            <button onClick={() => void health.refetch()}>Reconnect</button>
          </div>
        )}
        <main id="main-content" tabIndex={-1}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/extract" element={<ExtractPage />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:id" element={<DocumentPage />} />
            <Route
              path="/process"
              element={<Navigate replace to="/extract" />}
            />
            <Route path="/database" element={<LegacyDatabase />} />
            <Route
              path="*"
              element={
                <div className="empty">
                  <h1>Page not found</h1>
                  <Link to="/" className="button">
                    Back to overview
                  </Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer className="workspace-footer">
          IDPS · Intelligent Document Processing System
          <span>Review AI-generated information before use.</span>
        </footer>
      </div>
      {open && (
        <Modal title="Workspace navigation" onClose={() => setOpen(false)}>
          <nav className="mobile-nav" aria-label="Mobile navigation">
            {[
              ["/", "Overview"],
              ["/extract", "Extract document"],
              ["/documents", "Document library"],
            ].map(([path, label]) => (
              <NavLink key={path} to={path!} onClick={() => setOpen(false)}>
                {label}
              </NavLink>
            ))}
          </nav>
        </Modal>
      )}
    </div>
  );
}

/** Mount routing, cache and error containment. @returns App. @throws None. */
export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppShell />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
