import { useState } from 'react'
import { NavLink } from 'react-router-dom'

interface NavItem {
  to: string
  label: string
  icon: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: 'D' },
  { to: '/scan', label: 'Scan', icon: 'S' },
  { to: '/watchlist', label: 'Watchlist', icon: 'W' },
  { to: '/universe', label: 'Universe', icon: 'U' },
  { to: '/settings', label: 'Settings', icon: 'G' },
]

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={`flex flex-col border-r transition-all duration-200 ${
        collapsed ? 'w-12' : 'w-48'
      }`}
      style={{
        backgroundColor: 'var(--color-bg-secondary)',
        borderColor: 'var(--color-border-default)',
      }}
    >
      {/* Brand */}
      <div
        className="flex items-center border-b px-3 py-2"
        style={{ borderColor: 'var(--color-border-default)' }}
      >
        {!collapsed && (
          <span
            className="font-data text-sm font-bold tracking-wider"
            style={{ color: 'var(--color-text-accent)' }}
          >
            OPTION ALPHA
          </span>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className={`font-data text-xs ${collapsed ? 'mx-auto' : 'ml-auto'}`}
          style={{ color: 'var(--color-text-muted)' }}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? '>>' : '<<'}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex flex-1 flex-col gap-0.5 p-1">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-2 px-2 py-1.5 text-xs font-medium transition-colors ${
                isActive ? 'nav-active' : 'nav-inactive'
              }`
            }
            style={({ isActive }) => ({
              backgroundColor: isActive
                ? 'var(--color-bg-hover)'
                : 'transparent',
              color: isActive
                ? 'var(--color-text-primary)'
                : 'var(--color-text-secondary)',
              borderLeft: isActive
                ? '2px solid var(--color-interactive)'
                : '2px solid transparent',
            })}
          >
            <span className="font-data w-4 text-center">{item.icon}</span>
            {!collapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
