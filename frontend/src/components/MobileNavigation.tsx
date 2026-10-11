import { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'

interface NavItem {
  path: string
  label: string
  icon: string
}

const HOME_URL = 'https://www.probilliardssoftware.com'
const navItems: NavItem[] = [
  { path: '/', label: 'Dashboard', icon: '📈' },
  { path: '/trades', label: 'Trades', icon: '💰' },
  { path: '/settings', label: 'Settings', icon: '⚙️' },
  { path: '/system', label: 'System', icon: '🖥️' },
  { path: '/ai', label: 'AI', icon: '🤖' },
  { path: '/tax', label: 'Tax', icon: '📊' },
]

export default function MobileNavigation() {
  const location = useLocation()
  const [isOpen, setIsOpen] = useState(false)

  return (
    <>
      {/* Mobile Menu Button */}
      <div className="md:hidden fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-3 bg-card/90 backdrop-blur-sm border border-border rounded-full shadow-lg"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {isOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile Menu */}
      {isOpen && (
        <div className="md:hidden fixed bottom-20 left-1/2 transform -translate-x-1/2 z-50">
          <div className="bg-card/95 backdrop-blur-sm border border-border rounded-lg shadow-xl p-2 min-w-[200px]">
            <div className="grid grid-cols-2 gap-2">
              {navItems.map((item) => {
                const isActive = location.pathname === item.path
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setIsOpen(false)}
                    className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'
                    }`}
                  >
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-xl">{item.icon}</span>
                      <span>{item.label}</span>
                    </div>
                  </Link>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
