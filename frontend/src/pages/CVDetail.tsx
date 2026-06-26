import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCV, startAnalysis, fetchAnalysisList } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AgentBubble from '../components/AgentBubble'
import { ArrowLeftIcon, SparklesIcon, BriefcaseIcon, TrendingUpIcon, ListChecksIcon } from 'lucide-react'

const demandColor: Record<string, string> = {
  alto: 'bg-green-100 text-green-700',
  medio: 'bg-yellow-100 text-yellow-700',
  basso: 'bg-red-100 text-red-600',
}

export default function CVDetail() {
  const { id } = useParams<{ id: string }>()
  const cvId = Number(id)
  const navigate = useNavigate()
  const qc = useQueryClient()

  const { data: cv, isLoading } = useQuery({
    queryKey: ['cv', cvId],
    queryFn: () => fetchCV(cvId),
    refetchInterval: (q) => q.state.data?.status === 'parsing' ? 2000 : false,
  })

  const { data: analyses = [] } = useQuery({
    queryKey: ['analyses', cvId],
    queryFn: () => fetchAnalysisList(cvId),
    enabled: cv?.status === 'parsed',
    refetchInterval: (q) => (q.state.data ?? []).some(a => a.status === 'analyzing') ? 2000 : false,
  })

  const analyze = useMutation({
    mutationFn: () => startAnalysis(cvId),
    onSuccess: async (res) => {
      await qc.invalidateQueries({ queryKey: ['analyses', cvId] })
      navigate(`/cv/${cvId}/analysis/${res.data.analysis_id}`)
    },
  })

  // Ultima analisi (per id decrescente) e ultima completata
  const sorted = [...analyses].sort((a, b) => b.id - a.id)
  const latest = sorted[0]
  const latestCompleted = sorted.find(a => a.status === 'completed')
  const hasAnalysis = sorted.length > 0

  const handleAnalyze = () => {
    if (hasAnalysis && !window.confirm(
      'Generare una NUOVA analisi?\n\nL\'LLM produrrà un risultato diverso da quello attuale. L\'analisi precedente resterà nello storico.'
    )) return
    analyze.mutate()
  }

  if (isLoading) return <div className="p-8 text-gray-400">Caricamento...</div>
  if (!cv) return <div className="p-8 text-red-500">CV non trovato</div>

  const parsed = cv.parsed_data

  return (
    <div className="p-4 pb-40 md:px-8 md:pt-8 max-w-4xl">
      <Link to="/cv" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Tutti i CV
      </Link>

      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {parsed?.full_name ?? cv.filename}
          </h1>
          {parsed?.email && <p className="text-gray-500 text-sm mt-0.5">{parsed.email} · {parsed.phone}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <StatusBadge status={cv.status} />
          {cv.status === 'parsed' && (
            <div className="flex flex-wrap gap-2">
              <button
                onClick={handleAnalyze}
                disabled={analyze.isPending}
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-60 ${
                  hasAnalysis
                    ? 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                <SparklesIcon size={15} />
                {analyze.isPending ? 'Avvio...' : hasAnalysis ? 'Ricalcola' : 'Analizza carriera'}
              </button>
              <Link
                to="/applications"
                className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200"
              >
                <BriefcaseIcon size={15} />
                Nuova candidatura
              </Link>
            </div>
          )}
        </div>
      </div>

      {/* Minerva — visibile quando c'è un'analisi in corso o completata */}
      {(latest?.status === 'analyzing' || latestCompleted?.analysis) && (
        <AgentBubble
          name="Minerva"
          active={latest?.status === 'analyzing'}
          message={
            latest?.status === 'analyzing'
              ? 'Sto analizzando il tuo CV e costruendo la tua strategia di carriera...'
              : `Elaborazione completata: ${latestCompleted!.analysis.target_roles.length} ruoli target, ${latestCompleted!.analysis.skill_gaps.length} skill da colmare, ${latestCompleted!.analysis.ats_keywords.length} keyword ATS. Vuoi aprire la tua to-do?`
          }
          action={latestCompleted?.analysis ? { label: 'Apri Attività →', onClick: () => navigate('/attivita') } : undefined}
        />
      )}

      {cv.status === 'parsing' && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700">
          Il CV è in fase di parsing... questa pagina si aggiorna automaticamente.
        </div>
      )}

      {parsed && (
        <div className="space-y-6">
          {/* Executive summary dall'ultima analisi completata */}
          {latestCompleted?.analysis?.executive_summary && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between gap-4 mb-2">
                <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 flex items-center gap-2">
                  <SparklesIcon size={14} className="text-violet-500" /> Analisi carriera
                  <span className="text-gray-300">·</span>
                  <span className="text-xs text-gray-400 font-normal normal-case tracking-normal">
                    {new Date(latestCompleted.created_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}
                  </span>
                </h2>
                <Link
                  to="/attivita"
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-violet-600 text-white text-xs font-medium rounded-lg hover:bg-violet-700 shrink-0"
                >
                  <ListChecksIcon size={13} /> Vedi attività
                </Link>
              </div>
              <p className="text-gray-700 text-sm leading-relaxed">{latestCompleted.analysis.executive_summary}</p>
            </div>
          )}

          {/* Ruoli target */}
          {latestCompleted?.analysis?.target_roles?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 flex items-center gap-2 mb-4">
                <TrendingUpIcon size={14} /> Ruoli target
              </h2>
              <div className="space-y-3">
                {latestCompleted.analysis.target_roles.map((role: any, i: number) => (
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
          )}

          {/* Analisi in corso */}
          {latest?.status === 'analyzing' && (
            <Link
              to={`/cv/${cvId}/analysis/${latest.id}`}
              className="block bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-700 hover:bg-blue-100"
            >
              Minerva sta elaborando una nuova analisi... clicca per seguirne lo stato.
            </Link>
          )}

          {/* Summary */}
          {parsed.summary && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-gray-900 mb-2 text-sm uppercase tracking-wider text-gray-400">Summary</h2>
              <p className="text-gray-700 text-sm leading-relaxed">{parsed.summary}</p>
            </div>
          )}

          {/* Skills */}
          {parsed.skills?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-3">Skills</h2>
              <div className="flex flex-wrap gap-2">
                {parsed.skills.map(s => (
                  <span key={s} className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">{s}</span>
                ))}
              </div>
            </div>
          )}

          {/* Experience */}
          {parsed.work_experience?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-4">Esperienza</h2>
              <div className="space-y-4">
                {parsed.work_experience.map((exp, i) => (
                  <div key={i} className="flex gap-4">
                    <div className="w-1 bg-blue-200 rounded-full shrink-0 mt-1" />
                    <div>
                      <div className="font-medium text-gray-900 text-sm">{exp.role ?? '—'}</div>
                      <div className="text-sm text-gray-500">{exp.company} · {exp.start_date} – {exp.end_date ?? 'presente'}</div>
                      {exp.description && <p className="text-xs text-gray-500 mt-1 leading-relaxed">{exp.description}</p>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Education + Languages */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {parsed.education?.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-3">Formazione</h2>
                {parsed.education.map((edu, i) => (
                  <div key={i} className="text-sm">
                    <div className="font-medium text-gray-900">{edu.degree} {edu.field ? `in ${edu.field}` : ''}</div>
                    <div className="text-gray-500">{edu.institution} · {edu.year}</div>
                  </div>
                ))}
              </div>
            )}
            {parsed.languages?.length > 0 && (
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-3">Lingue</h2>
                <div className="flex flex-wrap gap-2">
                  {parsed.languages.map(l => (
                    <span key={l} className="px-2.5 py-1 bg-purple-50 text-purple-700 text-xs font-medium rounded-full">{l}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

        </div>
      )}
    </div>
  )
}
