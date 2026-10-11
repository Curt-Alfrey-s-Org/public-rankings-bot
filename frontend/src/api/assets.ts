/**
 * Assets API: list and upload pics/videos for appearance (avatar, background, splash).
 */

import apiClient from './client'

// Empty VITE_API_URL = same-origin (works with Vite proxy in dev and Nginx in prod)
const _raw = import.meta.env.VITE_API_URL
const _normalized = (typeof _raw === 'string' && _raw.trim() !== '')
  ? _raw.replace(/\/+$/, '')
  : ''
const API_BASE = _normalized ? `${_normalized}/api` : '/api'

export interface AssetEntry {
  path: string
  name: string
  type: 'image' | 'video'
}

export async function getAssets(): Promise<AssetEntry[]> {
  const { data } = await apiClient.get<{ files: AssetEntry[] }>('/assets')
  return data.files ?? []
}

export async function uploadAssets(files: File[]): Promise<string[]> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  const { data } = await apiClient.post<{ urls: string[] }>('/assets/upload', form, {
    timeout: 60_000,
  })
  return data.urls ?? []
}

/**
 * Convert asset relative path to full URL.
 * If URL already starts with http://, https://, or /, return as-is. Otherwise prepend API_BASE.
 */
export function assetUrl(path: string): string {
  if (!path) return ''
  if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/')) {
    return path
  }
  return `${API_BASE}/assets/${path}`
}
