/**
 * OG image preview — screenshot this at 1200×630 to produce og-image.png.
 * Exact copy of the landing page layout with action buttons removed.
 */
"use client";

import { Check, CheckCircle, MessageCircle, Upload } from "lucide-react";

export default function OgPreview() {
  return (
    <div className="min-h-screen bg-zinc-950 p-4 sm:p-6" style={{ width: 1200, height: 630, minHeight: 630 }}>
      <div className="absolute inset-0 quaero-bg-grid" aria-hidden />
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <main className="relative mx-auto flex h-149.5 w-full max-w-6xl items-center">
        <section className="grid w-full items-center gap-8 lg:grid-cols-[1.15fr_0.85fr] lg:gap-12">
          <div className="w-full max-w-xl mx-auto space-y-6 text-center lg:mx-0 lg:text-left">
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-400 sm:text-6xl lg:text-7xl pb-2">
              Quaero
            </h1>
            <p className="max-w-xl mx-auto text-2xl leading-tight text-zinc-100 sm:text-3xl lg:mx-0">
              Ask questions across your PDFs and get grounded answers with
              citations.
            </p>
          </div>

          <div className="w-full max-w-md mx-auto space-y-5 rounded-xl border border-zinc-800 bg-zinc-900/70 p-6 sm:p-8 lg:max-w-none lg:mx-0">
            <p className="text-label-accent">How It Works</p>
            <ol className="space-y-4 text-sm text-zinc-300">
              <li className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-lapis-500/15 text-lapis-400 flex items-center justify-center">
                  <Upload className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-zinc-100">Upload PDFs</p>
                  <p className="text-zinc-400">Ingest files once, then query them anytime.</p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-lapis-500/15 text-lapis-400 flex items-center justify-center">
                  <MessageCircle className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-zinc-100">Ask in plain language</p>
                  <p className="text-zinc-400">Use natural prompts instead of manual searching.</p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-lapis-500/15 text-lapis-400 flex items-center justify-center">
                  <CheckCircle className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-zinc-100">Validate with citations</p>
                  <p className="text-zinc-400">Jump straight to supporting excerpts.</p>
                </div>
              </li>
            </ol>
            <div className="grid grid-cols-2 gap-4 border-t border-zinc-800 pt-4">
              <div>
                <p className="text-label-accent mb-2">Why it works</p>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-center gap-2 text-zinc-300">
                    <Check className="h-3.5 w-3.5 shrink-0 text-lapis-400" />
                    Cited answers only
                  </li>
                  <li className="flex items-center gap-2 text-zinc-300">
                    <Check className="h-3.5 w-3.5 shrink-0 text-lapis-400" />
                    Your documents stay scoped
                  </li>
                  <li className="flex items-center gap-2 text-zinc-300">
                    <Check className="h-3.5 w-3.5 shrink-0 text-lapis-400" />
                    Fast retrieval + chat workflow
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
