import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "./pages/DashboardPage";
import ProcessPage from "./pages/ProcessPage";
import DatabasePage from "./pages/DatabasePage";

function Sidebar() {
  return (
    <aside className="w-64 shrink-0 border-r border-white/10 bg-[#151821]">
      <nav className="flex flex-col gap-2 p-4">
        <a href="/" className="rounded px-3 py-2 text-white hover:bg-white/10">
          Dashboard
        </a>
        <a href="/process" className="rounded px-3 py-2 text-white hover:bg-white/10">
          Processes
        </a>
        <a href="/database" className="rounded px-3 py-2 text-white hover:bg-white/10">
          Database
        </a>
      </nav>
    </aside>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, staleTime: 5000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen bg-[#0f1117]">
          <Sidebar />
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/process" element={<ProcessPage />} />
              <Route path="/database" element={<DatabasePage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}