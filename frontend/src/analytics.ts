import posthog from 'posthog-js'

export const initAnalytics = (): void => {
  const apiKey = import.meta.env.VITE_POSTHOG_KEY as string | undefined
  if (!apiKey) return
  const apiHost = (import.meta.env.VITE_POSTHOG_HOST as string | undefined) || 'https://app.posthog.com'

  posthog.init(apiKey, {
    api_host: apiHost,
    capture_pageview: true,
    autocapture: true,
    persistence: 'localStorage',
    person_profiles: 'identified_only',
  })
}

export { posthog }



