import { useEffect, useRef, useState } from 'react'
import AgentAvatar from './AgentAvatar'

type AgentName = 'Minerva' | 'Vera' | 'Clio' | 'Iris'

interface Props {
  name: AgentName
  message: string
  active?: boolean   // puntini animati quando l'agente sta lavorando
}

const STORAGE_KEY = 'agentBubblePos'
const WIDTH = 300

const AGENT_BG: Record<AgentName, string> = {
  Minerva: 'bg-gradient-to-br from-violet-100 to-violet-50 border-violet-300',
  Vera:    'bg-gradient-to-br from-blue-100 to-blue-50 border-blue-300',
  Clio:    'bg-gradient-to-br from-pink-100 to-pink-50 border-pink-300',
  Iris:    'bg-gradient-to-br from-orange-100 to-orange-50 border-orange-300',
}

export default function AgentBubble({ name, message, active = false }: Props) {
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

  return (
    <div
      style={{ left: pos.x, top: pos.y, width: WIDTH }}
      className={`fixed z-50 flex items-center gap-3 border rounded-xl p-3 shadow-lg cursor-move select-none ${AGENT_BG[name]}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      title="Trascina per spostare"
    >
      {/* cella avatar — userà il volto vero appena disponibile in /agents/<nome>.png */}
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
      </div>
    </div>
  )
}
