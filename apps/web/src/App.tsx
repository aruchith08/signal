import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './contexts/ToastContext';
import { AuthProvider } from './contexts/AuthContext';
import { Layout } from './components/layout/Layout';
import { DashboardPage } from './pages/DashboardPage';
import { FeedPage } from './pages/FeedPage';
import { OpportunityDetailPage } from './pages/OpportunityDetailPage';
import { SavedPage } from './pages/SavedPage';
import { ProfilePage } from './pages/ProfilePage';
import { VerificationQueuePage } from './pages/VerificationQueuePage';
import { ActivityPage } from './pages/ActivityPage';
import { NotificationsPage } from './pages/NotificationsPage';

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="feed" element={<FeedPage />} />
              <Route path="opportunities/:id" element={<OpportunityDetailPage />} />
              <Route path="saved" element={<SavedPage />} />
              <Route path="profile" element={<ProfilePage />} />
              <Route path="preferences" element={<ProfilePage />} />
              <Route path="review" element={<VerificationQueuePage />} />
              <Route path="activity" element={<ActivityPage />} />
              <Route path="notifications" element={<NotificationsPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ToastProvider>
  );
};

export default App;
