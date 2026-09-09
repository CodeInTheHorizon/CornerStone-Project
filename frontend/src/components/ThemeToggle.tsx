/** Switches between light and dark. */

import { Icon } from '@/components/Icon'
import { useTheme } from '@/hooks/useTheme'

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={`Switch to ${next} theme`}
      title={`Switch to ${next} theme`}
      className={`grid size-9 place-items-center rounded-card border border-border-hair text-muted transition-colors hover:border-accent hover:text-accent-text ${className ?? ''}`}
    >
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} className="size-[18px]" />
    </button>
  )
}
