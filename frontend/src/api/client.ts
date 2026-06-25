import axios from 'axios'
import type { CVDetail, AnalysisRecord, JobApplication, JobApplicationDetail, UserPreferences, JobOpportunity, RoadmapItem, AtsKeywordItem } from '../types'

const api = axios.create({ baseURL: '/api/v1' })

// ── System info ─────────────────────────────────────────────────────────────
export interface SystemInfo { provider: string; model: string; version: string }
export const fetchInfo = () =>
  api.get<SystemInfo>('/info').then(r => r.data)

// ── CV ────────────────────────────────────────────────────────────────────────
export const uploadCV = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return api.post<{ id: number; filename: string; status: string }>('/cv/upload', form)
}

export const parseCV = (cvId: number) =>
  api.post(`/cv/${cvId}/parse`)

export const fetchCV = (cvId: number) =>
  api.get<CVDetail>(`/cv/${cvId}`).then(r => r.data)

export const fetchCVList = () =>
  api.get<CVDetail[]>('/cv/').then(r => r.data)

export const deleteCV = (cvId: number) =>
  api.delete(`/cv/${cvId}`)

// ── Career Strategist ─────────────────────────────────────────────────────────
export const startAnalysis = (cvId: number) =>
  api.post<{ analysis_id: number }>(`/cv/${cvId}/analyze`)

export const fetchAnalysis = (cvId: number, analysisId: number) =>
  api.get<AnalysisRecord>(`/cv/${cvId}/analysis/${analysisId}`).then(r => r.data)

export const fetchAnalysisList = (cvId: number) =>
  api.get<AnalysisRecord[]>(`/cv/${cvId}/analysis`).then(r => r.data)

// Roadmap checklist persistente
export const fetchRoadmap = (cvId: number) =>
  api.get<RoadmapItem[]>(`/cv/${cvId}/roadmap`).then(r => r.data)

export const updateRoadmapItem = (cvId: number, itemId: number, status: 'todo' | 'done' | 'dismissed') =>
  api.patch(`/cv/${cvId}/roadmap/${itemId}`, { status })

// Keyword ATS checklist persistente
export const fetchAtsKeywords = (cvId: number) =>
  api.get<AtsKeywordItem[]>(`/cv/${cvId}/ats-keywords`).then(r => r.data)

export const updateAtsKeyword = (cvId: number, itemId: number, status: 'todo' | 'added' | 'ignored' | 'gap') =>
  api.patch(`/cv/${cvId}/ats-keywords/${itemId}`, { status })

// ── Applications / CV Expert ──────────────────────────────────────────────────
export const createApplication = (data: { cv_id: number; company: string; role: string; job_description: string }) =>
  api.post<JobApplication>('/applications/', data).then(r => r.data)

export const startOptimization = (appId: number) =>
  api.post(`/applications/${appId}/analyze`)

export const fetchApplication = (appId: number) =>
  api.get<JobApplicationDetail>(`/applications/${appId}`).then(r => r.data)

export const fetchApplicationList = () =>
  api.get<JobApplication[]>('/applications/').then(r => r.data)

export const updateApplicationStatus = (appId: number, status: string) =>
  api.patch<JobApplication>(`/applications/${appId}/status`, { status }).then(r => r.data)

export const startCoverLetter = (appId: number) =>
  api.post(`/applications/${appId}/cover-letter`)

// ── Market Scout ──────────────────────────────────────────────────────────────
export const fetchPreferences = () =>
  api.get<UserPreferences | null>('/market/preferences').then(r => r.data)

export const savePreferences = (data: Partial<UserPreferences>) =>
  api.put<UserPreferences>('/market/preferences', data).then(r => r.data)

export const startMarketSearch = (cvId: number) =>
  api.post(`/market/search?cv_id=${cvId}`)

export const fetchSearchStatus = () =>
  api.get<{ running: boolean; last_error: string | null; last_count: number | null }>('/market/search/status').then(r => r.data)

export const fetchOpportunities = (statusFilter?: string, limit: number = 10) =>
  api.get<JobOpportunity[]>('/market/opportunities', { params: { ...(statusFilter ? { status_filter: statusFilter } : {}), limit } }).then(r => r.data)

export const updateOpportunityStatus = (oppId: number, status: string) =>
  api.patch<JobOpportunity>(`/market/opportunities/${oppId}/status`, { status }).then(r => r.data)

export const createOpportunityDraft = (oppId: number, cvId: number) =>
  api.post(`/market/opportunities/${oppId}/draft?cv_id=${cvId}`)
