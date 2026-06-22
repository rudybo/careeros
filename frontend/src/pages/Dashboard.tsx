import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCVList, fetchApplicationList } from '../api/client'
import { BriefcaseIcon, FileTextIcon, TrendingUpIcon, TargetIcon } from 'lucide-react'
import type { JobApplication } from '../types'

const STATUS_ORDER: JobApplication['status'][] = ['offer', 'interview', 'applied', 'ready', 'draft']

export default function Dashboard() {
  const { data: cvs = [] } = useQuery({ queryKey: ['cvs'], queryFn: fetchCVList })
  const { data: apps = [] } = useQuery({ queryKey: ['applications'], queryFn: fetchApplicationList })

  const parsedCVs = cvs.filter(c => c.status === 'parsed').length
  const readyApps = apps.filter(a => ['ready', 'applied', 'interview', 'offer'].includes(a.status))
  const bestStatus = apps.reduce((best: string, app) => {
    const bi = STATUS_ORDER.indexOf(best as JobApplication['status'])
    const ai = STATUS_ORDER.indexOf(app.status as JobApplication['status'])
    return ai < bi ? app.status : best
  }, 'draft')

  const stats = [
    { label: 'CV caricati',    value: cvs.length,        sub: `${parsedCVs} parsati`,    icon: FileTextIcon,    color: 'text-blue-600',   bg: 'bg-blue-50' },
    { label: 'Candidature',    value: apps.length,       sub: `${readyApps.length} analizzate`, icon: BriefcaseIcon, color: 'text-purple-600', bg: 'bg-purple-50' },
    { label: 'Migliore stato', value: bestStatus === 'draft' ? '—' : bestStatus, sub: 'tra le candidature', icon: TrendingUpIcon, color: 'text-green-600', bg: 'bg-green-50' },
    { label: 'Agenti attivi',  value: 2,                 sub: 'Career Strategist + CV Expert', icon: TargetIcon, color: 'text-orange-600', bg: 'bg-orange-50' },
  ]

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Panoramica della tua ricerca lavoro</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, sub, icon: Icon, color, bg }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5">
            <div className={`w-10 h-10 ${bg} ${color} rounded-lg flex items-center justify-center mb-3`}>
              <Icon size={20} />
            </div>
            <div className="text-2xl font-bold text-gray-900">{value}</div>
            <div className="text-sm font-medium text-gray-700">{label}</div>
            <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Recent CVs */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">CV recenti</h2>
            <Link to="/cv" className="text-sm text-blue-600 hover:underline">Vedi tutti</Link>
          </div>
          {cvs.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <FileTextIcon size={32} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">Nessun CV caricato</p>
              <Link to="/cv" className="text-sm text-blue-600 hover:underline mt-1 block">Carica il primo CV</Link>
            </div>
          ) : (
            <ul className="space-y-2">
              {cvs.slice(0, 4).map(cv => (
                <li key={cv.id}>
                  <Link to={`/cv/${cv.id}`} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                    <span className="text-sm text-gray-700 truncate">{cv.filename}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${cv.status === 'parsed' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {cv.status}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Recent Applications */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">Candidature recenti</h2>
            <Link to="/applications" className="text-sm text-blue-600 hover:underline">Vedi tutte</Link>
          </div>
          {apps.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <BriefcaseIcon size={32} className="mx-auto mb-2 opacity-50" />
              <p className="text-sm">Nessuna candidatura</p>
              <Link to="/applications" className="text-sm text-blue-600 hover:underline mt-1 block">Crea la prima candidatura</Link>
            </div>
          ) : (
            <ul className="space-y-2">
              {apps.slice(0, 4).map(app => (
                <li key={app.id}>
                  <Link to={`/applications/${app.id}`} className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50">
                    <div>
                      <div className="text-sm font-medium text-gray-700">{app.role}</div>
                      <div className="text-xs text-gray-400">{app.company}</div>
                    </div>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      app.status === 'offer' ? 'bg-emerald-100 text-emerald-700' :
                      app.status === 'interview' ? 'bg-purple-100 text-purple-700' :
                      app.status === 'ready' ? 'bg-green-100 text-green-700' :
                      'bg-gray-100 text-gray-500'
                    }`}>
                      {app.status}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
