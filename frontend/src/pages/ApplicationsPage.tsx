import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { fetchApplicationList, fetchCVList, createApplication, startOptimization } from '../api/client'
import StatusBadge from '../components/StatusBadge'
import { PlusIcon, BriefcaseIcon, ChevronRightIcon } from 'lucide-react'

export default function ApplicationsPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ cv_id: '', company: '', role: '', job_description: '' })
  const [formError, setFormError] = useState<string | null>(null)

  const { data: apps = [], isLoading } = useQuery({
    queryKey: ['applications'],
    queryFn: fetchApplicationList,
    refetchInterval: (q) => (q.state.data ?? []).some(a => a.status === 'analyzing') ? 2000 : false,
  })

  const { data: cvs = [] } = useQuery({
    queryKey: ['cvs'],
    queryFn: fetchCVList,
  })

  const parsedCVs = cvs.filter(c => c.status === 'parsed')

  const create = useMutation({
    mutationFn: async () => {
      setFormError(null)
      if (!form.cv_id || !form.company || !form.role || !form.job_description) {
        throw new Error('Compila tutti i campi')
      }
      const app = await createApplication({
        cv_id: Number(form.cv_id),
        company: form.company,
        role: form.role,
        job_description: form.job_description,
      })
      await startOptimization(app.id)
      return app
    },
    onSuccess: (app) => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      setShowForm(false)
      setForm({ cv_id: '', company: '', role: '', job_description: '' })
      navigate(`/applications/${app.id}`)
    },
    onError: (e: any) => setFormError(e?.message ?? e?.response?.data?.detail ?? 'Errore'),
  })

  return (
    <div className="p-4 md:p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Candidature</h1>
          <p className="text-gray-500 mt-1">Ottimizza il CV per ogni posizione</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
        >
          <PlusIcon size={16} /> Nuova candidatura
        </button>
      </div>

      {/* New application form */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
          <h2 className="font-semibold text-gray-900 mb-4">Nuova candidatura</h2>
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">CV da usare</label>
              {parsedCVs.length === 0 ? (
                <p className="text-sm text-red-600">Nessun CV parsato disponibile. <Link to="/cv" className="underline">Carica un CV</Link> prima.</p>
              ) : (
                <select
                  value={form.cv_id}
                  onChange={e => setForm(f => ({ ...f, cv_id: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="">Seleziona CV...</option>
                  {parsedCVs.map(cv => (
                    <option key={cv.id} value={cv.id}>{cv.filename}</option>
                  ))}
                </select>
              )}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Azienda</label>
                <input
                  type="text"
                  value={form.company}
                  onChange={e => setForm(f => ({ ...f, company: e.target.value }))}
                  placeholder="es. Acme S.p.A."
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Ruolo</label>
                <input
                  type="text"
                  value={form.role}
                  onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  placeholder="es. IT Project Manager"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Testo annuncio (job description)</label>
              <textarea
                value={form.job_description}
                onChange={e => setForm(f => ({ ...f, job_description: e.target.value }))}
                placeholder="Incolla qui il testo completo dell'annuncio di lavoro..."
                rows={8}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
              />
            </div>
            {formError && <p className="text-sm text-red-600">{formError}</p>}
            <div className="flex gap-3">
              <button
                onClick={() => create.mutate()}
                disabled={create.isPending}
                className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-60"
              >
                {create.isPending ? 'Avvio analisi...' : 'Crea e analizza'}
              </button>
              <button
                onClick={() => { setShowForm(false); setFormError(null) }}
                className="px-5 py-2 bg-gray-100 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-200"
              >
                Annulla
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Applications list */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="px-5 py-4 border-b border-gray-100">
          <h2 className="font-semibold text-gray-900">Tutte le candidature</h2>
        </div>
        {isLoading ? (
          <div className="p-8 text-center text-gray-400 text-sm">Caricamento...</div>
        ) : apps.length === 0 ? (
          <div className="p-12 text-center">
            <BriefcaseIcon size={36} className="mx-auto text-gray-300 mb-3" />
            <p className="text-sm text-gray-500">Nessuna candidatura ancora.</p>
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {apps.map(app => (
              <li key={app.id}>
                <Link to={`/applications/${app.id}`} className="flex items-center justify-between px-5 py-4 hover:bg-gray-50">
                  <div className="flex items-center gap-3">
                    <BriefcaseIcon size={16} className="text-gray-400 shrink-0" />
                    <div>
                      <div className="text-sm font-medium text-gray-800">{app.role}</div>
                      <div className="text-xs text-gray-400">{app.company}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={app.status} />
                    <ChevronRightIcon size={16} className="text-gray-300" />
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
