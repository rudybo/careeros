import { NavLink, Outlet } from 'react-router-dom'
import { BriefcaseIcon, FileTextIcon, LayoutDashboardIcon } from 'lucide-react'

const nav = [
  { to: '/',            label: 'Dashboard',   icon: LayoutDashboardIcon },
  { to: '/cv',          label: 'Curriculum',  icon: FileTextIcon },
  { to: '/applications',label: 'Candidature', icon: BriefcaseIcon },
]

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 flex flex-col">
        <div className="px-5 py-6 border-b border-gray-700">
          <span className="text-white font-bold text-lg tracking-tight">CareerOS</span>
          <span className="block text-gray-400 text-xs mt-0.5">AI Career Platform</span>
        </div>
        <nav className="flex-1 p-3 space-y-1">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800'
                }`
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700">
          <span className="text-gray-500 text-xs">v0.1.0 · llama3.2</span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
