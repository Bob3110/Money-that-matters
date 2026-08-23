import { Routes, Route } from "react-router-dom";
import Header from "./components/Header.jsx";
import BottomNav from "./components/BottomNav.jsx";
import Footer from "./components/Footer.jsx";
import MoneyMatchPage from "./pages/MoneyMatchPage.jsx";
import MarketNewsPage from "./pages/MarketNewsPage.jsx";
import InsidersPage from "./pages/InsidersPage.jsx";
import CongressPage from "./pages/CongressPage.jsx";
import EgyptPage from "./pages/EgyptPage.jsx";
import WatchlistPage from "./pages/WatchlistPage.jsx";
import TickerDetailPage from "./pages/TickerDetailPage.jsx";

export default function App() {
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col bg-canvas font-sans">
      <Header />
      <main className="flex-1 pb-24">
        <Routes>
          <Route path="/" element={<MoneyMatchPage />} />
          <Route path="/news" element={<MarketNewsPage />} />
          <Route path="/insiders" element={<InsidersPage />} />
          <Route path="/congress" element={<CongressPage />} />
          <Route path="/egypt" element={<EgyptPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/ticker/:ticker" element={<TickerDetailPage />} />
        </Routes>
      </main>
      <div className="fixed bottom-14 left-0 right-0 z-10 mx-auto max-w-md">
        <Footer />
      </div>
      <BottomNav />
    </div>
  );
}
