import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchAnalysis } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { ArrowLeftIcon, TrendingUpIcon, AlertCircleIcon, MapIcon } from 'lucide-react'

const demandColor = { alto: 'bg-green-100 text-green-700', medio: 'bg-yellow-100 text-yellow-700', basso: 'bg-red-100 text-red-600' }
const priorityColor = { alta: 'bg-red-100 text-red-600', media: 'bg-yellow-100 text-yellow-700', bassa: 'bg-gray-100 text-gray-600' }
const categoryIcon: Record<string, string> = { portfolio: '📁', certificazione: '🏆', network: '🔗', candidatura: '📤', formazione: '📚' }

export default function AnalysisDetail() {
  const { id, analysisId } = useParams<{ id: string; analysisId: string }>()
  const cvId = Number(id)
  const aId = Number(analysisId)

  const { data: record } = useQuery({
    queryKey: ['analysis', cvId, aId],
    queryFn: () => fetchAnalysis(cvId, aId),
    refetchInterval: (q) => q.state.data?.status === 'analyzing' ? 2000 : false,
  })

  if (!record) return <div className="p-8 text-gray-400">Caricamento...</div>

  const a = record.analysis

  return (
    <div className="p-8 max-w-4xl">
      <Link to={`/cv/${cvId}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Torna al CV
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analisi carriera</h1>
        <StatusBadge status={record.status} />
      </div>

      {record.status === 'analyzing' && (
        <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700 mb-6">
          Il Career Strategist sta elaborando il tuo profilo... (1-3 minuti). La pagina si aggiorna automaticamente.
        </div>
      )}

      {record.status === 'error' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 mb-6">
          L'analisi non è riuscita. Riprova dalla pagina del CV.
        </div>
      )}

      {a && (
        <div className="space-y-6">
          {/* Executive summary */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-2">Executive Summary</h2>
            <p className="text-gray-700 leading-relaxed">{a.executive_summary}</p>
          </div>

          {/* Target roles */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
              <TrendingUpIcon size={15} /> Ruoli target
            </h2>
            <div className="space-y-3">
              {a.target_roles.map((role, i) => (
                <div key={i} className="flex items-center gap-4 p-3 rounded-lg bg-gray-50">
                  <div className="w-12 h-12 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm shrink-0">
                    {role.match_percentage}%
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 text-sm">{role.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5 truncate">{role.reason}</div>
                  </div>
                  <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${demandColor[role.market_demand] ?? 'bg-gray-100 text-gray-600'}`}>
                    {role.market_demand}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Skill gaps */}
          {a.skill_gaps.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                <AlertCircleIcon size={15} /> Skill gap da colmare
              </h2>
              <div className="space-y-3">
                {a.skill_gaps.map((gap, i) => (
                  <div key={i} className="p-3 rounded-lg border border-gray-100">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${priorityColor[gap.priority] ?? 'bg-gray-100 text-gray-600'}`}>
                        {gap.priority}
                      </span>
                      <span className="font-medium text-sm text-gray-900">{gap.skill}</span>
                      <span className="text-xs text-gray-400 ml-auto">{gap.estimated_time}</span>
                    </div>
                    <p className="text-xs text-gray-500">{gap.why_needed}</p>
                    <p className="text-xs text-blue-600 mt-1">→ {gap.how_to_acquire}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Roadmap */}
          {a.roadmap.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                <MapIcon size={15} /> Roadmap
              </h2>
              <ol className="space-y-3">
                {a.roadmap.map((step) => (
                  <li key={step.order} className="flex gap-4">
                    <div className="w-7 h-7 rounded-full bg-blue-600 text-white flex items-center justify-center text-xs font-bold shrink-0">
                      {step.order}
                    </div>
                    <div className="flex-1 pb-3 border-b border-gray-100 last:border-0">
                      <div className="flex items-center gap-2">
                        <span>{categoryIcon[step.category] ?? '📌'}</span>
                        <span className="font-medium text-sm text-gray-900 capitalize">{step.action}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-1">
                        <span className="text-xs text-gray-400">{step.impact}</span>
                        <span className="text-xs text-blue-600 font-medium">⏱ {step.timeframe}</span>
                      </div>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
