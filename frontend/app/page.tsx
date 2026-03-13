/**
 * Landing page (/). Branded entry point; links to login and register.
 * Redirects to dashboard if user already has a token.
 */
"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authService } from "@/lib/services/authService";

export default function Home() {
  const router = useRouter();
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [error, setError] = useState("");
  const primaryActionClass =
    "inline-flex items-center justify-center rounded-md border border-lapis-500 bg-lapis-600 px-8 py-3 text-base font-medium text-white transition hover:bg-lapis-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50";
  const secondaryActionClass =
    "inline-flex items-center justify-center rounded-md border border-lapis-500/40 px-8 py-3 text-base font-medium text-lapis-200 transition hover:bg-lapis-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50 disabled:cursor-not-allowed disabled:opacity-60";
  const neutralActionClass =
    "inline-flex items-center justify-center rounded-md border border-zinc-700 bg-zinc-800 px-8 py-3 text-base font-medium text-zinc-100 transition hover:bg-zinc-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50";

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
          <div className="space-y-6">
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-300 sm:text-6xl lg:text-7xl">
              Quaero
            </h1>
            <p className="max-w-xl text-2xl leading-tight text-zinc-100 sm:text-3xl">
              Ask better questions across your PDFs and get grounded answers with citations.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
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
              <Link href="/register" className={neutralActionClass}>
                Register
              </Link>
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}
          </div>

          <div className="space-y-5 rounded-xl border border-zinc-800 bg-zinc-900/70 p-6 sm:p-8">
            <p className="text-label-accent">How It Works</p>
            <ol className="space-y-4 text-sm text-zinc-300">
              <li>
                <p className="text-zinc-100">1. Upload PDFs</p>
                <p className="text-zinc-400">Ingest files once, then query them anytime.</p>
              </li>
              <li>
                <p className="text-zinc-100">2. Ask in plain language</p>
                <p className="text-zinc-400">Use natural prompts instead of manual searching.</p>
              </li>
              <li>
                <p className="text-zinc-100">3. Validate with citations</p>
                <p className="text-zinc-400">Jump straight to supporting excerpts.</p>
              </li>
            </ol>
            <ul className="space-y-2 border-t border-zinc-800 pt-4 text-sm text-zinc-300">
              <li>Cited answers only</li>
              <li>Your documents stay scoped</li>
              <li>Fast retrieval + chat workflow</li>
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}
