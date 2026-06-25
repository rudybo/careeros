import { useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { uploadCV, parseCV, fetchCVList, deleteCV } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { UploadCloudIcon, FileTextIcon, ChevronRightIcon, Trash2Icon } from 'lucide-react'

export default function CVPage() {
  const qc = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)

  const { data: cvs = [], isLoading } = useQuery({
    queryKey: ['cvs'],
    queryFn: fetchCVList,
    refetchInterval: (query) => {
      const data = query.state.data ?? []
      return data.some(c => c.status === 'parsing') ? 2000 : false
    },
  })

  const remove = useMutation({
    mutationFn: (cvId: number) => deleteCV(cvId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['cvs'] })
      qc.invalidateQueries({ queryKey: ['applications'] })
    },
  })

  const upload = useMutation({
    mutationFn: async (file: File) => {
      setUploadError(null)
      const { data } = await uploadCV(file)
      await parseCV(data.id)
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvs'] }),
    onError: (e: any) => setUploadError(e?.response?.data?.detail ?? 'Errore durante il caricamento'),
  })

  const handleFile = (file: File) => {
    if (!file.name.match(/\.(pdf|docx)$/i)) {
      setUploadError('Formato non supportato. Carica un file PDF o DOCX.')
      return
    }
    upload.mutate(file)
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Curriculum</h1>
        <p className="text-gray-500 mt-1">Carica il tuo CV e avvia il parsing automatico</p>
      </div>

      {/* Upload area */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors mb-8 ${
          dragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-blue-400 hover:bg-gray-50'
        } ${upload.isPending ? 'opacity-60 pointer-events-none' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        <UploadCloudIcon size={40} className="mx-auto text-gray-400 mb-3" />
        {upload.isPending ? (
          <p className="text-sm text-blue-600 font-medium">Caricamento e parsing in corso...</p>
        ) : (
          <>
            <p className="text-sm font-medium text-gray-700">Trascina qui il tuo CV o clicca per sceglierlo</p>
            <p className="text-xs text-gray-400 mt-1">PDF o DOCX · max 10MB</p>
          </>
        )}
      </div>

      {uploadError && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {uploadError}
        </div>
      )}

      {/* CV list */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">CV caricati</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Caricamento...</div>
        ) : cvs.length === 0 ? (
          <div className="p-12 text-center">
            <FileTextIcon size={36} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">Nessun CV ancora. Caricane uno!</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {cvs.map(cv => (
              <li key={cv.id} className="flex items-center justify-between px-5 py-4 hover:bg-gray-50">
                <Link to={`/cv/${cv.id}`} className="flex items-center gap-3 flex-1 min-w-0">
                  <FileTextIcon size={18} className="text-gray-400 shrink-0" />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-gray-800 truncate">{cv.filename}</div>
                    <div className="text-xs text-gray-400">
                      {new Date(cv.created_at).toLocaleDateString('it-IT', { day: '2-digit', month: 'short', year: 'numeric' })}
                    </div>
                  </div>
                </Link>
                <div className="flex items-center gap-3 ml-4 shrink-0">
                  <StatusBadge status={cv.status} />
                  <Link to={`/cv/${cv.id}`}>
                    <ChevronRightIcon size={16} className="text-gray-300" />
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
