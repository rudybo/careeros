import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchAnalysis } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AgentBubble from '../components/AgentBubble'
import { ArrowLeftIcon, TrendingUpIcon, ListChecksIcon } from 'lucide-react'

const demandColor = { alto: 'bg-green-100 text-green-700', medio: 'bg-yellow-100 text-yellow-700', basso: 'bg-red-100 text-red-600' }

export default function AnalysisDetail() {
  const { id, analysisId } = useParams<{ id: string; analysisId: string }>()
  const navigate = useNavigate()
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
    <div className="p-4 pb-24 md:p-8 max-w-3xl">
      <Link to={`/cv/${cvId}`} className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Torna al CV
      </Link>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Analisi carriera</h1>
        <StatusBadge status={record.status} />
      </div>

      <AgentBubble
        name="Minerva"
        active={record.status === 'analyzing'}
        message={
          record.status === 'analyzing'
            ? 'Sto analizzando il tuo CV e costruendo la tua strategia di carriera...'
            : a
            ? `Elaborazione completata: ${a.target_roles.length} ruoli target, ${a.skill_gaps.length} skill da colmare, ${a.ats_keywords.length} keyword ATS. Vuoi aprire la tua to-do?`
            : 'Sono Minerva. Analizzo il tuo profilo e disegno la rotta verso i ruoli più adatti a te.'
        }
        action={a ? { label: 'Apri Attività →', onClick: () => navigate('/attivita') } : undefined}
      />

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

          {/* Ruoli target — importanza (domanda) + % match a sinistra, dettagli a destra */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
              <TrendingUpIcon size={15} /> Ruoli target
            </h2>
            <div className="space-y-3">
              {a.target_roles.map((role, i) => (
                <div key={i} className="flex items-start gap-3 p-3 rounded-lg bg-gray-50">
                  <div className="flex flex-col items-center gap-1 shrink-0 w-16">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium w-full text-center ${demandColor[role.market_demand] ?? 'bg-gray-100 text-gray-600'}`}>
                      {role.market_demand}
                    </span>
                    <span className="text-sm font-bold text-blue-600">{role.match_percentage}%</span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium text-gray-900 text-sm break-words">{role.title}</div>
                    <div className="text-xs text-gray-500 mt-0.5 break-words">{role.reason}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Link alla to-do di carriera (roadmap, skill gap, keyword ATS) */}
          <Link
            to="/attivita"
            className="flex items-center justify-between gap-3 bg-gradient-to-br from-violet-50 to-blue-50 border border-violet-200 rounded-xl p-5 hover:border-violet-300 transition-colors"
          >
            <div className="flex items-center gap-3 min-w-0">
              <ListChecksIcon size={20} className="text-violet-600 shrink-0" />
              <div className="min-w-0">
                <div className="font-semibold text-gray-900 text-sm">Vai alle Attività</div>
                <div className="text-xs text-gray-500 break-words">Roadmap, skill gap con corsi e keyword ATS sono nella tua to-do di carriera.</div>
              </div>
            </div>
            <span className="text-violet-600 text-sm font-medium shrink-0">Apri →</span>
          </Link>
        </div>
      )}
    </div>
  )
}
