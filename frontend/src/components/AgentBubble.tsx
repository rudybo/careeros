import { useEffect, useRef, useState } from 'react'
import AgentAvatar from './AgentAvatar'

type AgentName = 'Minerva' | 'Vera' | 'Clio' | 'Iris'

interface Props {
  name: AgentName
  message: string
  active?: boolean   // puntini animati quando l'agente sta lavorando
  action?: { label: string; onClick: () => void }
}

const STORAGE_KEY = 'agentBubblePos'
const WIDTH = 300

const AGENT_BG: Record<AgentName, string> = {
  Minerva: 'bg-gradient-to-br from-violet-100 to-violet-50 border-violet-300',
  Vera:    'bg-gradient-to-br from-blue-100 to-blue-50 border-blue-300',
  Clio:    'bg-gradient-to-br from-pink-100 to-pink-50 border-pink-300',
  Iris:    'bg-gradient-to-br from-orange-100 to-orange-50 border-orange-300',
}

function useIsMobile() {
  const [mobile, setMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 767px)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const handler = (e: MediaQueryListEvent) => setMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])
  return mobile
}

export default function AgentBubble({ name, message, active = false, action }: Props) {
  const isMobile = useIsMobile()
  const [pos, setPos] = useState<{ x: number; y: number }>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) return JSON.parse(saved)
    } catch { /* ignore */ }
    return { x: window.innerWidth - WIDTH - 24, y: window.innerHeight - 120 }
  })
  const drag = useRef<{ dx: number; dy: number } | null>(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pos))
  }, [pos])

  const onPointerDown = (e: React.PointerEvent) => {
    drag.current = { dx: e.clientX - pos.x, dy: e.clientY - pos.y }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag.current) return
    const x = Math.min(Math.max(0, e.clientX - drag.current.dx), window.innerWidth - WIDTH)
    const y = Math.min(Math.max(0, e.clientY - drag.current.dy), window.innerHeight - 60)
    setPos({ x, y })
  }
  const onPointerUp = (e: React.PointerEvent) => {
    drag.current = null
    ;(e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId)
  }

  const content = (
    <>
      {/* cella avatar — volto vero da /agents/<nome>.png */}
      <AgentAvatar name={name} size={44} />
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-gray-900 text-sm">{name}</span>
          {active && (
            <span className="flex gap-0.5">
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-1.5 h-1.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </span>
          )}
        </div>
        <p className="text-sm text-gray-600 mt-0.5">{message}</p>
        {action && (
          <button
            onPointerDown={e => e.stopPropagation()}
            onClick={action.onClick}
            className="mt-2 px-3 py-1 text-xs font-medium rounded-lg bg-violet-600 text-white hover:bg-violet-700"
          >
            {action.label}
          </button>
        )}
      </div>
    </>
  )

  // Mobile: barra fissa in basso, non trascinabile
  if (isMobile) {
    return (
      <div className={`fixed bottom-0 left-0 right-0 z-50 flex items-center gap-3 border-t p-3 shadow-lg ${AGENT_BG[name]}`}>
        {content}
      </div>
    )
  }

  // Desktop: vignetta flottante trascinabile
  return (
    <div
      style={{ left: pos.x, top: pos.y, width: WIDTH }}
      className={`fixed z-50 flex items-center gap-3 border rounded-xl p-3 shadow-lg cursor-move select-none touch-none ${AGENT_BG[name]}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      title="Trascina per spostare"
    >
      {content}
    </div>
  )
}
