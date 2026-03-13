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

      <main className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-6xl items-center py-8 sm:py-12">
        <section className="grid w-full gap-8 lg:grid-cols-[1.1fr_0.9fr] lg:gap-10">
          <div className="space-y-6">
            <p className="text-label-accent">Document Q&amp;A Workspace</p>
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-300 sm:text-6xl lg:text-7xl">
              Quaero
            </h1>
            <p className="max-w-xl text-2xl leading-tight text-zinc-100 sm:text-3xl">
              Ask better questions across your PDFs and get grounded answers with citations.
            </p>
            <p className="max-w-xl text-base text-zinc-400">
              Upload documents, retrieve precise context, and move from scattered files to verifiable answers in one place.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
              <Link href="/login" className="ui-btn ui-btn-primary ui-btn-lg">
                Sign In
              </Link>
              <button
                type="button"
                onClick={handleTryDemo}
                disabled={loadingDemo}
                className="ui-btn ui-btn-secondary ui-btn-lg"
              >
                {loadingDemo ? "Accessing..." : "Try Demo"}
              </button>
              <Link href="/register" className="ui-btn ui-btn-neutral ui-btn-lg">
                Register
              </Link>
            </div>
            {error && <p className="text-sm text-red-400">{error}</p>}

            <ul className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-3">
              <li className="ui-panel px-3 py-2">Cited answers only</li>
              <li className="ui-panel px-3 py-2">Your documents stay scoped</li>
              <li className="ui-panel px-3 py-2">Fast retrieval + chat workflow</li>
            </ul>
          </div>

          <div className="ui-panel space-y-5 p-6 sm:p-8">
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

            <div className="rounded-lg border border-zinc-800 bg-zinc-900/70 p-4 text-sm">
              <p className="mb-2 text-zinc-100">Preview</p>
              <p className="text-zinc-400">
                &quot;What are the termination clauses in our vendor agreement?&quot;
              </p>
              <p className="mt-3 rounded-md border border-lapis-900/60 bg-lapis-950/30 px-3 py-2 text-zinc-200">
                Clauses 4.2 and 9.1 allow termination for breach with 30-day cure period.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
