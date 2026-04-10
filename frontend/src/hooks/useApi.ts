import useSWR, { mutate } from 'swr'
import { getSelectedProfile } from '../lib/profile'

const fetcher = async (url: string) => {
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

export function useApi<T = any>(path: string | null, refreshInterval = 30000) {
  const profile = getSelectedProfile()
  const key = path 
    ? `/api${path}${path.includes('?') ? '&' : '?'}profile=${profile}` 
    : null
    
  return useSWR<T>(key, fetcher, {
    refreshInterval,
    revalidateOnFocus: false,
    dedupingInterval: 5000,
    errorRetryCount: 3,
    errorRetryInterval: 2000,
    onError: (err) => {
      if (path) {
        console.warn(`[HUD] ${path}: ${err.message}`)
      }
    },
  })
}

/** Force-revalidate all SWR caches (for manual refresh) */
export function refreshAll() {
  mutate(
    (key) => typeof key === 'string' && key.startsWith('/api'),
    undefined,
    { revalidate: true }
  )
}
