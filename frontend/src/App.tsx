import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Sidebar from "./components/Sidebar";
import DashboardPage from "./pages/DashboardPage";
import ProcessPage from "./pages/ProcessPage";
import DatabasePage from "./pages/DatabasePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Keep data reasonably fresh across page switches without refetching
      // on every single render.
      staleTime: 10_000,
      refetchOnWindowFocus: true,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {/* Skip link — the first focusable element for keyboard users,
            visually hidden until focused. Lets someone tabbing through
            the page jump straight past the sidebar to page content. */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:bg-indigo-500 focus:text-white focus:px-4 focus:py-2 focus:rounded-lg focus:text-sm focus:font-medium"
        >
          Skip to main content
        </a>
        <div className="flex min-h-screen bg-[#0b0d14]">
          <Sidebar />
          <div id="main-content" tabIndex={-1} className="flex-1 overflow-auto focus:outline-none">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/process" element={<ProcessPage />} />
              <Route path="/database" element={<DatabasePage />} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}