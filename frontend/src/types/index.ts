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

export interface SkillGap {
  skill: string
  priority: 'alta' | 'media' | 'bassa'
  why_needed: string
  how_to_acquire: string
  estimated_time: string
}

export interface RoadmapStep {
  order: number
  action: string
  category: string
  impact: string
  timeframe: string
}

export interface CareerAnalysis {
  executive_summary: string
  target_roles: TargetRole[]
  skill_gaps: SkillGap[]
  roadmap: RoadmapStep[]
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

export interface JobApplicationDetail extends JobApplication {
  job_description: string
  optimization: CVOptimization | null
}
