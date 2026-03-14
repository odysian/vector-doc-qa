/**
 * Landing page (/). Branded entry point; links to login and register.
 * Redirects to dashboard if user already has a token.
 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, CheckCircle, MessageCircle, Upload } from "lucide-react";
import { authService } from "@/lib/services/authService";

export default function Home() {
  const router = useRouter();
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [error, setError] = useState("");
  const primaryActionClass =
    "inline-flex items-center justify-center rounded-md border border-lapis-500 bg-lapis-600 px-8 py-3 text-base font-medium text-white transition hover:bg-lapis-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50";
  const secondaryActionClass =
    "inline-flex items-center justify-center rounded-md border border-lapis-500/40 px-8 py-3 text-base font-medium text-lapis-200 transition hover:bg-lapis-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50 disabled:cursor-not-allowed disabled:opacity-60";

  useEffect(() => {
    if (authService.hasActiveSession()) {
      router.replace("/dashboard");
    }
  }, [router]);

  const handleTryDemo = async () => {
    setError("");
    setLoadingDemo(true);
    try {
      await authService.loginDemo();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Demo login failed");
    } finally {
      setLoadingDemo(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 p-4 sm:p-6">
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <main className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-6xl items-center py-6 sm:py-8">
        <section className="grid w-full items-center gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10">
          <div className="w-full max-w-xl mx-auto space-y-6 text-center lg:mx-0 lg:text-left">
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-300 sm:text-6xl lg:text-7xl">
              Quaero
            </h1>
            <p className="max-w-xl mx-auto text-2xl leading-tight text-zinc-100 sm:text-3xl lg:mx-0">
              Ask questions across your PDFs and get grounded answers with
              citations.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:justify-center lg:justify-start">
              <Link href="/login" className={primaryActionClass}>
                Sign In
              </Link>
              <button
                type="button"
                onClick={handleTryDemo}
                disabled={loadingDemo}
                className={secondaryActionClass}
              >
                {loadingDemo ? "Accessing..." : "Try Demo"}
              </button>
            </div>
            <p className="text-sm text-zinc-500">
              New here?{" "}
              <Link
                href="/register"
                className="text-lapis-400 hover:text-lapis-300 transition-colors"
              >
                Create a free account →
              </Link>
            </p>
            {error && <p className="text-sm text-red-400">{error}</p>}
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
                  <p className="text-zinc-400">
                    Ingest files once, then query them anytime.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-lapis-500/15 text-lapis-400 flex items-center justify-center">
                  <MessageCircle className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-zinc-100">Ask in plain language</p>
                  <p className="text-zinc-400">
                    Use natural prompts instead of manual searching.
                  </p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="h-7 w-7 shrink-0 rounded-full bg-lapis-500/15 text-lapis-400 flex items-center justify-center">
                  <CheckCircle className="h-3.5 w-3.5" />
                </div>
                <div>
                  <p className="text-zinc-100">Validate with citations</p>
                  <p className="text-zinc-400">
                    Jump straight to supporting excerpts.
                  </p>
                </div>
              </li>
            </ol>
            <p className="text-label-accent border-t border-zinc-800 pt-4">Why it works</p>
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
        </section>
      </main>
    </div>
  );
}
