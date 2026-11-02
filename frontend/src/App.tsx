import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from './components/layout/Layout';
import { DashboardOverview } from './pages/DashboardOverview';
import { TransactionsPage } from './pages/TransactionsPage';
import { AlertsPage } from './pages/AlertsPage';
import { InvestigationsPage } from './pages/InvestigationsPage';

export const App: React.FC = () => {
  const [refreshKey, setRefreshKey] = useState<number>(0);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const handleGlobalRefresh = () => {
    setIsRefreshing(true);
    setRefreshKey((prev) => prev + 1);
    setTimeout(() => {
      setIsRefreshing(false);
    }, 600);
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <Layout
              onGlobalRefresh={handleGlobalRefresh}
              isRefreshing={isRefreshing}
            />
          }
        >
          <Route index element={<DashboardOverview key={`dash-${refreshKey}`} />} />
          <Route path="transactions" element={<TransactionsPage key={`tx-${refreshKey}`} />} />
          <Route path="alerts" element={<AlertsPage key={`alert-${refreshKey}`} />} />
          <Route path="investigations" element={<InvestigationsPage key={`inv-${refreshKey}`} />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
};

export default App;
