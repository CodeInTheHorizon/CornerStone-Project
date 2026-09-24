/** Shared button/link styling for calls to action. */

import { cn } from '@/lib/cn'

type Variant = 'primary' | 'secondary' | 'ghost'
type Size = 'sm' | 'md' | 'lg'

const base =
  'inline-flex items-center justify-center gap-2 rounded-card font-medium ' +
  'transition-[background-color,border-color,color,box-shadow,transform] duration-200 ' +
  'active:translate-y-px disabled:pointer-events-none disabled:opacity-50'

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-accent-ink shadow-accent hover:bg-accent-hover',
  secondary:
    'border border-border-strong bg-surface text-foreground hover:border-accent hover:bg-accent-soft hover:text-accent-text',
  ghost: 'text-muted hover:bg-accent-soft hover:text-accent-text',
}

const sizes: Record<Size, string> = {
  sm: 'px-3.5 py-2 text-sm',
  md: 'px-5 py-2.5 text-sm',
  lg: 'rounded-full px-7 py-3.5 text-base',
}

interface CommonProps {
  variant?: Variant
  size?: Size
  className?: string
  children: React.ReactNode
}

type ButtonProps = CommonProps &
  React.ButtonHTMLAttributes<HTMLButtonElement> & { as?: 'button' }
type AnchorProps = CommonProps &
  React.AnchorHTMLAttributes<HTMLAnchorElement> & { as: 'a' }

export function Button(props: ButtonProps | AnchorProps) {
  const {
    variant = 'primary',
    size = 'md',
    className,
    children,
    ...rest
  } = props
  const classes = cn(base, variants[variant], sizes[size], className)

  if (rest.as === 'a') {
    const { as: _as, ...anchorProps } = rest as AnchorProps
    return (
      <a className={classes} {...anchorProps}>
        {children}
      </a>
    )
  }

  const { as: _as, ...buttonProps } = rest as ButtonProps
  return (
    <button className={classes} {...buttonProps}>
      {children}
    </button>
  )
}
