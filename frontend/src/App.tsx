import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Sidebar from "./components/Sidebar";        // ← only place Sidebar is ever imported
import DashboardPage from "./pages/DashboardPage"; // ← now correctly exports a page, not a Sidebar
import ProcessPage from "./pages/ProcessPage";
import DatabasePage from "./pages/DatabasePage";

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen bg-[#0f1117]">
          <Sidebar />                   {/* rendered ONCE here */}
          <main className="flex-1 overflow-auto">
            <Routes>
              <Route path="/"          element={<DashboardPage />} />
              <Route path="/process"   element={<ProcessPage />} />
              <Route path="/database"  element={<DatabasePage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  );
}