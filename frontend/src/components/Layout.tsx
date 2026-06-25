import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { NavLink, Outlet } from 'react-router-dom'
import { BriefcaseIcon, FileTextIcon, LayoutDashboardIcon, MoonIcon, SunIcon, TrendingUpIcon } from 'lucide-react'
import { fetchInfo } from '../api/client'

const nav = [
  { to: '/',            label: 'Dashboard',   icon: LayoutDashboardIcon },
  { to: '/cv',          label: 'Curriculum',  icon: FileTextIcon },
  { to: '/applications',label: 'Candidature', icon: BriefcaseIcon },
  { to: '/market',      label: 'Market Scout', icon: TrendingUpIcon },
]

function useDarkMode() {
  const [dark, setDark] = useState(() => localStorage.getItem('theme') === 'dark')
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('theme', dark ? 'dark' : 'light')
  }, [dark])
  return [dark, setDark] as const
}

export default function Layout() {
  const [dark, setDark] = useDarkMode()
  const { data: info } = useQuery({ queryKey: ['info'], queryFn: fetchInfo, staleTime: Infinity })
  const isCloud = info?.provider === 'groq'
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
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-1.5 min-w-0"
              title={info ? `${info.provider} · ${info.model}` : ''}>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${isCloud ? 'bg-green-400' : 'bg-sky-400'}`} />
              <span className="text-gray-400 text-xs truncate">
                {info ? (isCloud ? 'Groq · cloud' : 'Ollama · locale') : '…'}
              </span>
            </div>
            <button onClick={() => setDark(d => !d)}
              className="p-1.5 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-800 shrink-0"
              title={dark ? 'Modalità chiara' : 'Modalità scura'}>
              {dark ? <SunIcon size={14} /> : <MoonIcon size={14} />}
            </button>
          </div>
          <span className="block text-gray-600 text-[10px] mt-1 truncate" title={info?.model}>
            v0.1.0 · {info?.model ?? '—'}
          </span>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
