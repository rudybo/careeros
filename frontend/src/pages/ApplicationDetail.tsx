import { useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { fetchApplication, updateApplicationStatus, startCoverLetter, startTailoredDraft, checkSent, updateApplicationMeta, documentUrl } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import AgentBubble from '../components/AgentBubble'
import {
  ArrowLeftIcon, CheckCircleIcon, XCircleIcon, AlertTriangleIcon,
  FileTextIcon, MailIcon, SparklesIcon, CopyIcon, CheckIcon, Loader2Icon, ExternalLinkIcon, SendIcon,
} from 'lucide-react'
import type { JobApplication } from '../types'

const STATUS_FLOW: Array<{ value: JobApplication['status']; label: string }> = [
  { value: 'applied',   label: 'Inviato' },
  { value: 'interview', label: 'Colloquio' },
  { value: 'offer',     label: 'Offerta' },
  { value: 'rejected',  label: 'Rifiutato' },
]

const STATUS_LABELS: Record<string, string> = {
  draft: 'Bozza', ready: 'Pronto', applied: 'Inviato',
  interview: 'Colloquio', offer: 'Offerta', rejected: 'Rifiutato',
}

function MatchBar({ score }: { score: number }) {
  const color = score >= 70 ? 'bg-green-500' : score >= 45 ? 'bg-yellow-400' : 'bg-red-400'
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-lg font-bold text-gray-900 w-12 text-right">{score}%</span>
    </div>
  )
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }
  return (
    <button
      onClick={handleCopy}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border border-gray-300 bg-white text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors"
    >
      {copied ? <CheckIcon size={13} className="text-green-500" /> : <CopyIcon size={13} />}
      {copied ? 'Copiato!' : 'Copia lettera'}
    </button>
  )
}

export default function ApplicationDetail() {
  const { id } = useParams<{ id: string }>()
  const appId = Number(id)
  const qc = useQueryClient()
  const [draftError, setDraftError] = useState<string | null>(null)

  const { data: app } = useQuery({
    queryKey: ['application', appId],
    queryFn: () => fetchApplication(appId),
    refetchInterval: (q) => {
      const d = q.state.data
      if (!d) return false
      if (d.status === 'analyzing') return 2000
      if (d.cover_letter_status === 'generating') return 2000
      if (d.draft_status === 'generating') return 2000
      return false
    },
  })

  const updateStatus = useMutation({
    mutationFn: (status: string) => updateApplicationStatus(appId, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['application', appId] }),
  })

  const generateLetter = useMutation({
    mutationFn: () => startCoverLetter(appId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['application', appId] }),
  })

  const createDraft = useMutation({
    mutationFn: () => startTailoredDraft(appId),
    onSuccess: () => {
      setDraftError(null)
      qc.invalidateQueries({ queryKey: ['application', appId] })
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      setDraftError((typeof d === 'string' ? d : null) ?? e?.message ?? 'Errore')
    },
  })

  const [sentMsg, setSentMsg] = useState<string | null>(null)
  const checkSentMut = useMutation({
    mutationFn: () => checkSent(appId),
    onSuccess: (r) => {
      setSentMsg(r.sent.length > 0 ? 'Invio rilevato ✓' : 'Non risulta ancora inviata')
      qc.invalidateQueries({ queryKey: ['application', appId] })
    },
    onError: () => setSentMsg('Controllo non riuscito'),
  })

  const saveMeta = useMutation({
    mutationFn: (v: { advertiser_type: 'recruiter' | 'direct' | null; contact_email: string | null }) =>
      updateApplicationMeta(appId, v),
    onSuccess: () => {
      setDraftError(null)
      qc.invalidateQueries({ queryKey: ['application', appId] })
    },
    onError: (e: any) => {
      const d = e?.response?.data?.detail
      setDraftError((typeof d === 'string' ? d : null) ?? e?.message ?? 'Errore')
    },
  })

  if (!app) return <div className="p-8 text-gray-400">Caricamento...</div>

  const opt = app.optimization
  const cl = app.cover_letter
  const clStatus = app.cover_letter_status

  const canGenerateLetter = ['ready', 'applied', 'interview', 'offer'].includes(app.status)

  const bubble = clStatus === 'generating'
    ? { name: 'Clio' as const, active: true, message: 'Sto scrivendo la tua lettera di presentazione su misura per questa offerta...' }
    : app.status === 'analyzing'
    ? { name: 'Vera' as const, active: true, message: 'Sto ottimizzando il tuo CV per questa offerta e calcolo il match ATS...' }
    : { name: 'Vera' as const, active: false, message: 'Sono Vera. Ottimizzo il tuo CV per questa posizione; Clio prepara la cover letter su misura.' }

  return (
    <div className="p-4 md:p-8 max-w-4xl">
      <Link to="/applications" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Tutte le candidature
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{app.role}</h1>
          <p className="text-gray-500 mt-0.5">{app.company}</p>
        </div>
        <StatusBadge status={app.status} />
      </div>

      {/* Cronologia stati */}
      {app.status_history && app.status_history.length > 0 && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-gray-400 -mt-3 mb-6">
          {app.status_history.map((e, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span className="text-gray-300">→</span>}
              <span className="font-medium text-gray-500">{STATUS_LABELS[e.status] ?? e.status}</span>
              <span>{new Date(e.at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
            </span>
          ))}
        </div>
      )}

      <AgentBubble name={bubble.name} active={bubble.active} message={bubble.message} />

      {/* Status flow buttons */}
      {['ready', 'applied', 'interview'].includes(app.status) && (
        <div className="flex gap-2 mb-6">
          {STATUS_FLOW.map(({ value, label }) => (
            <button
              key={value}
              onClick={() => updateStatus.mutate(value)}
              disabled={updateStatus.isPending || app.status === value}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-colors ${
                app.status === value
                  ? 'bg-blue-600 text-white border-blue-600'
                  : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400 hover:text-blue-600'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}


      {opt && (
        <div className="space-y-6">
          {/* Match score */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">Match score</h2>
            <MatchBar score={opt.match_score} />
            <p className="text-xs text-gray-400 mt-2">
              {opt.match_score >= 70 ? 'Ottimo match — il tuo CV è ben allineato a questa posizione.' :
               opt.match_score >= 45 ? 'Match discreto — ci sono margini di miglioramento.' :
               'Match basso — leggi i suggerimenti qui sotto per ottimizzare il CV.'}
            </p>
          </div>

          {/* Keywords */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
                <CheckCircleIcon size={14} className="text-green-500" /> Keyword presenti
              </h2>
              {opt.matched_keywords.length === 0 ? (
                <p className="text-sm text-gray-400">Nessuna keyword trovata</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {opt.matched_keywords.map(k => (
                    <span key={k} className="px-2.5 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full">{k}</span>
                  ))}
                </div>
              )}
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
                <XCircleIcon size={14} className="text-red-400" /> Keyword mancanti
              </h2>
              {opt.missing_keywords.length === 0 ? (
                <p className="text-sm text-gray-400">Nessuna keyword mancante!</p>
              ) : (
                <div className="flex flex-wrap gap-1.5">
                  {opt.missing_keywords.map(k => (
                    <span key={k} className="px-2.5 py-1 bg-red-500 text-white text-xs font-medium rounded-full">{k}</span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ATS warnings */}
          {opt.ats_warnings.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
                <AlertTriangleIcon size={14} className="text-yellow-500" /> Warning ATS
              </h2>
              <ul className="space-y-2">
                {opt.ats_warnings.map((w, i) => (
                  <li key={i} className="flex gap-2 text-sm text-gray-700">
                    <span className="text-yellow-500 shrink-0">⚠</span> {w}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Section suggestions */}
          {opt.section_suggestions.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
                <FileTextIcon size={14} /> Suggerimenti per sezione
              </h2>
              <div className="space-y-3">
                {opt.section_suggestions.map((s, i) => (
                  <div key={i} className="p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-semibold uppercase tracking-wider text-blue-600">{s.section}</span>
                    </div>
                    <p className="text-sm text-red-600 mb-1">⚠ {s.issue}</p>
                    <p className="text-sm text-gray-700">→ {s.suggestion}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Optimized summary */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-400 mb-2">Summary ottimizzato per questa posizione</h2>
            <p className="text-gray-700 text-sm leading-relaxed italic">"{opt.optimized_summary}"</p>
            <p className="text-xs text-gray-400 mt-2">Sostituisci il summary del tuo CV con questo testo prima di candidarti.</p>
          </div>

          {/* Cover letter hints */}
          {opt.cover_letter_hints.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
                <MailIcon size={14} /> Punti chiave per la lettera di presentazione
              </h2>
              <ol className="space-y-2">
                {opt.cover_letter_hints.map((hint, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-700">
                    <span className="w-5 h-5 bg-blue-600 text-white rounded-full flex items-center justify-center text-xs font-bold shrink-0">
                      {i + 1}
                    </span>
                    {hint}
                  </li>
                ))}
              </ol>
            </div>
          )}

          {/* ── Bozza Gmail ── */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400 mb-3">
              <MailIcon size={14} className="text-blue-500" /> Bozza email (CV su misura + lettera)
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
              <select
                aria-label="Tipo inserzionista"
                value={app.advertiser_type ?? ''}
                onChange={e => saveMeta.mutate({ advertiser_type: (e.target.value || null) as any, contact_email: app.contact_email })}
                disabled={saveMeta.isPending}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-60"
              >
                <option value="">Non rilevato</option>
                <option value="recruiter">Recruiter</option>
                <option value="direct">Azienda diretta</option>
              </select>
              <input
                type="email"
                key={app.contact_email ?? ''}
                aria-label="Email destinatario"
                defaultValue={app.contact_email ?? ''}
                onBlur={e => saveMeta.mutate({ advertiser_type: app.advertiser_type, contact_email: e.target.value.trim() || null })}
                placeholder="Email destinatario"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            {draftError && <p className="text-sm text-red-600 mb-3">{draftError}</p>}
            {app.source_url && (
              <a href={app.source_url} target="_blank" rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-blue-600 hover:underline mb-3">
                <ExternalLinkIcon size={12} /> Annuncio originale
              </a>
            )}
            {app.draft_status === 'idle' && (
              <button
                onClick={() => createDraft.mutate()}
                disabled={createDraft.isPending}
                className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
              >
                Crea bozza Gmail
              </button>
            )}
            {app.draft_status === 'generating' && (
              <div className="flex items-center gap-2 rounded-lg bg-blue-50 border border-blue-200 p-3 text-sm text-blue-700">
                <Loader2Icon size={16} className="animate-spin" /> Sto adattando il CV e preparando la bozza...
              </div>
            )}
            {app.draft_status === 'ready' && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-800">
                <div className="flex flex-wrap items-center gap-2">
                  {app.draft_url && (
                    <a href={app.draft_url} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-1 font-medium underline">
                      <ExternalLinkIcon size={14} /> Apri bozza in Gmail
                    </a>
                  )}
                  <span>Controlla e premi Invia</span>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                {!['applied', 'interview', 'offer', 'rejected'].includes(app.status) && (
                  <>
                    <button
                      onClick={() => { setSentMsg(null); checkSentMut.mutate() }}
                      disabled={checkSentMut.isPending}
                      className="inline-flex items-center gap-1 px-3 py-2 border border-gray-300 dark:border-gray-600 text-gray-600 dark:text-gray-300 text-sm font-medium rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-60"
                    >
                      {checkSentMut.isPending && <Loader2Icon size={14} className="animate-spin" />}
                      Controlla invio
                    </button>
                    {sentMsg && <span className="text-xs text-gray-600 dark:text-gray-300">{sentMsg}</span>}
                  </>
                )}
                <button
                  onClick={() => createDraft.mutate()}
                  disabled={createDraft.isPending}
                  title="La bozza precedente resta in Gmail"
                  className="px-4 py-2 bg-amber-500 text-white text-sm font-medium rounded-lg hover:bg-amber-600 disabled:opacity-60"
                >
                  Rigenera bozza Gmail
                </button>
                </div>
              </div>
            )}
            {app.draft_status === 'error' && (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
                <span>Creazione bozza fallita (controlla Gmail/log)</span>
                <button
                  onClick={() => createDraft.mutate()}
                  disabled={createDraft.isPending}
                  className="px-3 py-1 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
                >
                  Riprova
                </button>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-2 mt-3">
              {['applied', 'interview', 'offer', 'rejected'].includes(app.status) ? (
                ['applied', 'interview', 'offer'].includes(app.status) && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-3 py-1 text-xs font-medium text-emerald-700">
                    ✓ Candidato
                    {app.sent_at
                      ? ` · Inviata il ${new Date(app.sent_at).toLocaleDateString('it-IT')}`
                      : app.applied_at && ` · ${new Date(app.applied_at).toLocaleDateString('it-IT')}`}
                  </span>
                )
              ) : (
                <button
                  onClick={() => updateStatus.mutate('applied', {
                    onError: (e: any) => {
                      const d = e?.response?.data?.detail
                      setDraftError((typeof d === 'string' ? d : null) ?? e?.message ?? 'Errore')
                    },
                  })}
                  disabled={updateStatus.isPending}
                  className="inline-flex items-center gap-1.5 px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-60"
                >
                  <SendIcon size={14} /> Mi sono candidato
                </button>
              )}
            </div>
            {(() => {
              const cvDocs =(app.documents ?? []).filter(d => d.kind === 'cv_su_misura')
              const [latest, ...older] = cvDocs
              const fmt = (d: { created_at: string }) => new Date(d.created_at).toLocaleDateString('it-IT')
              const linkCls = 'text-xs font-medium text-blue-600 hover:underline'
              if (!latest) {
                return app.draft_status === 'ready' ? (
                  <p className="mt-3 text-xs text-gray-400">Nessun allegato salvato (bozza creata prima dell'archivio)</p>
                ) : null
              }
              return (
                <div className="mt-3 text-sm">
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">Allegato</span>
                    <FileTextIcon size={14} className="text-red-500 shrink-0" />
                    <span className="min-w-0 break-all text-gray-700">{latest.filename}</span>
                    <span className="text-xs text-gray-400">{Math.round(latest.size / 1024)} KB · {fmt(latest)}</span>
                    <a href={documentUrl(app.id, latest.id)} target="_blank" rel="noreferrer" className={linkCls}>Apri</a>
                    <a href={documentUrl(app.id, latest.id)} download={latest.filename} className={linkCls}>Scarica</a>
                  </div>
                  {older.length > 0 && (
                    <details className="mt-2">
                      <summary className="cursor-pointer text-xs text-gray-500">Versioni precedenti ({older.length})</summary>
                      <ul className="mt-1 space-y-1">
                        {older.map(d => (
                          <li key={d.id} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                            <FileTextIcon size={14} className="text-gray-400 shrink-0" />
                            <span className="min-w-0 break-all text-gray-600">{d.filename}</span>
                            <span className="text-xs text-gray-400">{Math.round(d.size / 1024)} KB · {fmt(d)}</span>
                            <a href={documentUrl(app.id, d.id)} target="_blank" rel="noreferrer" className={linkCls}>Apri</a>
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </div>
              )
            })()}
          </div>

          {/* ── Cover Letter Generator ── */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="flex items-center gap-1.5 text-sm font-semibold uppercase tracking-wider text-gray-400">
                <SparklesIcon size={14} className="text-purple-500" /> Lettera di presentazione
              </h2>
              {cl && <CopyButton text={cl.full_text} />}
            </div>

            {/* State: idle — can generate */}
            {clStatus === 'idle' && canGenerateLetter && (
              <div className="flex flex-col items-start gap-3">
                <p className="text-sm text-gray-500">
                  Genera una lettera di presentazione personalizzata basata sul tuo CV e questa job description.
                </p>
                <button
                  onClick={() => generateLetter.mutate()}
                  disabled={generateLetter.isPending}
                  className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
                >
                  <SparklesIcon size={14} />
                  Genera lettera
                </button>
              </div>
            )}

            {/* State: generating */}
            {clStatus === 'generating' && (
              <div className="flex items-center gap-3 text-sm text-purple-700 bg-purple-50 border border-purple-200 rounded-lg p-4">
                <Loader2Icon size={16} className="animate-spin shrink-0" />
                Sto generando la tua lettera personalizzata... La pagina si aggiorna automaticamente.
              </div>
            )}

            {/* State: ready — show letter */}
            {clStatus === 'ready' && cl && (
              <div className="space-y-3">
                <div className="p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-400 uppercase tracking-wider mb-1 font-medium">Oggetto email</p>
                  <p className="text-sm font-medium text-gray-800">{cl.subject}</p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg border border-gray-100">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{cl.full_text}</p>
                </div>
                <button
                  onClick={() => generateLetter.mutate()}
                  disabled={generateLetter.isPending}
                  className="text-xs text-gray-400 hover:text-purple-600 transition-colors"
                >
                  Rigenera lettera
                </button>
              </div>
            )}

            {/* State: error */}
            {clStatus === 'error' && (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg p-3">
                  <XCircleIcon size={14} /> Generazione fallita. Riprova.
                </div>
                {canGenerateLetter && (
                  <button
                    onClick={() => generateLetter.mutate()}
                    disabled={generateLetter.isPending}
                    className="inline-flex items-center gap-2 px-4 py-2 bg-purple-600 text-white text-sm font-medium rounded-lg hover:bg-purple-700 disabled:opacity-50 transition-colors"
                  >
                    <SparklesIcon size={14} /> Riprova
                  </button>
                )}
              </div>
            )}
          </div>

          {/* Job description (collapsed) */}
          <details className="bg-white rounded-xl border border-gray-200">
            <summary className="px-5 py-4 cursor-pointer text-sm font-medium text-gray-600 hover:text-gray-900">
              Testo annuncio originale
            </summary>
            <div className="px-5 pb-5">
              <p className="text-xs text-gray-500 whitespace-pre-wrap">{app.job_description}</p>
            </div>
          </details>
        </div>
      )}
    </div>
  )
}
