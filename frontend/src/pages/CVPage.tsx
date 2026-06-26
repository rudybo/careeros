import { useRef, useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { uploadCV, parseCV, fetchCVList, fetchCV, fetchAnalysisList, startAnalysis } from '../api/client'
import AgentBubble from '../components/AgentBubble'
import {
  UploadCloudIcon, ListChecksIcon, HistoryIcon, FileTextIcon,
  SparklesIcon, TrendingUpIcon, Loader2Icon,
} from 'lucide-react'

const demandColor: Record<string, string> = {
  alto: 'bg-green-100 text-green-700',
  medio: 'bg-yellow-100 text-yellow-700',
  basso: 'bg-red-100 text-red-600',
}

export default function CVPage() {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const retryRef = useRef<{ cvId: number; attempts: number } | null>(null)

  const { data: cvs = [] } = useQuery({
    queryKey: ['cvs'],
    queryFn: fetchCVList,
    refetchInterval: (q) => (q.state.data ?? []).some(c => c.status === 'parsing') ? 2000 : false,
  })

  // CV corrente = l'ultimo caricato (id più alto)
  const current = [...cvs].sort((a, b) => b.id - a.id)[0]

  const { data: cv } = useQuery({
    queryKey: ['cv', current?.id],
    queryFn: () => fetchCV(current!.id),
    enabled: !!current,
    refetchInterval: (q) => q.state.data?.status === 'parsing' ? 2000 : false,
  })

  const { data: analyses = [] } = useQuery({
    queryKey: ['analyses', current?.id],
    queryFn: () => fetchAnalysisList(current!.id),
    enabled: cv?.status === 'parsed',
    refetchInterval: (q) => (q.state.data ?? []).some(a => a.status === 'analyzing') ? 2000 : false,
  })

  const sortedAnalyses = [...analyses].sort((a, b) => b.id - a.id)
  const latest = sortedAnalyses[0]
  const latestCompleted = sortedAnalyses.find(x => x.status === 'completed')

  const upload = useMutation({
    mutationFn: async (file: File) => {
      setUploadError(null)
      const { data } = await uploadCV(file)
      await parseCV(data.id)   // il backend, finito il parsing, analizza in automatico
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvs'] }),
    onError: (e: any) => setUploadError(e?.response?.data?.detail ?? 'Errore durante il caricamento'),
  })

  // Auto-analisi/retry: se il CV è parsato ma NON c'è ancora un'analisi completata
  // (mai fatta, o la prima è andata in errore), (ri)avvia da sola. Se invece esiste
  // già un'analisi buona, un re-run fallito NON deve insistere.
  useEffect(() => {
    if (!cv || cv.status !== 'parsed') return
    const needs = !latestCompleted && (!latest || latest.status === 'error')
    if (!needs) return
    const prev = retryRef.current?.cvId === cv.id ? retryRef.current!.attempts : 0
    if (prev >= 3) return
    const delay = latest?.status === 'error' ? 8000 : 6000
    const t = setTimeout(() => {
      retryRef.current = { cvId: cv.id, attempts: prev + 1 }
      startAnalysis(cv.id).then(() => qc.invalidateQueries({ queryKey: ['analyses', cv.id] }))
    }, delay)
    return () => clearTimeout(t)
  }, [cv?.id, cv?.status, latest?.id, latest?.status, latestCompleted?.id, qc])

  const handleFile = (file: File) => {
    if (!file.name.match(/\.(pdf|docx)$/i)) {
      setUploadError('Formato non supportato. Carica un file PDF o DOCX.')
      return
    }
    upload.mutate(file)
  }

  const NuovoCurriculumButton = (
    <>
      <input ref={inputRef} type="file" accept=".pdf,.docx" className="hidden"
        onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
      <button onClick={() => inputRef.current?.click()} disabled={upload.isPending}
        className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60">
        <UploadCloudIcon size={15} />
        {upload.isPending ? 'Caricamento...' : 'Nuovo curriculum'}
      </button>
    </>
  )

  // ── Stato vuoto: nessun CV ───────────────────────────────────────────────────
  if (!current) {
    return (
      <div className="p-4 pb-24 md:p-8 max-w-3xl">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Curriculum</h1>
        <p className="text-gray-500 mb-8 text-sm">Carica il tuo CV: Minerva lo analizza e ti dice cosa migliorare.</p>
        <div
          onClick={() => inputRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors border-gray-300 hover:border-blue-400 hover:bg-gray-50 ${upload.isPending ? 'opacity-60 pointer-events-none' : ''}`}
        >
          <input ref={inputRef} type="file" accept=".pdf,.docx" className="hidden"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
          <UploadCloudIcon size={40} className="mx-auto text-gray-400 mb-3" />
          {upload.isPending
            ? <p className="text-sm text-blue-600 font-medium">Caricamento e analisi in corso...</p>
            : <>
                <p className="text-sm font-medium text-gray-700">Carica il tuo primo curriculum</p>
                <p className="text-xs text-gray-400 mt-1">PDF o DOCX · max 10MB</p>
              </>}
        </div>
        {uploadError && <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{uploadError}</div>}
      </div>
    )
  }

  const parsed = cv?.parsed_data
  const a = latestCompleted?.analysis          // mostra SEMPRE l'ultima analisi buona
  const hasGood = !!a
  const analyzing = latest?.status === 'analyzing' || (cv?.status === 'parsed' && !latest)
  const errored = latest?.status === 'error'
  // Lavoro "bloccante" (niente da mostrare) solo se non c'è ancora un'analisi buona
  const working = cv?.status === 'parsing' || ((analyzing || errored) && !hasGood)

  const minervaMsg = cv?.status === 'parsing'
    ? 'Sto leggendo il tuo CV...'
    : errored && !hasGood
    ? 'Non riesco a raggiungere il server per completare l\'analisi. Riprovo tra qualche secondo...'
    : analyzing && !hasGood
    ? 'Sto analizzando il tuo CV e costruendo la tua strategia di carriera...'
    : 'Ecco la mia analisi del tuo profilo. Nelle Attività trovi cosa migliorare.'

  return (
    <div className="p-4 pb-24 md:px-8 md:pt-8 max-w-3xl">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between mb-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-gray-900 truncate">
            {parsed?.full_name ?? cv?.filename ?? 'Curriculum'}
          </h1>
          {parsed?.email && <p className="text-gray-500 text-sm mt-0.5 truncate">{parsed.email}{parsed.phone ? ` · ${parsed.phone}` : ''}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          {NuovoCurriculumButton}
          <Link to="/attivita"
            className="inline-flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-sm font-medium rounded-lg hover:bg-violet-700">
            <ListChecksIcon size={15} /> Attività
          </Link>
          <Link to="/cv/storico"
            className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200">
            <HistoryIcon size={15} /> Storico
          </Link>
        </div>
      </div>

      {/* Riferimento del CV: file + data di caricamento */}
      {cv && (
        <div className="flex items-center gap-2 mb-5 px-3 py-2 bg-white border border-gray-200 rounded-lg text-xs text-gray-500">
          <FileTextIcon size={14} className="text-gray-400 shrink-0" />
          <span className="font-medium text-gray-700 truncate">{cv.filename}</span>
          <span className="shrink-0 ml-auto">caricato il {new Date(cv.created_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
        </div>
      )}

      {uploadError && <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{uploadError}</div>}

      <AgentBubble name="Minerva" active={working} message={minervaMsg} />

      {/* Stato lavoro in corso (solo se non c'è ancora un'analisi buona da mostrare) */}
      {working && (
        <div className="mt-6 flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl text-sm text-blue-700">
          <Loader2Icon size={16} className="animate-spin shrink-0" />
          {cv?.status === 'parsing'
            ? 'Lettura del CV in corso...'
            : errored
            ? 'Server occupato, riprovo a completare l\'analisi...'
            : 'Analisi di carriera in corso (1-3 minuti). La pagina si aggiorna da sola.'}
        </div>
      )}

      {/* Aggiornamento in corso/non riuscito, ma c'è già un'analisi buona da mostrare */}
      {hasGood && (analyzing || errored) && (
        <div className="mt-4 text-xs text-gray-400">
          {analyzing
            ? 'Aggiornamento dell\'analisi in corso…'
            : 'Ultimo aggiornamento non riuscito (server occupato). Mostro l\'analisi precedente.'}
        </div>
      )}

      {/* Analisi (ultima completata) */}
      {a && (
        <div className="mt-6 space-y-6">
          {/* Executive summary */}
          {a.executive_summary && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 flex items-center gap-2 mb-2">
                <SparklesIcon size={14} className="text-violet-500" /> Analisi carriera
              </h2>
              <p className="text-gray-700 text-sm leading-relaxed">{a.executive_summary}</p>
            </div>
          )}

          {/* Ruoli target */}
          {a.target_roles?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 flex items-center gap-2 mb-4">
                <TrendingUpIcon size={14} /> Ruoli target
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
          )}

          {/* Dati del CV */}
          {parsed?.skills?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="font-semibold text-sm uppercase tracking-wider text-gray-400 mb-3">Skills</h2>
              <div className="flex flex-wrap gap-2">
                {parsed.skills.map(s => (
                  <span key={s} className="px-2.5 py-1 bg-blue-50 text-blue-700 text-xs font-medium rounded-full">{s}</span>
                ))}
              </div>
            </div>
          )}

          {parsed?.work_experience && parsed.work_experience.length > 0 && (
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

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            {parsed?.education && parsed.education.length > 0 && (
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
            {parsed?.languages && parsed.languages.length > 0 && (
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
