import React, { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { motion } from 'framer-motion';
import { Home, User, Settings, Film, Sparkles } from 'lucide-react';

import HomePage from './pages/HomePage.js';
import ProfilePage from './pages/ProfilePage.js';
import type { UserProfile } from './types/index.js';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

const Navigation: React.FC<{ userId: number; onUserIdChange: (id: number) => void }> = ({ 
  userId, 
  onUserIdChange 
}) => {
  const location = useLocation();
  const [showUserSelect, setShowUserSelect] = useState(false);
  const [tempUserId, setTempUserId] = useState(userId);

  const handleUserIdSubmit = () => {
    onUserIdChange(tempUserId);
    setShowUserSelect(false);
  };

  const navItems = [
    { path: '/', icon: Home, label: 'Home' },
    { path: '/profile', icon: User, label: 'Profile' },
  ];

  return (
    <nav className="bg-background-200/80 backdrop-blur-md border-b border-white/10 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to="/" className="flex items-center space-x-2">
            <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-accent-500 rounded-lg flex items-center justify-center">
              <Film className="w-5 h-5 text-white" />
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-primary-400 to-accent-400 bg-clip-text text-transparent">
              FlickIQ
            </span>
          </Link>

          {/* Navigation Links */}
          <div className="hidden md:flex items-center space-x-1">
            {navItems.map(({ path, icon: Icon, label }) => {
              const isActive = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  className={`relative px-4 py-2 rounded-xl font-medium transition-all duration-200 flex items-center gap-2 ${
                    isActive
                      ? 'text-white bg-white/10'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-gradient-to-r from-primary-500/20 to-accent-500/20 rounded-xl border border-primary-500/30"
                    />
                  )}
                </Link>
              );
            })}
          </div>

          {/* User Controls */}
          <div className="flex items-center space-x-3">
            <div className="text-sm text-gray-400">
              User: <span className="text-white font-medium">{userId}</span>
            </div>
            <button
              onClick={() => setShowUserSelect(!showUserSelect)}
              className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all duration-200"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Mobile Navigation */}
        <div className="md:hidden border-t border-white/10">
          <div className="flex justify-around py-2">
            {navItems.map(({ path, icon: Icon, label }) => {
              const isActive = location.pathname === path;
              return (
                <Link
                  key={path}
                  to={path}
                  className={`flex flex-col items-center py-2 px-3 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'text-primary-400'
                      : 'text-gray-400 hover:text-white'
                  }`}
                >
                  <Icon className="w-5 h-5" />
                  <span className="text-xs mt-1">{label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>

      {/* User Selection Dropdown */}
      {showUserSelect && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          className="absolute top-full right-4 mt-2 bg-background-300/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-md p-4 min-w-64"
        >
          <h3 className="text-white font-medium mb-3">Switch User</h3>
          <div className="space-y-3">
            <input
              type="number"
              value={tempUserId}
              onChange={(e) => setTempUserId(Number(e.target.value))}
              min="1"
              className="w-full px-3 py-2 bg-background-400 border border-white/10 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-primary-500/50"
              placeholder="Enter user ID"
            />
            <div className="flex gap-2">
              <button
                onClick={handleUserIdSubmit}
                className="flex-1 px-3 py-2 bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-500 hover:to-primary-600 text-white rounded-lg font-medium transition-all duration-200"
              >
                Switch
              </button>
              <button
                onClick={() => setShowUserSelect(false)}
                className="flex-1 px-3 py-2 bg-background-400 hover:bg-background-300 text-gray-300 rounded-lg font-medium transition-all duration-200"
              >
                Cancel
              </button>
            </div>
          </div>
        </motion.div>
      )}
    </nav>
  );
};

const App: React.FC = () => {
  const [userId, setUserId] = useState(1001);
  const [profiles, setProfiles] = useState<Record<number, UserProfile>>({});

  const currentProfile = profiles[userId] || { display_name: '', bio: '' };

  const handleProfileUpdate = (profile: UserProfile) => {
    setProfiles(prev => ({
      ...prev,
      [userId]: profile
    }));
  };

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="min-h-screen bg-gradient-to-br from-background-50 via-background-100 to-background-200">
          {/* Background Effects */}
          <div className="fixed inset-0 overflow-hidden pointer-events-none">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary-500/5 rounded-full blur-3xl" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-accent-500/5 rounded-full blur-3xl" />
          </div>

          <Navigation userId={userId} onUserIdChange={setUserId} />
          
          <main className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <Routes>
              <Route 
                path="/" 
                element={<HomePage userId={userId} />} 
              />
              <Route 
                path="/profile" 
                element={
                  <ProfilePage 
                    userId={userId} 
                    profile={currentProfile}
                    onProfileUpdate={handleProfileUpdate}
                  />
                } 
              />
            </Routes>
          </main>

          {/* Toast Notifications */}
          <Toaster
            position="bottom-right"
            toastOptions={{
              duration: 3000,
              style: {
                background: 'rgba(40, 42, 54, 0.95)',
                color: 'white',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                backdropFilter: 'blur(8px)',
              },
              success: {
                iconTheme: {
                  primary: '#10B981',
                  secondary: 'white',
                },
              },
              error: {
                iconTheme: {
                  primary: '#EF4444',
                  secondary: 'white',
                },
              },
            }}
          />
        </div>
      </Router>
    </QueryClientProvider>
  );
};

export default App;