import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchAnalysis, fetchRoadmap, updateRoadmapItem, fetchAtsKeywords, updateAtsKeyword } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AgentBubble from '../components/AgentBubble'
import { ArrowLeftIcon, TrendingUpIcon, AlertCircleIcon, MapIcon, SearchIcon, TagIcon, CheckIcon, XIcon } from 'lucide-react'
import type { RoadmapItem, AtsKeywordItem } from '../types'

const demandColor = { alto: 'bg-green-100 text-green-700', medio: 'bg-yellow-100 text-yellow-700', basso: 'bg-red-100 text-red-600' }
const priorityColor = { alta: 'bg-red-100 text-red-600', media: 'bg-yellow-100 text-yellow-700', bassa: 'bg-gray-100 text-gray-600' }
const categoryIcon: Record<string, string> = { portfolio: '📁', certificazione: '🏆', network: '🔗', candidatura: '📤', formazione: '📚' }

const searchUrl = (title: string, provider: string) =>
  `https://www.google.com/search?q=${encodeURIComponent(`${title} ${provider} corso`)}`

export default function AnalysisDetail() {
  const { id, analysisId } = useParams<{ id: string; analysisId: string }>()
  const cvId = Number(id)
  const aId = Number(analysisId)

  const qc = useQueryClient()

  const { data: record } = useQuery({
    queryKey: ['analysis', cvId, aId],
    queryFn: () => fetchAnalysis(cvId, aId),
    refetchInterval: (q) => q.state.data?.status === 'analyzing' ? 2000 : false,
  })

  const { data: roadmap = [] } = useQuery({
    queryKey: ['roadmap', cvId],
    queryFn: () => fetchRoadmap(cvId),
    enabled: !!cvId,
    refetchInterval: () => (record?.status === 'analyzing' ? 3000 : false),
  })

  const setItemStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: RoadmapItem['status'] }) =>
      updateRoadmapItem(cvId, id, status),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ['roadmap', cvId] })
      const prev = qc.getQueryData<RoadmapItem[]>(['roadmap', cvId])
      qc.setQueryData<RoadmapItem[]>(['roadmap', cvId], (old) =>
        (old ?? []).map(it => (it.id === id ? { ...it, status } : it)))
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(['roadmap', cvId], ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['roadmap', cvId] }),
  })

  const { data: atsItems = [] } = useQuery({
    queryKey: ['ats', cvId],
    queryFn: () => fetchAtsKeywords(cvId),
    enabled: !!cvId,
    refetchInterval: () => (record?.status === 'analyzing' ? 3000 : false),
  })

  const setAtsStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: AtsKeywordItem['status'] }) =>
      updateAtsKeyword(cvId, id, status),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: ['ats', cvId] })
      const prev = qc.getQueryData<AtsKeywordItem[]>(['ats', cvId])
      qc.setQueryData<AtsKeywordItem[]>(['ats', cvId], (old) =>
        (old ?? []).map(it => (it.id === id ? { ...it, status } : it)))
      return { prev }
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) qc.setQueryData(['ats', cvId], ctx.prev) },
    onSettled: () => qc.invalidateQueries({ queryKey: ['ats', cvId] }),
  })

  if (!record) return <div className="p-8 text-gray-400">Caricamento...</div>

  const a = record.analysis
  const activeItems = roadmap.filter(it => it.status !== 'dismissed')
  const dismissedItems = roadmap.filter(it => it.status === 'dismissed')
  const doneCount = activeItems.filter(it => it.status === 'done').length
  const atsTodo = atsItems.filter(k => k.status === 'todo')
  const atsHandled = atsItems.filter(k => k.status !== 'todo')

  return (
    <div className="p-4 md:p-8 max-w-6xl">
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
        message={record.status === 'analyzing'
          ? 'Sto analizzando il tuo CV e costruendo la tua strategia di carriera...'
          : 'Sono Minerva. Analizzo il tuo profilo e disegno la rotta verso i ruoli più adatti a te.'}
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
          {/* Executive summary - tutta larghezza */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-2">Executive Summary</h2>
            <p className="text-gray-700 leading-relaxed">{a.executive_summary}</p>
          </div>

          {/* Due colonne: sinistra = ruoli+skill+ATS, destra = roadmap sticky */}
          <div className="grid lg:grid-cols-2 gap-6 items-start">

          {/* ── Colonna sinistra ─────────────────────────────── */}
          <div className="space-y-6">

          {/* Target roles — importanza (domanda) a sinistra, % a destra */}
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
                    {gap.resources && gap.resources.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {gap.resources.map((r, j) => (
                          <a
                            key={j}
                            href={searchUrl(r.title, r.provider)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors max-w-full"
                            title={`Cerca: ${r.title} · ${r.provider}`}
                          >
                            <SearchIcon size={11} className="text-gray-400 shrink-0" />
                            <span className="font-medium text-gray-700 truncate min-w-0">{r.title}</span>
                            <span className="text-gray-400 shrink-0">· {r.provider}</span>
                            <span className={`shrink-0 px-1.5 py-0.5 rounded-full font-medium ${
                              r.cost === 'gratuito' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'
                            }`}>
                              {r.cost}
                            </span>
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Keyword ATS — checklist interattiva */}
          {atsItems.length > 0 && (
            <div className="bg-white rounded-xl border border-amber-200 p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-amber-600 mb-1">
                <TagIcon size={15} /> Keyword ATS da aggiungere al CV
              </h2>
              <p className="text-xs text-gray-400 mb-4">
                Termini che i filtri ATS cercano per i tuoi ruoli target. Per ognuna:
                <b className="text-green-700"> Aggiunta</b> (l'hai scritta nel CV),
                <b className="text-gray-500"> Ce l'ho già</b> (la possiedi / falso positivo),
                <b className="text-amber-700"> Da acquisire</b> (competenza che ti manca davvero). Al ricalcolo non te le riproporrà.
              </p>

              {atsTodo.length === 0 ? (
                <p className="text-sm text-gray-400">Tutte gestite 🎉</p>
              ) : (
                <div className="space-y-2">
                  {atsTodo.map((k) => (
                    <div key={k.id} className="p-2.5 rounded-lg border border-gray-100">
                      <div className="flex gap-2 items-start">
                        <span className="px-2.5 py-1 bg-amber-50 text-amber-700 text-xs font-semibold rounded-md shrink-0">
                          {k.keyword}
                        </span>
                        <p className="text-xs text-gray-500 mt-1 leading-relaxed flex-1 min-w-0">{k.reason}</p>
                      </div>
                      <div className="flex gap-1.5 mt-2">
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'added' })}
                          title="L'ho scritta nel CV"
                          className="px-2 py-1 text-xs rounded-md bg-green-50 text-green-700 hover:bg-green-100 font-medium"
                        >
                          Aggiunta
                        </button>
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'ignored' })}
                          title="La possiedo già / falso positivo"
                          className="px-2 py-1 text-xs rounded-md bg-gray-100 text-gray-500 hover:bg-gray-200 font-medium"
                        >
                          Ce l'ho già
                        </button>
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'gap' })}
                          title="Competenza che mi manca davvero — devo impararla"
                          className="px-2 py-1 text-xs rounded-md bg-amber-50 text-amber-700 hover:bg-amber-100 font-medium"
                        >
                          Da acquisire
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {atsHandled.length > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-2">Gestite · non verranno riproposte ({atsHandled.length})</p>
                  <ul className="space-y-1">
                    {atsHandled.map(k => {
                      const badge = k.status === 'added'
                        ? { label: 'aggiunta', cls: 'bg-green-100 text-green-700' }
                        : k.status === 'gap'
                        ? { label: 'da acquisire', cls: 'bg-amber-100 text-amber-700' }
                        : { label: 'già presente', cls: 'bg-gray-100 text-gray-500' }
                      return (
                        <li key={k.id} className="flex items-center gap-2 text-xs">
                          <span className={`px-1.5 py-0.5 rounded font-medium shrink-0 ${badge.cls}`}>{badge.label}</span>
                          <span className="text-gray-600 truncate flex-1 min-w-0">{k.keyword}</span>
                          {k.status === 'added' && (
                            <span className="text-gray-400 shrink-0">
                              {new Date(k.updated_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}
                            </span>
                          )}
                          <button
                            onClick={() => setAtsStatus.mutate({ id: k.id, status: 'todo' })}
                            className="text-blue-500 hover:underline shrink-0"
                          >
                            ripristina
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
            </div>
          )}

          </div>{/* fine colonna sinistra */}

          {/* ── Colonna destra: checklist roadmap sempre visibile ── */}
          <div className="lg:sticky lg:top-6">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400">
                  <MapIcon size={15} /> Roadmap
                </h2>
                {activeItems.length > 0 && (
                  <span className="text-xs text-gray-400">{doneCount}/{activeItems.length} fatte</span>
                )}
              </div>

              {activeItems.length === 0 ? (
                <p className="text-sm text-gray-400">Nessuna attività in lista.</p>
              ) : (
                <ul className="space-y-1">
                  {activeItems.map((item, idx) => (
                    <li key={item.id} className="flex gap-3 group">
                      <button
                        onClick={() => setItemStatus.mutate({ id: item.id, status: item.status === 'done' ? 'todo' : 'done' })}
                        className={`mt-1 w-6 h-6 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                          item.status === 'done' ? 'bg-green-500 border-green-500 text-white' : 'border-gray-300 hover:border-green-400'
                        }`}
                        title={item.status === 'done' ? 'Segna da fare' : 'Segna completata'}
                      >
                        {item.status === 'done'
                          ? <CheckIcon size={13} />
                          : <span className="text-[10px] text-gray-400">{idx + 1}</span>}
                      </button>
                      <div className="flex-1 py-1 pb-3 border-b border-gray-100 last:border-0">
                        <div className="flex items-start gap-2">
                          <span className="shrink-0">{categoryIcon[item.category] ?? '📌'}</span>
                          <span className={`font-medium text-sm capitalize ${item.status === 'done' ? 'text-gray-400 line-through' : 'text-gray-900'}`}>
                            {item.action}
                          </span>
                          <button
                            onClick={() => setItemStatus.mutate({ id: item.id, status: 'dismissed' })}
                            title="Non lo farò mai — non riproporlo"
                            className="ml-auto text-gray-300 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0"
                          >
                            <XIcon size={14} />
                          </button>
                        </div>
                        {(item.impact || item.timeframe) && (
                          <div className="flex items-center gap-3 mt-1 pl-6">
                            {item.impact && <span className="text-xs text-gray-400">{item.impact}</span>}
                            {item.timeframe && <span className="text-xs text-blue-600 font-medium">⏱ {item.timeframe}</span>}
                          </div>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              )}

              {dismissedItems.length > 0 && (
                <div className="mt-4 pt-3 border-t border-gray-100">
                  <p className="text-xs text-gray-400 mb-2">Annullate · non verranno riproposte ({dismissedItems.length})</p>
                  <ul className="space-y-1">
                    {dismissedItems.map(item => (
                      <li key={item.id} className="flex items-center gap-2 text-xs text-gray-400">
                        <XIcon size={11} className="shrink-0" />
                        <span className="line-through truncate">{item.action}</span>
                        <button
                          onClick={() => setItemStatus.mutate({ id: item.id, status: 'todo' })}
                          className="ml-auto text-blue-500 hover:underline shrink-0"
                        >
                          ripristina
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>{/* fine colonna destra */}

          </div>{/* fine grid due colonne */}
        </div>
      )}
    </div>
  )
}
