import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';

import { ThemeProvider } from './context/ThemeContext';
import { AuthProvider } from './auth/AuthContext';
import { ProtectedRoute } from './auth/ProtectedRoute';
import { ToastProvider } from './components/Toast';
import { Sidebar } from './components/Sidebar';
import { LiveConfirmationModal } from './components/LiveConfirmationModal';

// Public Pages
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/auth/LoginPage';
import { RegisterPage } from './pages/auth/RegisterPage';
import { ForgotPasswordPage } from './pages/auth/ForgotPasswordPage';

// Protected App Pages
import { DashboardPage } from './pages/DashboardPage';
import { TrainingPage } from './pages/TrainingPage';
import { BacktestPage } from './pages/BacktestPage';
import { BotPage } from './pages/BotPage';
import { ModelsPage } from './pages/ModelsPage';
import { MarketsPage } from './pages/MarketsPage';
import { TradesPage } from './pages/TradesPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';
import { ForecastPage } from './pages/ForecastPage';
import { botApi } from './services/api';

/**
 * Shell layout for authenticated platform routes (Dashboard, Markets, Bot, etc.)
 * Includes institutional Sidebar, Live confirmation modal, and content viewport.
 */
interface AppLayoutProps {
  botMode: 'paper' | 'live';
  setBotMode: (mode: 'paper' | 'live') => void;
  showLiveModal: boolean;
  setShowLiveModal: (show: boolean) => void;
}

const AppLayout: React.FC<AppLayoutProps> = ({
  botMode,
  setBotMode,
  showLiveModal,
  setShowLiveModal,
}) => {
  const handleConfirmLive = async (code: string) => {
    try {
      await botApi.setMode('live', code);
      setBotMode('live');
    } catch {
      // Error handled in BotPage toast
    }
  };

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      {/* Platform Sidebar */}
      <Sidebar
        botMode={botMode}
        onOpenLiveModal={() => setShowLiveModal(true)}
      />

      {/* Live execution safety modal */}
      <LiveConfirmationModal
        isOpen={showLiveModal}
        onClose={() => setShowLiveModal(false)}
        onConfirm={handleConfirmLive}
      />

      {/* Main trading workspace */}
      <main className="main-with-sidebar page-enter" style={{ flex: 1, minWidth: 0 }}>
        <Outlet />
      </main>
    </div>
  );
};

function App() {
  const [botMode, setBotMode] = useState<'paper' | 'live'>('paper');
  const [showLiveModal, setShowLiveModal] = useState(false);

  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              {/* ── Public Landing & Auth Routes ── */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route path="/forgot-password" element={<ForgotPasswordPage />} />

              {/* ── Protected Trading Platform Routes ── */}
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout
                      botMode={botMode}
                      setBotMode={setBotMode}
                      showLiveModal={showLiveModal}
                      setShowLiveModal={setShowLiveModal}
                    />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<DashboardPage botMode={botMode} />} />
                <Route path="/markets" element={<MarketsPage />} />
                <Route path="/bot" element={<BotPage setBotMode={setBotMode} />} />
                <Route path="/training" element={<TrainingPage />} />
                <Route path="/backtest" element={<BacktestPage />} />
                <Route path="/backtesting" element={<BacktestPage />} />
                <Route path="/models" element={<ModelsPage />} />
                <Route path="/forecast" element={<ForecastPage />} />
                <Route path="/trades" element={<TradesPage />} />
                <Route path="/analytics" element={<AnalyticsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
              </Route>

              {/* ── Fallback Route ── */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
