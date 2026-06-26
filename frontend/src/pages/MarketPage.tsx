import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  fetchOpportunities, fetchPreferences, fetchSearchStatus,
  savePreferences, startMarketSearch, updateOpportunityStatus, fetchCVList,
  createOpportunityDraft,
} from '../api/client'
import { SearchIcon, BookmarkIcon, XCircleIcon, ExternalLinkIcon, Loader2Icon, SlidersIcon, ChevronDownIcon, ChevronUpIcon, MailIcon, CheckCircleIcon, SendIcon } from 'lucide-react'
import type { UserPreferences } from '../types'
import AgentBubble from '../components/AgentBubble'

const MIN_MATCH = 60  // soglia minima di match% per mostrare un'offerta nella vista principale
const WORK_MODE_LABELS: Record<string, string> = { remote: 'Remoto', hybrid: 'Ibrido', onsite: 'In sede' }
const SCORE_COLOR = (s: number) => s >= 70 ? 'text-green-600 bg-green-50' : s >= 45 ? 'text-yellow-600 bg-yellow-50' : 'text-red-500 bg-red-50'

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null) return null
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-bold ${SCORE_COLOR(score)}`}>
      {score}%
    </span>
  )
}

function PreferencesPanel({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient()
  const { data: prefs } = useQuery({ queryKey: ['preferences'], queryFn: fetchPreferences })
  const [form, setForm] = useState<Partial<UserPreferences>>(prefs ?? {})

  const save = useMutation({
    mutationFn: () => savePreferences(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['preferences'] }); onClose() },
  })

  const f = (field: keyof UserPreferences) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const val = e.target.value === '' ? null : e.target.value
    setForm(prev => ({ ...prev, [field]: val }))
  }

  const targetRolesValue = Array.isArray(form.target_roles) ? form.target_roles.join(', ') : (form.target_roles ?? '')
  const onTargetRolesChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    const roles = val ? val.split(',').map(r => r.trim()).filter(Boolean) : null
    setForm(prev => ({ ...prev, target_roles: roles }))
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
      <h2 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
        <SlidersIcon size={16} /> Preferenze di ricerca <span className="text-xs font-normal text-gray-400">(tutti opzionali)</span>
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="sm:col-span-2">
          <label className="text-xs text-gray-500 mb-1 block">Ruoli target <span className="text-gray-400">(separati da virgola)</span></label>
          <input type="text"
            placeholder="es. IT Manager, Data Analyst, BI Manager, Business Central Consultant"
            defaultValue={targetRolesValue}
            onChange={onTargetRolesChange}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">RAL minima (€)</label>
          <input type="number" placeholder="es. 35000" defaultValue={prefs?.ral_min ?? ''}
            onChange={f('ral_min')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">RAL massima (€)</label>
          <input type="number" placeholder="es. 55000" defaultValue={prefs?.ral_max ?? ''}
            onChange={f('ral_max')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Città di riferimento</label>
          <input type="text" placeholder="es. Torino" defaultValue={prefs?.city ?? ''}
            onChange={f('city')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Raggio (km)</label>
          <input type="number" placeholder="es. 50" defaultValue={prefs?.radius_km ?? ''}
            onChange={f('radius_km')} className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400" />
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Modalità lavoro</label>
          <select defaultValue={prefs?.work_mode ?? ''} onChange={f('work_mode')}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">Qualsiasi</option>
            <option value="remote">Solo remoto</option>
            <option value="hybrid">Ibrido</option>
            <option value="onsite">In sede</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Tipo contratto</label>
          <select defaultValue={prefs?.contract_type ?? ''} onChange={f('contract_type')}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">Qualsiasi</option>
            <option value="indeterminato">Tempo indeterminato</option>
            <option value="determinato">Tempo determinato</option>
            <option value="piva">Partita IVA</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Dimensione azienda</label>
          <select defaultValue={prefs?.company_size ?? ''} onChange={f('company_size')}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">Qualsiasi</option>
            <option value="startup">Startup</option>
            <option value="sme">PMI</option>
            <option value="enterprise">Grande azienda</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-500 mb-1 block">Lingua richiesta</label>
          <select defaultValue={prefs?.language ?? ''} onChange={f('language')}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-400">
            <option value="">Qualsiasi</option>
            <option value="italian">Solo italiano</option>
            <option value="english">Inglese richiesto</option>
            <option value="bilingual">Bilingue</option>
          </select>
        </div>
      </div>
      <div className="flex justify-end gap-2 mt-4">
        <button onClick={onClose} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-800">Annulla</button>
        <button onClick={() => save.mutate()} disabled={save.isPending}
          className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {save.isPending ? 'Salvataggio...' : 'Salva preferenze'}
        </button>
      </div>
    </div>
  )
}

export default function MarketPage() {
  const qc = useQueryClient()
  const [showPrefs, setShowPrefs] = useState(false)
  const [activeFilter, setActiveFilter] = useState<string | undefined>(undefined)
  const [sourceFilter, setSourceFilter] = useState<string | undefined>(undefined)

  const { data: cvs = [] } = useQuery({ queryKey: ['cvs'], queryFn: fetchCVList })
  const parsedCV = cvs.find(c => c.status === 'parsed')

  const { data: searchStatus } = useQuery({
    queryKey: ['searchStatus'],
    queryFn: fetchSearchStatus,
    refetchInterval: (q) => q.state.data?.running ? 3000 : false,
  })

  // Con un filtro fonte attivo carichiamo di più (100) per non restare al Top 10
  const wantAll = (!!activeFilter && activeFilter !== 'new') || !!sourceFilter
  const { data: opportunities = [], isLoading } = useQuery({
    queryKey: ['opportunities', activeFilter, sourceFilter],
    queryFn: () => fetchOpportunities(activeFilter, wantAll ? 100 : 10),
    refetchInterval: (q) => {
      const opps = q.state.data ?? []
      const hasGenerating = opps.some((o: any) => o.draft_status === 'generating')
      if (searchStatus?.running || hasGenerating) return 4000
      return 8000  // refresh leggero: riflette le azioni fatte da Telegram
    },
  })

  const search = useMutation({
    mutationFn: () => startMarketSearch(parsedCV!.id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['searchStatus'] }),
  })

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => updateOpportunityStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['opportunities'] }),
  })

  const createDraft = useMutation({
    mutationFn: (oppId: number) => createOpportunityDraft(oppId, parsedCV!.id),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ['opportunities'] }), 8000)
    },
  })

  const isRunning = searchStatus?.running ?? false

  const irisMessage = !parsedCV
    ? 'Per cercare ho bisogno di un CV analizzato: caricane e analizzane uno prima.'
    : isRunning
    ? 'Sto cercando nuove occasioni lavorative per te su Adzuna e Jooble...'
    : searchStatus?.last_error
    ? `Ho avuto un intoppo nell'ultima ricerca: ${searchStatus.last_error}`
    : searchStatus?.last_count === 0
    ? 'Stavolta non ho trovato nuove offerte. Prova a ritoccare le preferenze e rilanciami.'
    : (searchStatus?.last_count ?? 0) > 0
    ? `Nell'ultima ricerca ho trovato ${searchStatus!.last_count} nuove offerte per te.`
    : 'Sono Iris. Cerco e seleziono le offerte più adatte al tuo profilo, ogni giorno alle 08:00 e alle 19:00.'
  const filters = [
    { value: undefined, label: 'Tutte' },
    { value: 'new', label: 'Nuove' },
    { value: 'saved', label: 'Salvate' },
    { value: 'applied', label: 'Candidato' },
    { value: 'dismissed', label: 'Scartate' },
  ]
  const sources = [
    { value: undefined, label: 'Tutte le fonti' },
    { value: 'adzuna', label: 'Adzuna' },
    { value: 'jooble', label: 'Jooble' },
  ]
  // Soglia minima di match: sotto il 60% non mostriamo (match basso = difficile assunzione).
  // Vale solo per Tutte/Nuove; le viste manuali (Salvate/Candidato/Scartate) restano integre.
  const scoreGated = !activeFilter || activeFilter === 'new'
  const visibleOpps = (sourceFilter ? opportunities.filter(o => o.source === sourceFilter) : opportunities)
    .filter(o => !scoreGated || (o.match_score ?? 0) >= MIN_MATCH)

  return (
    <div className="p-4 pb-24 md:p-8 max-w-4xl">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Market Scout</h1>
          <p className="text-gray-500 mt-1 text-sm">Offerte di lavoro selezionate e rankate in base al tuo CV — ricerca automatica 08:00 e 19:00</p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button onClick={() => setShowPrefs(p => !p)}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-sm border border-gray-300 rounded-lg hover:border-blue-400 hover:text-blue-600 transition-colors">
            <SlidersIcon size={14} /> Preferenze
            {showPrefs ? <ChevronUpIcon size={13} /> : <ChevronDownIcon size={13} />}
          </button>
          <button
            onClick={() => search.mutate()}
            disabled={isRunning || !parsedCV || search.isPending}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {isRunning
              ? <><Loader2Icon size={14} className="animate-spin" /> Ricerca in corso...</>
              : <><SearchIcon size={14} /> Cerca offerte</>}
          </button>
        </div>
      </div>

      <AgentBubble name="Iris" active={isRunning} message={irisMessage} />

      {showPrefs && <PreferencesPanel onClose={() => setShowPrefs(false)} />}

      {/* Filter tabs — always visible after first search */}
      {searchStatus !== undefined && (
        <div className="mb-4 space-y-2">
          <div className="flex flex-wrap gap-1">
            {filters.map(f => (
              <button key={String(f.value)} onClick={() => setActiveFilter(f.value)}
                className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
                  activeFilter === f.value
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}>
                {f.label}
              </button>
            ))}
            {!sourceFilter && (!activeFilter || activeFilter === 'new') && opportunities.length > 0 && (
              <span className="text-xs text-gray-400 self-center ml-auto hidden sm:block">Top 10 per match score</span>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {sources.map(s => (
              <button key={String(s.value)} onClick={() => setSourceFilter(s.value)}
                className={`px-3 py-1 text-xs font-medium rounded-full border transition-colors ${
                  sourceFilter === s.value
                    ? 'bg-violet-600 text-white border-violet-600'
                    : 'bg-white text-gray-500 border-gray-200 hover:border-violet-300'
                }`}>
                {s.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Opportunities list */}
      {isLoading ? (
        <div className="text-center text-gray-400 py-12 text-sm">Caricamento...</div>
      ) : visibleOpps.length === 0 && !isRunning ? (
        <div className="text-center py-16 text-gray-400">
          <SearchIcon size={40} className="mx-auto mb-3 opacity-30" />
          <p className="text-sm">
            {scoreGated && opportunities.length > 0
              ? `Nessuna offerta sopra il ${MIN_MATCH}% di match.`
              : sourceFilter
              ? `Nessuna offerta da ${sourceFilter} con questo filtro.`
              : 'Nessuna offerta trovata. Avvia una ricerca!'}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {visibleOpps.map(opp => (
            <div key={opp.id} className={`bg-white rounded-xl border p-5 transition-opacity ${
              opp.status === 'dismissed' ? 'opacity-40 border-gray-100' : 'border-gray-200'
            }`}>
              <div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <ScoreBadge score={opp.match_score} />
                    {opp.work_mode && opp.work_mode !== 'unknown' && (
                      <span className="text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded-full font-medium">
                        {WORK_MODE_LABELS[opp.work_mode] ?? opp.work_mode}
                      </span>
                    )}
                    {opp.status === 'saved' && (
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full font-medium">Salvata</span>
                    )}
                    {opp.status === 'applied' && (
                      <span className="text-xs px-2 py-0.5 bg-emerald-50 text-emerald-600 rounded-full font-medium">Candidato</span>
                    )}
                  </div>
                  <h3 className="font-semibold text-gray-900 text-sm leading-snug">{opp.title}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {opp.company && <span className="font-medium">{opp.company}</span>}
                    {opp.company && opp.location && ' · '}
                    {opp.location}
                  </p>
                  {(opp.salary_min || opp.salary_max) && (
                    <p className="text-xs text-gray-400 mt-1">
                      RAL: {opp.salary_min ? `${(opp.salary_min / 1000).toFixed(0)}k` : '?'}
                      {opp.salary_max ? ` – ${(opp.salary_max / 1000).toFixed(0)}k €` : '+ €'}
                    </p>
                  )}
                  {opp.match_reasons && opp.match_reasons.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {opp.match_reasons.map((r, i) => (
                        <li key={i} className="text-xs text-gray-500 flex gap-1.5">
                          <span className="text-blue-400 shrink-0">·</span> {r}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="flex items-center justify-between gap-3 mt-3">
                  <div className="flex items-center gap-1.5">
                    <a href={opp.url} target="_blank" rel="noreferrer"
                      className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors" title="Apri offerta">
                      <ExternalLinkIcon size={15} />
                    </a>
                    {opp.draft_status === 'ready' && opp.gmail_url ? (
                      <a href={opp.gmail_url} target="_blank" rel="noreferrer"
                        className="p-1.5 text-green-500 hover:text-green-700 transition-colors" title="Apri bozza in Gmail">
                        <CheckCircleIcon size={15} />
                      </a>
                    ) : opp.draft_status === 'generating' ? (
                      <span className="p-1.5 text-indigo-400" title="Generazione in corso...">
                        <Loader2Icon size={15} className="animate-spin" />
                      </span>
                    ) : (
                      <button
                        onClick={() => createDraft.mutate(opp.id)}
                        disabled={!parsedCV || createDraft.isPending}
                        className="p-1.5 text-gray-400 hover:text-indigo-600 transition-colors disabled:opacity-30" title="Crea bozza email">
                        <MailIcon size={15} />
                      </button>
                    )}
                    {opp.status !== 'applied' && (
                      <button onClick={() => updateStatus.mutate({ id: opp.id, status: 'applied' })}
                        className="p-1.5 text-gray-400 hover:text-emerald-600 transition-colors" title="Mi sono candidato">
                        <SendIcon size={15} />
                      </button>
                    )}
                    {opp.status !== 'saved' && opp.status !== 'applied' && (
                      <button onClick={() => updateStatus.mutate({ id: opp.id, status: 'saved' })}
                        className="p-1.5 text-gray-400 hover:text-blue-600 transition-colors" title="Salva">
                        <BookmarkIcon size={15} />
                      </button>
                    )}
                    {opp.status !== 'dismissed' && (
                      <button onClick={() => updateStatus.mutate({ id: opp.id, status: 'dismissed' })}
                        className="p-1.5 text-gray-400 hover:text-red-500 transition-colors" title="Scarta">
                        <XCircleIcon size={15} />
                      </button>
                    )}
                  </div>
                  <span className="text-xs text-gray-300 uppercase tracking-wide shrink-0">{opp.source}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
