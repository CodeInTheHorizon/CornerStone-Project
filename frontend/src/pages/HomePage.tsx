/**
 * Public landing page (Phase 2).
 *
 * Section order follows PROJECT_CONTEXT.md section 7.
 */

import { Footer } from '@/components/Footer'
import { Navbar } from '@/components/Navbar'
import { Contact } from '@/sections/Contact'
import { Developer } from '@/sections/Developer'
import { Features } from '@/sections/Features'
import { Hero } from '@/sections/Hero'
import { HowItWorks } from '@/sections/HowItWorks'
import { Stats } from '@/sections/Stats'
import { WhyChoose } from '@/sections/WhyChoose'

export function HomePage() {
  return (
    <>
      <a
        href="#main"
        className="sr-only rounded-full bg-accent px-4 py-2 text-sm font-medium text-accent-ink
                   focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-[60]"
      >
        Skip to content
      </a>

      <Navbar />

      <main id="main">
        <Hero />
        <HowItWorks />
        <Stats />
        <WhyChoose />
        <Developer />
        <Features />
        <Contact />
      </main>

      <Footer />
    </>
  )
}
