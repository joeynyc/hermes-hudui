/** Utility for profile state and formatting */

export const PROFILE_KEY = 'hermes_hud_selected_profile'

/** Get current profile from localStorage */
export function getSelectedProfile(): string {
  return localStorage.getItem(PROFILE_KEY) || 'default'
}

/** Set current profile to localStorage */
export function setSelectedProfile(profile: string) {
  localStorage.setItem(PROFILE_KEY, profile)
}

/** Format profile name for display */
export function profileName(name: string): string {
  if (!name || name === 'default') return 'Core'
  return name.charAt(0).toUpperCase() + name.slice(1)
}
