import { Headphones, Smartphone, Laptop, Tv, Camera, Watch, Speaker, Gamepad2, Cpu, MonitorSmartphone, Package } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const mapping: Record<string, LucideIcon> = {
  headphones: Headphones,
  earphones: Headphones,
  earbuds: Headphones,
  audio: Speaker,
  speaker: Speaker,
  smartphone: Smartphone,
  phone: Smartphone,
  mobile: Smartphone,
  laptop: Laptop,
  notebook: Laptop,
  computer: Laptop,
  television: Tv,
  tv: Tv,
  monitor: MonitorSmartphone,
  camera: Camera,
  watch: Watch,
  smartwatch: Watch,
  gaming: Gamepad2,
  processor: Cpu,
  tablet: MonitorSmartphone,
}

export function categoryIcon(category: string): LucideIcon {
  const lower = category.toLowerCase()
  for (const [key, icon] of Object.entries(mapping)) {
    if (lower.includes(key)) return icon
  }
  return Package
}
