import { useState } from 'react'

type AgentName = 'Minerva' | 'Vera' | 'Clio' | 'Iris'

const SK = '#fde8d8'
const BR = '#7a5248'
const LP = '#d4706a'
const BL = '#f9a8d4'

function FaceBase({ iris }: { iris: string }) {
  return <>
    <rect x="36" y="62" width="8" height="5" rx="3" fill={SK}/>
    <ellipse cx="40" cy="47" rx="14" ry="16.5" fill={SK}/>
    <circle cx="26.5" cy="47" r="3.5" fill={SK}/>
    <circle cx="53.5" cy="47" r="3.5" fill={SK}/>
    <path d="M31.5 38.5 Q35 36.5 38.5 38" stroke={BR} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
    <path d="M41.5 38 Q45 36.5 48.5 38.5" stroke={BR} strokeWidth="1.6" fill="none" strokeLinecap="round"/>
    <ellipse cx="35" cy="43.5" rx="4" ry="3.5" fill="white"/>
    <circle cx="35" cy="43.5" r="2.6" fill={iris}/>
    <circle cx="35" cy="43.5" r="1.4" fill="#050510"/>
    <circle cx="36.3" cy="42.3" r="0.9" fill="white"/>
    <ellipse cx="45" cy="43.5" rx="4" ry="3.5" fill="white"/>
    <circle cx="45" cy="43.5" r="2.6" fill={iris}/>
    <circle cx="45" cy="43.5" r="1.4" fill="#050510"/>
    <circle cx="46.3" cy="42.3" r="0.9" fill="white"/>
    <path d="M39 50 Q40 52 41 50" stroke="#dda090" strokeWidth="1.2" fill="none" strokeLinecap="round"/>
    <path d="M36.5 55.5 Q40 58.5 43.5 55.5" stroke={LP} strokeWidth="1.8" fill="none" strokeLinecap="round"/>
    <ellipse cx="29.5" cy="51.5" rx="4" ry="2.5" fill={BL} opacity="0.35"/>
    <ellipse cx="50.5" cy="51.5" rx="4" ry="2.5" fill={BL} opacity="0.35"/>
  </>
}

function MinervaSvg() {
  return (
    <svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="a-min" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#c4b5fd"/>
          <stop offset="100%" stopColor="#5b21b6"/>
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="40" fill="url(#a-min)"/>
      <ellipse cx="40" cy="36" rx="19" ry="23" fill="#6d28d9"/>
      <path d="M21 42 Q17 60 21 78" stroke="#6d28d9" strokeWidth="9" fill="none" strokeLinecap="round"/>
      <path d="M59 42 Q63 60 59 78" stroke="#6d28d9" strokeWidth="9" fill="none" strokeLinecap="round"/>
      <FaceBase iris="#8b5cf6"/>
      <path d="M25 36 Q29 17 40 15 Q51 17 55 36 Q50 32 44 34 Q40 30 36 34 Q30 32 25 36Z" fill="#7c3aed"/>
      <path d="M30 18 L33 10 L37 16 L40 8 L43 16 L47 10 L50 18" stroke="#fbbf24" strokeWidth="2" fill="none" strokeLinejoin="round"/>
      <rect x="29" y="17" width="22" height="3" rx="1.5" fill="#f59e0b" opacity="0.85"/>
    </svg>
  )
}

function VeraSvg() {
  return (
    <svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="a-ver" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#93c5fd"/>
          <stop offset="100%" stopColor="#1d4ed8"/>
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="40" fill="url(#a-ver)"/>
      <path d="M22 34 Q21 62 30 68 L50 68 Q59 62 58 34 Q52 20 40 18 Q28 20 22 34Z" fill="#1e40af"/>
      <FaceBase iris="#3b82f6"/>
      <path d="M26 35 Q29 19 40 17 Q51 19 54 35 Q50 31 45 33 Q40 30 35 33 Q30 31 26 35Z" fill="#2563eb"/>
      <ellipse cx="35" cy="43.5" rx="5.5" ry="4.5" fill="none" stroke="#94a3b8" strokeWidth="1.4"/>
      <ellipse cx="45" cy="43.5" rx="5.5" ry="4.5" fill="none" stroke="#94a3b8" strokeWidth="1.4"/>
      <line x1="40.5" y1="43.5" x2="39.5" y2="43.5" stroke="#94a3b8" strokeWidth="1.4"/>
      <line x1="29.5" y1="43.5" x2="26.5" y2="44.5" stroke="#94a3b8" strokeWidth="1.3"/>
      <line x1="50.5" y1="43.5" x2="53.5" y2="44.5" stroke="#94a3b8" strokeWidth="1.3"/>
    </svg>
  )
}

function ClioSvg() {
  return (
    <svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="a-cli" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#f9a8d4"/>
          <stop offset="100%" stopColor="#be185d"/>
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="40" fill="url(#a-cli)"/>
      <circle cx="40" cy="30" r="22" fill="#db2777"/>
      <circle cx="18" cy="38" r="11" fill="#be185d"/>
      <circle cx="62" cy="38" r="11" fill="#be185d"/>
      <circle cx="22" cy="22" r="10" fill="#db2777"/>
      <circle cx="58" cy="22" r="10" fill="#db2777"/>
      <circle cx="40" cy="13" r="9" fill="#be185d"/>
      <FaceBase iris="#ec4899"/>
      <path d="M26 36 Q28 18 40 16 Q52 18 54 36 Q50 30 46 34 Q42 29 38 34 Q34 29 30 33 Q26 29 26 36Z" fill="#ec4899"/>
      <g transform="translate(53,24)">
        <circle cx="0" cy="-4"   r="2.8" fill="#fce7f3"/>
        <circle cx="3.8" cy="-1.2" r="2.8" fill="#fce7f3"/>
        <circle cx="2.4" cy="3.2"  r="2.8" fill="#fce7f3"/>
        <circle cx="-2.4" cy="3.2" r="2.8" fill="#fce7f3"/>
        <circle cx="-3.8" cy="-1.2" r="2.8" fill="#fce7f3"/>
        <circle cx="0" cy="0" r="2.2" fill="#fde68a"/>
      </g>
    </svg>
  )
}

function IrisSvg() {
  return (
    <svg viewBox="0 0 80 80" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="a-iri" cx="50%" cy="30%" r="70%">
          <stop offset="0%" stopColor="#fed7aa"/>
          <stop offset="100%" stopColor="#c2410c"/>
        </radialGradient>
      </defs>
      <circle cx="40" cy="40" r="40" fill="url(#a-iri)"/>
      <ellipse cx="41" cy="34" rx="20" ry="23" fill="#ea580c"/>
      <path d="M37 15 Q34 6 29 3"  stroke="#f97316" strokeWidth="4.5" fill="none" strokeLinecap="round"/>
      <path d="M44 13 Q47 5 52 3"  stroke="#ea580c" strokeWidth="4"   fill="none" strokeLinecap="round"/>
      <path d="M51 18 Q57 12 62 9" stroke="#f97316" strokeWidth="3.5" fill="none" strokeLinecap="round"/>
      <path d="M20 44 Q16 62 20 78" stroke="#ea580c" strokeWidth="9" fill="none" strokeLinecap="round"/>
      <path d="M60 44 Q64 62 60 78" stroke="#ea580c" strokeWidth="7" fill="none" strokeLinecap="round"/>
      <FaceBase iris="#f97316"/>
      <path d="M24 34 Q28 16 41 14 Q52 16 57 32 Q52 36 46 33 Q41 29 36 33 Q30 37 24 34Z" fill="#f97316"/>
    </svg>
  )
}

interface Props {
  name: AgentName
  size?: number
}

export default function AgentAvatar({ name, size = 48 }: Props) {
  const components: Record<AgentName, () => JSX.Element> = {
    Minerva: MinervaSvg,
    Vera: VeraSvg,
    Clio: ClioSvg,
    Iris: IrisSvg,
  }
  const Avatar = components[name]
  const [imgError, setImgError] = useState(false)
  return (
    <div style={{ width: size, height: size }} className="rounded-full overflow-hidden shrink-0 shadow-md">
      {imgError ? (
        <Avatar />
      ) : (
        <img
          src={`/agents/${name.toLowerCase()}.png`}
          alt={name}
          className="w-full h-full object-cover"
          onError={() => setImgError(true)}
        />
      )}
    </div>
  )
}
