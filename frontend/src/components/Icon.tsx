/**
 * Inline SVG icon set.
 *
 * Hand-rolled rather than pulled from an icon package: the landing page needs
 * roughly a dozen glyphs, and inlining keeps them theme-aware (they inherit
 * currentColor) with no extra dependency or network request.
 */

export type IconName =
  | 'brain'
  | 'pulse'
  | 'target'
  | 'chart'
  | 'trend'
  | 'refresh'
  | 'dashboard'
  | 'layers'
  | 'compass'
  | 'github'
  | 'linkedin'
  | 'mail'
  | 'globe'
  | 'sun'
  | 'moon'
  | 'menu'
  | 'close'
  | 'arrow-right'
  | 'whatsapp'
  | 'spark'

const paths: Record<IconName, React.ReactNode> = {
  brain: (
    <>
      <path d="M12 5a3 3 0 0 0-6 0 3 3 0 0 0-1.5 5.6A3 3 0 0 0 6 16a3 3 0 0 0 6 1" />
      <path d="M12 5a3 3 0 0 1 6 0 3 3 0 0 1 1.5 5.6A3 3 0 0 1 18 16a3 3 0 0 1-6 1" />
      <path d="M12 5v13" />
    </>
  ),
  pulse: (
    <>
      <path d="M3 12h4l2.5-7 5 14L17 12h4" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  trend: (
    <>
      <path d="M3 16.5 9 10l4 4 7.5-7.5" />
      <path d="M15 6.5h5.5V12" />
    </>
  ),
  refresh: (
    <>
      <path d="M20 12a8 8 0 1 1-2.6-5.9" />
      <path d="M20 4v4.5h-4.5" />
    </>
  ),
  dashboard: (
    <>
      <rect x="3" y="3" width="7.5" height="8.5" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
      <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
      <rect x="3" y="14.5" width="7.5" height="6.5" rx="1.5" />
    </>
  ),
  layers: (
    <>
      <path d="m12 3 9 5-9 5-9-5 9-5Z" />
      <path d="m3 13 9 5 9-5" />
    </>
  ),
  compass: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5.5-5.5 2 2-5.5 5.5-2Z" />
    </>
  ),
  github: (
    <>
      <path d="M9 19c-4.3 1.3-4.3-2.2-6-2.7m12 5v-3.4a3 3 0 0 0-.8-2.3c2.7-.3 5.5-1.3 5.5-6a4.6 4.6 0 0 0-1.3-3.2 4.3 4.3 0 0 0-.1-3.2s-1-.3-3.4 1.3a11.6 11.6 0 0 0-6 0C6.5 2.9 5.5 3.2 5.5 3.2a4.3 4.3 0 0 0-.1 3.2A4.6 4.6 0 0 0 4 9.7c0 4.6 2.8 5.6 5.5 6a3 3 0 0 0-.8 2.3V21" />
    </>
  ),
  linkedin: (
    <>
      <path d="M4.5 9.5v11M4.5 4.5v.01M10 20.5v-6a3 3 0 0 1 6 0v6" />
      <path d="M10 9.5v11" />
    </>
  ),
  mail: (
    <>
      <rect x="2.5" y="5" width="19" height="14" rx="2.5" />
      <path d="m3.5 7 8.5 6 8.5-6" />
    </>
  ),
  globe: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18Z" />
    </>
  ),
  sun: (
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2.5M12 19.5V22M4.9 4.9l1.8 1.8M17.3 17.3l1.8 1.8M2 12h2.5M19.5 12H22M4.9 19.1l1.8-1.8M17.3 6.7l1.8-1.8" />
    </>
  ),
  moon: (
    <>
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
    </>
  ),
  menu: (
    <>
      <path d="M3.5 7h17M3.5 12h17M3.5 17h17" />
    </>
  ),
  close: (
    <>
      <path d="m6 6 12 12M18 6 6 18" />
    </>
  ),
  'arrow-right': (
    <>
      <path d="M4 12h15M13 6l6 6-6 6" />
    </>
  ),
  whatsapp: (
    <>
      <path d="M3.5 20.5 5 16.4A8.2 8.2 0 1 1 8 19.3l-4.5 1.2Z" />
      <path d="M9 9.2c.3 2.3 2.4 4.4 4.7 4.7.6.1 1.3-.4 1.3-1v-.6l-1.8-.7-.8.8a6 6 0 0 1-2-2l.8-.8-.7-1.8h-.6c-.6 0-1.1.7-.9 1.4Z" />
    </>
  ),
  spark: (
    <>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" />
    </>
  ),
}

interface IconProps {
  name: IconName
  className?: string
  /** Provide when the icon carries meaning on its own. */
  title?: string
}

export function Icon({ name, className = 'size-5', title }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role={title ? 'img' : undefined}
      aria-label={title}
      aria-hidden={title ? undefined : true}
      focusable="false"
    >
      {paths[name]}
    </svg>
  )
}
