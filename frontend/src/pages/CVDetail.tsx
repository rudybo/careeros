import { useParams, Link, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchCV, startAnalysis, fetchAnalysisList } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { ArrowLeftIcon, SparklesIcon, BriefcaseIcon } from 'lucide-react'

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

  if (isLoading) return <div className="p-8 text-gray-400">Caricamento...</div>
  if (!cv) return <div className="p-8 text-red-500">CV non trovato</div>

  const parsed = cv.parsed_data

  return (
    <div className="p-8 max-w-4xl">
      <Link to="/cv" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Tutti i CV
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {parsed?.full_name ?? cv.filename}
          </h1>
          {parsed?.email && <p className="text-gray-500 text-sm mt-0.5">{parsed.email} · {parsed.phone}</p>}
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={cv.status} />
          {cv.status === 'parsed' && (
            <div className="flex gap-2">
              <button
                onClick={() => analyze.mutate()}
                disabled={analyze.isPending}
                className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
              >
                <SparklesIcon size={15} />
                {analyze.isPending ? 'Avvio...' : 'Analizza carriera'}
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

      {cv.status === 'parsing' && (
        <div className="mb-6 p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700">
          Il CV è in fase di parsing... questa pagina si aggiorna automaticamente.
        </div>
      )}

      {parsed && (
        <div className="space-y-6">
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
          <div className="grid grid-cols-2 gap-6">
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

          {/* Past analyses */}
          {analyses.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-3">Analisi carriera</h2>
              <ul className="space-y-2">
                {analyses.map(a => (
                  <li key={a.id}>
                    <Link
                      to={`/cv/${cvId}/analysis/${a.id}`}
                      className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50"
                    >
                      <span className="text-sm text-gray-700">
                        Analisi #{a.id} · {new Date(a.created_at).toLocaleDateString('it-IT')}
                      </span>
                      <StatusBadge status={a.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
