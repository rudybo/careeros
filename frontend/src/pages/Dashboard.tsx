import { useState, type ReactNode } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCVList, fetchApplicationList, fetchSystemHealth, restartSystem } from '../api/client'
import { BriefcaseIcon, FileTextIcon, TrendingUpIcon, TargetIcon, XIcon, ActivityIcon, RotateCwIcon, CheckCircle2Icon, AlertTriangleIcon, Loader2Icon } from 'lucide-react'
import AgentAvatar from '../components/AgentAvatar'
import type { JobApplication } from '../types'

const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString('it-IT', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '—'

function HealthRow({ label, ok, children }: { label: string; ok: boolean | null; children: ReactNode }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`w-2 h-2 rounded-full shrink-0 ${ok === null ? 'bg-gray-300' : ok ? 'bg-green-500' : 'bg-red-500'}`} />
      <span className="text-gray-500 w-28 shrink-0">{label}</span>
      <span className="text-gray-700 truncate">{children}</span>
    </div>
  )
}

function SystemHealthPanel() {
  const qc = useQueryClient()
  const [restarting, setRestarting] = useState(false)
  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchSystemHealth,
    refetchInterval: restarting ? false : 20000,
  })
  const restart = useMutation({
    mutationFn: restartSystem,
    onSuccess: () => {
      setRestarting(true)
      setTimeout(() => { setRestarting(false); qc.invalidateQueries({ queryKey: ['health'] }) }, 12000)
    },
  })

  const nextRun = (health?.scheduler.jobs ?? []).filter(j => j.id.startsWith('iris')).map(j => j.next_run).filter(Boolean).sort()[0]
  const overall: boolean | null = restarting ? null : (health?.ok ?? null)

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 mb-8">
      <div className="flex items-center justify-between gap-3 mb-4">
        <h2 className="font-semibold text-gray-900 flex items-center gap-2">
          <ActivityIcon size={16} className="text-gray-400" /> Stato sistema
        </h2>
        <div className="flex items-center gap-3 shrink-0">
          <span className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ${
            restarting ? 'bg-blue-50 text-blue-600' : overall ? 'bg-green-50 text-green-700' : overall === false ? 'bg-red-50 text-red-600' : 'bg-gray-100 text-gray-500'
          }`}>
            {restarting ? <><Loader2Icon size={12} className="animate-spin" /> Riavvio…</>
              : overall ? <><CheckCircle2Icon size={12} /> Operativo</>
              : overall === false ? <><AlertTriangleIcon size={12} /> Problema</>
              : 'Caricamento…'}
          </span>
          <button onClick={() => { if (window.confirm('Riavviare il backend? Richiede ~10 secondi.')) restart.mutate() }}
            disabled={restarting || restart.isPending}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium border border-gray-300 rounded-lg hover:border-red-300 hover:text-red-600 transition-colors disabled:opacity-50">
            <RotateCwIcon size={13} /> Riavvia
          </button>
        </div>
      </div>
      {restarting ? (
        <p className="text-sm text-gray-400">Riavvio in corso, attendi qualche secondo…</p>
      ) : (
        <div className="space-y-2">
          <HealthRow label="Motore AI" ok={health ? true : null}>
            {health ? `${health.llm.provider} · ${health.llm.model}` : '—'}
          </HealthRow>
          <HealthRow label="Ricerca auto" ok={health?.scheduler.running ?? null}>
            {health?.scheduler.running ? `attiva · prossima ${fmtDate(nextRun)}` : 'non attiva'}
          </HealthRow>
          <HealthRow label="Telegram" ok={health ? (health.telegram.alive || !health.telegram.enabled) : null}>
            {!health ? '—' : !health.telegram.enabled ? 'non configurato' : health.telegram.alive ? `connesso · ultimo controllo ${health.telegram.seconds_ago}s fa` : 'bloccato'}
          </HealthRow>
          <HealthRow label="Ultima ricerca" ok={health?.last_search ? !health.last_search.error : null}>
            {health?.last_search ? `${fmtDate(health.last_search.at)} · ${health.last_search.error ? 'errore' : `${health.last_search.created} nuove`}` : 'nessuna ancora'}
          </HealthRow>
        </div>
      )}
    </div>
  )
}

const AGENTS = [
  {
    name: 'Minerva',
    role: 'Career Strategist',
    color: 'bg-violet-100 text-violet-700',
    dot: 'bg-violet-500',
    description: 'Analizza il tuo CV e identifica i ruoli più adatti al tuo profilo. Costruisce una roadmap di carriera personalizzata con i gap di competenze da colmare e i passi concreti da seguire.',
    trigger: 'Si attiva dalla pagina CV → "Analizza carriera"',
  },
  {
    name: 'Vera',
    role: 'CV Expert',
    color: 'bg-blue-100 text-blue-700',
    dot: 'bg-blue-500',
    description: 'Ottimizza il tuo CV per una specifica offerta di lavoro. Calcola il match score ATS, individua le keyword mancanti, segnala problemi di formato e suggerisce miglioramenti sezione per sezione.',
    trigger: 'Si attiva dalla pagina Candidature → analisi di una posizione',
  },
  {
    name: 'Clio',
    role: 'Cover Letter',
    color: 'bg-pink-100 text-pink-700',
    dot: 'bg-pink-500',
    description: 'Genera lettere di presentazione su misura per ogni candidatura. Usa i suggerimenti di Vera per personalizzare tono e contenuto, e crea una bozza pronta in Gmail con un clic.',
    trigger: 'Si attiva dalla pagina Candidature → "Genera cover letter" · oppure da Market Scout → icona busta',
  },
  {
    name: 'Iris',
    role: 'Market Scout',
    color: 'bg-orange-100 text-orange-700',
    dot: 'bg-orange-500',
    description: 'Cerca offerte di lavoro su Adzuna e Jooble in base ai tuoi ruoli target e preferenze salariali. Ranka ogni annuncio per compatibilità con il tuo profilo e lancia ricerche automatiche ogni mattina alle 08:00 e ogni sera alle 19:00.',
    trigger: 'Si attiva dalla pagina Market Scout → "Avvia ricerca" · oppure in automatico 2× al giorno',
  },
]

function AgentsModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-5xl overflow-hidden max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">I tuoi agenti AI</h2>
          <button onClick={onClose} className="p-1.5 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100">
            <XIcon size={16} />
          </button>
        </div>
        <img src="/agents/group.png" alt="Le agenti di CareerOS" className="w-full max-h-72 object-cover" style={{ objectPosition: '50% 28%' }} />
        <div className="p-6 grid grid-cols-1 md:grid-cols-2 gap-5">
          {AGENTS.map(a => (
            <div key={a.name} className="flex gap-4">
              <AgentAvatar name={a.name as any} size={64} />
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-semibold text-gray-900">{a.name}</span>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${a.color}`}>{a.role}</span>
                </div>
                <p className="text-sm text-gray-600 leading-relaxed">{a.description}</p>
                <p className="text-xs text-gray-400 mt-1.5 italic">{a.trigger}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

const STATUS_ORDER: JobApplication['status'][] = ['offer', 'interview', 'applied', 'ready', 'draft']

export default function Dashboard() {
  const [showAgents, setShowAgents] = useState(false)
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
    { label: 'Agenti attivi',  value: 4,                 sub: 'Minerva · Vera · Clio · Iris', icon: TargetIcon, color: 'text-orange-600', bg: 'bg-orange-50' },
  ]

  return (
    <div className="p-4 md:p-8">
      {showAgents && <AgentsModal onClose={() => setShowAgents(false)} />}

      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 mt-1">Panoramica della tua ricerca lavoro</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map(({ label, value, sub, icon: Icon, color, bg }) => {
          const isAgents = label === 'Agenti attivi'
          return (
            <div
              key={label}
              onClick={isAgents ? () => setShowAgents(true) : undefined}
              className={`bg-white rounded-xl border border-gray-200 p-5 ${isAgents ? 'cursor-pointer hover:border-orange-300 hover:shadow-sm transition-all' : ''}`}
            >
              <div className={`w-10 h-10 ${bg} ${color} rounded-lg flex items-center justify-center mb-3`}>
                <Icon size={20} />
              </div>
              <div className="text-2xl font-bold text-gray-900">{value}</div>
              <div className="text-sm font-medium text-gray-700">{label}</div>
              <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
            </div>
          )
        })}
      </div>

      {/* Stato sistema */}
      <SystemHealthPanel />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
