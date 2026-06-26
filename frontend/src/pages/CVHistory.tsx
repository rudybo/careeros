import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { fetchCVList, deleteCV, startAnalysis } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { ArrowLeftIcon, FileTextIcon, Trash2Icon, RefreshCwIcon, ChevronRightIcon } from 'lucide-react'

export default function CVHistory() {
  const qc = useQueryClient()
  const { data: cvs = [], isLoading } = useQuery({ queryKey: ['cvs'], queryFn: fetchCVList })

  const remove = useMutation({
    mutationFn: (cvId: number) => deleteCV(cvId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cvs'] })
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  const reanalyze = useMutation({
    mutationFn: (cvId: number) => startAnalysis(cvId),
    onSuccess: (_d, cvId) => qc.invalidateQueries({ queryKey: ['analyses', cvId] }),
  })

  // Discendente: il più recente in alto
  const sorted = [...cvs].sort((a, b) => b.id - a.id)
  const latestId = sorted[0]?.id

  return (
    <div className="p-4 pb-24 md:px-8 md:pt-8 max-w-3xl">
      <Link to="/cv" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-800 mb-6">
        <ArrowLeftIcon size={14} /> Curriculum
      </Link>

      <h1 className="text-2xl font-bold text-gray-900 mb-1">Storico caricamenti</h1>
      <p className="text-gray-500 text-sm mb-6">Le versioni precedenti del tuo CV. La più recente è quella attiva.</p>

      <div className="bg-white rounded-xl border border-gray-200">
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Caricamento...</div>
        ) : sorted.length === 0 ? (
          <div className="p-12 text-center">
            <FileTextIcon size={36} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">Nessun CV caricato.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {sorted.map(cv => (
              <li key={cv.id} className="flex items-center justify-between px-5 py-4 hover:bg-gray-50">
                <Link to={`/cv/${cv.id}`} className="flex items-center gap-3 flex-1 min-w-0">
                  <FileTextIcon size={18} className="text-gray-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate">
                      {cv.filename}
                      {cv.id === latestId && <span className="ml-2 text-[10px] px-1.5 py-0.5 bg-green-100 text-green-700 rounded-full font-medium align-middle">attivo</span>}
                    </div>
                    <div className="text-xs text-gray-400">
                      {new Date(cv.created_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-2 ml-4 shrink-0">
                  <StatusBadge status={cv.status} />
                  {cv.id === latestId && cv.status === 'parsed' && (
                    <button
                      onClick={() => reanalyze.mutate(cv.id)}
                      disabled={reanalyze.isPending}
                      className="p-1.5 text-gray-400 hover:text-violet-600 transition-colors disabled:opacity-50"
                      title="Rianalizza (Minerva può dare una nuova lettura)"
                    >
                      <RefreshCwIcon size={15} />
                    </button>
                  )}
                  <Link to={`/cv/${cv.id}`} className="p-1 text-gray-300 hover:text-gray-500" title="Apri">
                    <ChevronRightIcon size={16} />
                  </Link>
                  <button
                    onClick={() => {
                      if (window.confirm(`Eliminare "${cv.filename}"?\n\nAttenzione: tutte le candidature collegate a questo CV verranno eliminate.`)) {
                        remove.mutate(cv.id)
                      }
                    }}
                    disabled={remove.isPending}
                    className="p-1 text-gray-300 hover:text-red-500 transition-colors disabled:opacity-50"
                    title="Elimina CV"
                  >
                    <Trash2Icon size={15} />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
