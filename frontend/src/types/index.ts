export interface CV {
  id: number
  filename: string
  status: 'pending' | 'parsing' | 'parsed' | 'error'
  created_at: string
  updated_at?: string
}

export interface WorkExperience {
  company: string | null
  role: string | null
  start_date: string | null
  end_date: string | null
  description: string | null
}

export interface Education {
  institution: string | null
  degree: string | null
  field: string | null
  year: string | null
}

export interface ParsedCV {
  full_name: string
  email: string | null
  phone: string | null
  summary: string | null
  skills: string[]
  languages: string[]
  work_experience: WorkExperience[]
  education: Education[]
  certifications: string[]
}

export interface CVDetail extends CV {
  parsed_data: ParsedCV | null
}

// Career Strategist
export interface TargetRole {
  title: string
  match_percentage: number
  reason: string
  market_demand: 'alto' | 'medio' | 'basso'
}

export interface Resource {
  title: string
  provider: string
  cost: 'gratuito' | 'a pagamento'
}

export interface SkillGap {
  skill: string
  priority: 'alta' | 'media' | 'bassa'
  why_needed: string
  how_to_acquire: string
  estimated_time: string
  resources?: Resource[]
}

export interface AtsKeyword {
  keyword: string
  reason: string
}

// Checklist persistente keyword ATS (per CV)
// todo = da gestire · added = aggiunta al CV · ignored = già presente/falso positivo · gap = competenza da acquisire
export interface AtsKeywordItem {
  id: number
  cv_id: number
  keyword: string
  reason: string | null
  status: 'todo' | 'added' | 'ignored' | 'gap'
  created_at: string
  updated_at: string
}

export interface RoadmapStep {
  order: number
  action: string
  category: string
  impact: string
  timeframe: string
}

// Checklist persistente (per CV) — sopravvive ai ricalcoli
export interface RoadmapItem {
  id: number
  cv_id: number
  action: string
  category: string
  impact: string | null
  timeframe: string | null
  status: 'todo' | 'done' | 'dismissed'
  created_at: string
}

export interface CareerAnalysis {
  executive_summary: string
  target_roles: TargetRole[]
  skill_gaps: SkillGap[]
  roadmap: RoadmapStep[]
  ats_keywords?: AtsKeyword[]
}

export interface AnalysisRecord {
  id: number
  cv_id: number
  status: 'pending' | 'analyzing' | 'completed' | 'error'
  analysis: CareerAnalysis | null
  created_at: string
  updated_at: string
}

// CV Expert / Applications
export interface SectionSuggestion {
  section: string
  issue: string
  suggestion: string
}

export interface CVOptimization {
  match_score: number
  matched_keywords: string[]
  missing_keywords: string[]
  ats_warnings: string[]
  section_suggestions: SectionSuggestion[]
  cover_letter_hints: string[]
  optimized_summary: string
}

export interface JobApplication {
  id: number
  cv_id: number
  company: string
  role: string
  status: 'draft' | 'analyzing' | 'ready' | 'applied' | 'interview' | 'offer' | 'rejected' | 'error'
  applied_at: string | null
  created_at: string
  updated_at: string
}

// Market Scout
export interface UserPreferences {
  id?: number
  ral_min: number | null
  ral_max: number | null
  city: string | null
  radius_km: number | null
  work_mode: 'remote' | 'hybrid' | 'onsite' | null
  sectors: string[] | null
  target_roles: string[] | null
  contract_type: string | null
  company_size: string | null
  language: string | null
  available_travel: boolean | null
  updated_at?: string
}

export interface JobOpportunity {
  id: number
  external_id: string
  source: string
  title: string
  company: string | null
  location: string | null
  url: string
  salary_min: number | null
  salary_max: number | null
  work_mode: string | null
  match_score: number | null
  match_reasons: string[] | null
  status: 'new' | 'saved' | 'dismissed' | 'applied'
  draft_status: 'none' | 'generating' | 'ready'
  gmail_url: string | null
  found_at: string
}

export interface CoverLetter {
  subject: string
  full_text: string
}

export interface StatusEvent {
  status: string
  at: string
}

export interface JobApplicationDetail extends JobApplication {
  job_description: string
  status_history: StatusEvent[]
  optimization: CVOptimization | null
  cover_letter: CoverLetter | null
  cover_letter_status: 'idle' | 'generating' | 'ready' | 'error'
}
