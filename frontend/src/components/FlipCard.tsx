import { motion } from 'framer-motion'

import { Icon, type IconName } from '@/components/Icon'

interface FlipCardProps {
  icon: IconName
  title: string
  body: string
}

export function FlipCard({ icon, title, body }: FlipCardProps) {
  return (
    <motion.div
      className="group relative flex h-64 flex-col justify-between overflow-hidden rounded-panel border border-border-hair bg-surface p-8 shadow-card transition-colors duration-300 hover:border-accent/30"
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
    >
      <div>
        <span
          className="grid size-11 place-items-center rounded-2xl bg-linear-to-br from-accent-soft to-accent/5 text-accent-text"
          aria-hidden="true"
        >
          <Icon name={icon} className="size-[22px]" />
        </span>
        <h3 className="mt-5 text-xl font-semibold">{title}</h3>
        <p className="mt-2 text-sm leading-relaxed text-muted sm:hidden">{body}</p>
      </div>

      <div className="absolute inset-x-0 bottom-0 translate-y-full bg-linear-to-t from-surface via-surface to-surface/0 px-8 pt-10 pb-8 transition-transform duration-300 ease-standard group-hover:translate-y-0 group-focus-within:translate-y-0 sm:block hidden">
        <p className="text-[15px] leading-relaxed text-muted">{body}</p>
      </div>

      <div
        className="absolute inset-x-0 bottom-0 h-px bg-linear-to-r from-transparent via-accent/40 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        aria-hidden="true"
      />
    </motion.div>
  )
}
