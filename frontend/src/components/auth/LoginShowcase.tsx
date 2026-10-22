import { HeroIllustration } from './HeroIllustration'

/** Left half of the login screen: hero artwork with the product name in the bottom-left corner. */
export function LoginShowcase() {
  return (
    <aside className="bg-login-hero relative hidden overflow-hidden text-white lg:flex lg:flex-col">
      {/* dotted grid + soft glows */}
      <div className="absolute inset-0 bg-[radial-gradient(rgba(255,255,255,0.08)_1px,transparent_1px)] [background-size:22px_22px]" />
      <div className="absolute -top-24 -left-24 h-96 w-96 rounded-full bg-brand-400/25 blur-3xl" />
      <div className="absolute top-1/3 -right-32 h-[28rem] w-[28rem] rounded-full bg-violet-500/20 blur-3xl" />

      <div className="relative flex flex-1 items-center justify-center px-10 pt-10 pb-44">
        <div className="h-full max-h-[620px] w-full max-w-[680px]">
          <HeroIllustration />
        </div>
      </div>

      {/* bottom-left product name over a fade, like a hero caption */}
      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#0b0a24] via-[#0b0a24]/80 to-transparent px-12 pt-24 pb-12">
        <p className="text-[11px] font-semibold tracking-[0.32em] text-brand-200">POWERED BY</p>
        <p className="mt-2 text-4xl font-extrabold tracking-tight">SQL QUERY AGENT</p>
        <p className="mt-2 text-lg text-brand-100/90">Natural-language analytics for your database</p>
      </div>
    </aside>
  )
}
