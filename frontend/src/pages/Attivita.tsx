import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCVList, fetchRoadmap, updateRoadmapItem, fetchAtsKeywords, updateAtsKeyword, fetchAnalysisList } from '../api/client'
import { MapIcon, TagIcon, CheckIcon, XIcon, ListChecksIcon, AlertCircleIcon, SearchIcon, CheckCircleIcon, CircleSlashIcon, GraduationCapIcon, GiftIcon, EuroIcon } from 'lucide-react'
import type { RoadmapItem, AtsKeywordItem } from '../types'

const categoryIcon: Record<string, string> = { portfolio: '📁', certificazione: '🏆', network: '🔗', candidatura: '📤', formazione: '📚' }
const priorityColor: Record<string, string> = { alta: 'bg-red-100 text-red-600', media: 'bg-yellow-100 text-yellow-700', bassa: 'bg-gray-100 text-gray-600' }

const searchUrl = (title: string, provider: string) =>
  `https://www.google.com/search?q=${encodeURIComponent(`${title} ${provider} corso`)}`

export default function Attivita() {
  const qc = useQueryClient()

  // La to-do è di carriera (globale): basta un CV "parsed" per interrogare gli endpoint,
  // che restituiscono comunque tutte le voci (get_all sul backend).
  const { data: cvs = [] } = useQuery({ queryKey: ['cvs'], queryFn: fetchCVList })
  const parsedCV = cvs.find(c => c.status === 'parsed')
  const cvId = parsedCV?.id ?? 0

  const { data: roadmap = [] } = useQuery({
    queryKey: ['roadmap', cvId],
    queryFn: () => fetchRoadmap(cvId),
    enabled: !!cvId,
    refetchInterval: 8000,  // riflette le analisi lanciate altrove
  })

  const { data: atsItems = [] } = useQuery({
    queryKey: ['ats', cvId],
    queryFn: () => fetchAtsKeywords(cvId),
    enabled: !!cvId,
    refetchInterval: 8000,
  })

  const { data: analyses = [] } = useQuery({
    queryKey: ['analyses', cvId],
    queryFn: () => fetchAnalysisList(cvId),
    enabled: !!cvId,
    refetchInterval: 8000,
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

  const activeItems = roadmap.filter(it => it.status !== 'dismissed')
  const dismissedItems = roadmap.filter(it => it.status === 'dismissed')
  const doneCount = activeItems.filter(it => it.status === 'done').length
  const atsTodo = atsItems.filter(k => k.status === 'todo')
  const atsHandled = atsItems.filter(k => k.status !== 'todo')
  const latestCompleted = [...analyses].sort((a, b) => b.id - a.id).find(a => a.status === 'completed')
  const skillGaps = latestCompleted?.analysis?.skill_gaps ?? []

  return (
    <div className="p-4 pb-24 md:p-8 max-w-3xl">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-bold text-gray-900">
          <ListChecksIcon size={24} className="text-violet-600" /> Attività di carriera
        </h1>
        <p className="text-gray-500 mt-1 text-sm">
          La tua to-do unica: roadmap e keyword ATS raccolte dalle analisi di Minerva. Si aggiorna a ogni ricalcolo.
        </p>
      </div>

      {!parsedCV ? (
        <div className="bg-white rounded-xl border border-gray-200 p-10 text-center text-gray-400">
          <ListChecksIcon size={36} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">Nessuna attività ancora. Carica e analizza un CV per popolare la tua to-do.</p>
        </div>
      ) : (
        <div className="space-y-6">

          {/* Roadmap */}
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
                        <div className="flex flex-wrap items-center gap-3 mt-1 pl-6">
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
                      <span className="line-through break-words min-w-0 flex-1">{item.action}</span>
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

          {/* Skill gap da colmare (con corsi) */}
          {skillGaps.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-4">
                <AlertCircleIcon size={15} /> Skill gap da colmare
              </h2>
              <div className="space-y-3">
                {skillGaps.map((gap, i) => (
                  <div key={i} className="p-3 rounded-lg border border-gray-100">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium shrink-0 ${priorityColor[gap.priority] ?? 'bg-gray-100 text-gray-600'}`}>
                        {gap.priority}
                      </span>
                      <span className="font-medium text-sm text-gray-900 flex-1 min-w-0 break-words">{gap.skill}</span>
                      <span className="text-xs text-gray-400 shrink-0">{gap.estimated_time}</span>
                    </div>
                    <p className="text-xs text-gray-500">{gap.why_needed}</p>
                    {(!gap.resources || gap.resources.length === 0) && (
                      <p className="text-xs text-blue-600 mt-1">→ {gap.how_to_acquire}</p>
                    )}
                    {gap.resources && gap.resources.length > 0 && (
                      <div className="space-y-1.5 mt-2">
                        {gap.resources.map((r, j) => (
                          <a
                            key={j}
                            href={searchUrl(r.title, r.provider)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs border border-gray-200 hover:border-blue-300 hover:bg-blue-50 transition-colors"
                            title={`Cerca: ${r.title} · ${r.provider} · ${r.cost === 'gratuito' ? 'gratuito' : 'a pagamento'}`}
                          >
                            <SearchIcon size={12} className="text-gray-400 shrink-0" />
                            <span className="font-medium text-gray-700 truncate min-w-0 flex-1">{r.title}</span>
                            <span className="text-gray-400 shrink-0 hidden sm:inline">{r.provider}</span>
                            {r.cost === 'gratuito'
                              ? <GiftIcon size={14} className="text-emerald-600 shrink-0" />
                              : <EuroIcon size={14} className="text-amber-600 shrink-0" />}
                          </a>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Keyword ATS */}
          {atsItems.length > 0 && (
            <div className="bg-white rounded-xl border border-amber-200 p-5">
              <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 mb-2">
                <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-amber-600">
                  <TagIcon size={15} /> Keyword ATS da aggiungere al CV
                </h2>
                <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
                  <span className="flex items-center gap-1"><CheckCircleIcon size={14} className="text-emerald-600 shrink-0" /> Aggiunta</span>
                  <span className="flex items-center gap-1"><CircleSlashIcon size={14} className="text-slate-500 shrink-0" /> Ce l'ho già</span>
                  <span className="flex items-center gap-1"><GraduationCapIcon size={14} className="text-indigo-600 shrink-0" /> Da acquisire</span>
                </div>
              </div>
              <p className="text-xs text-gray-400 mb-4">
                Termini che i filtri ATS cercano per i tuoi ruoli target. Tocca un'icona per classificare ogni keyword — al ricalcolo non te la riproporrà.
              </p>

              {atsTodo.length === 0 ? (
                <p className="text-sm text-gray-400">Tutte gestite 🎉</p>
              ) : (
                <div className="space-y-3">
                  {atsTodo.map((k) => (
                    <div key={k.id} className="p-3 rounded-lg border border-gray-200">
                      <div className="flex items-center justify-between gap-2">
                        <span className="inline-block px-2.5 py-1 bg-amber-50 text-amber-700 text-xs font-semibold rounded-md shrink-0">
                          {k.keyword}
                        </span>
                        <div className="flex items-center gap-1 shrink-0">
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'added' })}
                          title="Aggiunta — l'ho scritta nel CV"
                          className="p-1.5 text-gray-400 hover:text-emerald-600 transition-colors"
                        >
                          <CheckCircleIcon size={16} />
                        </button>
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'ignored' })}
                          title="Ce l'ho già / falso positivo"
                          className="p-1.5 text-gray-400 hover:text-slate-600 transition-colors"
                        >
                          <CircleSlashIcon size={16} />
                        </button>
                        <button
                          onClick={() => setAtsStatus.mutate({ id: k.id, status: 'gap' })}
                          title="Da acquisire — competenza da imparare"
                          className="p-1.5 text-gray-400 hover:text-indigo-600 transition-colors"
                        >
                          <GraduationCapIcon size={16} />
                        </button>
                        </div>
                      </div>
                      <p className="text-xs text-gray-500 mt-2 leading-relaxed break-words">{k.reason}</p>
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
                          <span className="text-gray-600 break-words flex-1 min-w-0">{k.keyword}</span>
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

        </div>
      )}
    </div>
  )
}
