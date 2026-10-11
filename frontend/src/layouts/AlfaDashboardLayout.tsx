/**
 * Main layout for Alfa Dashboard
 */

import React, { useState } from 'react'
import { Outlet } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { useAlfaDashboardStats } from '@/hooks/useAlfaRatings'

export const AlfaDashboardLayout: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const { data: stats } = useAlfaDashboardStats()

  const formatTime = (date: Date) => date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })

  const [lastUpdate] = React.useState(() => formatTime(new Date()))

  return (
    <div className="flex h-screen bg-slate-950">
      {/* Sidebar */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-slate-800 transform transition-transform duration-200 ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } md:relative md:translate-x-0`}
      >
        <div className="flex flex-col h-full">
          {/* Header */}
          <div className="p-6 border-b border-slate-800">
            <h1 className="text-2xl font-bold text-sky-400">Alfa</h1>
            <p className="text-xs text-slate-500 mt-1">Rating System v2.1</p>
          </div>

          {/* Navigation */}
          <nav className="flex-1 overflow-y-auto p-4 space-y-2">
            <NavLink to="/alfa/dashboard" icon="📊" label="Dashboard" />
            <NavLink to="/alfa/players" icon="👥" label="Player Ratings" />
            <NavLink to="/alfa/anomalies" icon="⚠️" label="Anomaly Alerts" />
            <NavLink to="/alfa/predictions" icon="🎯" label="Predictions" />
            <NavLink to="/alfa/ab-tests" icon="📈" label="A/B Testing" />
            <NavLink to="/alfa/analysis" icon="🔍" label="Analysis" />
            <NavLink to="/alfa/health" icon="❤️" label="System Health" />
            <NavLink to="/alfa/admin" icon="⚙️" label="Admin" />
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-slate-800">
            <div className="text-xs text-slate-400 space-y-1">
              <p>Players: <span className="text-sky-400">{stats?.total_players || 0}</span></p>
              <p>Anomalies: <span className="text-yellow-400">{stats?.anomalies_detected || 0}</span></p>
              <p>Health: <span className="text-emerald-400">{stats?.system_health_score.toFixed(0) || 0}%</span></p>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navbar */}
        <nav className="h-16 bg-slate-900 border-b border-slate-800 px-6 flex items-center justify-between">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="md:hidden p-2 hover:bg-slate-800 rounded-lg"
          >
            {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>

          <h2 className="text-lg font-semibold text-slate-pool_opt_in">Alfa Rating System</h2>

          <div className="flex items-center gap-4">
            <div className="text-xs text-slate-400">
              <p className="font-mono">v2.1</p>
            </div>
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-sky-500" />
          </div>
        </nav>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-6">
            <Outlet />
          </div>
        </div>

        {/* Footer */}
        <div className="h-12 bg-slate-900 border-t border-slate-800 px-6 flex items-center justify-between text-xs text-slate-500">
          <p>Last updated: {lastUpdate}</p>
          <p>Alfa Rating System © 2026</p>
        </div>
      </div>
    </div>
  )
}

interface NavLinkProps {
  to: string
  icon: string
  label: string
}

const NavLink: React.FC<NavLinkProps> = ({ to, icon, label }) => {
  return (
    <a
      href={to}
      className="flex items-center gap-3 px-4 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 hover:text-sky-400 transition-colors"
    >
      <span className="text-lg">{icon}</span>
      {label}
    </a>
  )
}

export default AlfaDashboardLayout
