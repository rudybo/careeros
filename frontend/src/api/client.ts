import axios from 'axios'
import type { CVDetail, AnalysisRecord, JobApplication, JobApplicationDetail } from '../types'

const api = axios.create({ baseURL: '/api/v1' })

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

// ── Career Strategist ─────────────────────────────────────────────────────────
export const startAnalysis = (cvId: number) =>
  api.post<{ analysis_id: number }>(`/cv/${cvId}/analyze`)

export const fetchAnalysis = (cvId: number, analysisId: number) =>
  api.get<AnalysisRecord>(`/cv/${cvId}/analysis/${analysisId}`).then(r => r.data)

export const fetchAnalysisList = (cvId: number) =>
  api.get<AnalysisRecord[]>(`/cv/${cvId}/analysis`).then(r => r.data)

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
