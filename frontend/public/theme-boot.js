/**
 * Applies the stored theme before the first paint.
 *
 * This is a separate file rather than an inline <script> on purpose: the page
 * ships a Content-Security-Policy of `default-src 'self'` with no
 * `unsafe-inline` for scripts, and loosening that to avoid a brief flash would
 * be a poor trade on a closed network. A same-origin file is allowed, and
 * because it is a classic (non-module, non-deferred) script it runs while the
 * parser is blocked — before anything is painted.
 *
 * Kept deliberately tiny and dependency-free. It duplicates a few lines of
 * themeStore.ts because it must run before any bundle is fetched.
 */
(function () {
  try {
    var stored = localStorage.getItem('servizon.theme')
    var preference = stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'system'
    var theme =
      preference === 'system'
        ? window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light'
        : preference
    document.documentElement.setAttribute('data-theme', theme)
  } catch {
    // Private browsing can throw on localStorage access. Light is the safe
    // default; a wrong theme is a blemish, a blank page is a failure.
    document.documentElement.setAttribute('data-theme', 'light')
  }
})()
