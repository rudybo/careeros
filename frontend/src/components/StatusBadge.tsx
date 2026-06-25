const config: Record<string, { label: string; className: string }> = {
  pending:   { label: 'In attesa',   className: 'bg-gray-100 text-gray-600' },
  parsing:   { label: 'Parsing...',  className: 'bg-yellow-100 text-yellow-700 animate-pulse' },
  analyzing:  { label: 'Analisi...',   className: 'bg-blue-100 text-blue-700 animate-pulse' },
  generating: { label: 'Generazione...', className: 'bg-purple-100 text-purple-700 animate-pulse' },
  parsed:    { label: 'Pronto',      className: 'bg-green-100 text-green-700' },
  completed: { label: 'Completato',  className: 'bg-green-100 text-green-700' },
  ready:     { label: 'Pronto',      className: 'bg-green-100 text-green-700' },
  draft:     { label: 'Bozza',       className: 'bg-gray-100 text-gray-600' },
  applied:   { label: 'Inviato',     className: 'bg-blue-100 text-blue-700' },
  interview: { label: 'Colloquio',   className: 'bg-purple-100 text-purple-700' },
  offer:     { label: 'Offerta!',    className: 'bg-emerald-100 text-emerald-700 font-semibold' },
  rejected:  { label: 'Rifiutato',   className: 'bg-red-100 text-red-600' },
  error:     { label: 'Errore',      className: 'bg-red-100 text-red-600' },
}

export default function StatusBadge({ status }: { status: string }) {
  const { label, className } = config[status] ?? { label: status, className: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${className}`}>
      {label}
    </span>
  )
}
