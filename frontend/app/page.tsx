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
    <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 p-4">
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <main className="relative w-full max-w-lg text-center">
        <h1 className="text-6xl sm:text-7xl font-bold font-cormorant italic text-lapis-400 mb-3">
          Quaero
        </h1>
        <p className="text-zinc-400 text-lg mb-10">
          Document Intelligence
        </p>
        <p className="text-zinc-500 text-sm max-w-md mx-auto mb-12">
          Upload PDFs, ask questions, and get answers grounded in your documents.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link
            href="/login"
            className="ui-btn ui-btn-primary ui-btn-lg"
          >
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
          <Link
            href="/register"
            className="ui-btn ui-btn-neutral ui-btn-lg"
          >
            Register
          </Link>
        </div>
        {error && <p className="mt-4 text-sm text-red-400">{error}</p>}
      </main>
    </div>
  );
}
