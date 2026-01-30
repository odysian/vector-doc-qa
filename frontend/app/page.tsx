/**
 * Landing page (/). Branded entry point; links to login and register.
 * Redirects to dashboard if user already has a token.
 */
"use client";

import { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (token) {
      router.replace("/dashboard");
    }
  }, [router]);

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-zinc-950 p-4">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,var(--tw-gradient-stops))] from-lapis-500/20 via-zinc-950 to-zinc-950" />

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
            className="inline-flex items-center justify-center py-3 px-8 bg-lapis-600 hover:bg-lapis-500 text-white font-medium rounded-lg transition-colors shadow-lg shadow-lapis-900/20 focus:outline-none focus:ring-2 focus:ring-lapis-500 focus:ring-offset-2 focus:ring-offset-zinc-950 cursor-pointer"
          >
            Sign In
          </Link>
          <Link
            href="/register"
            className="inline-flex items-center justify-center py-3 px-8 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 font-medium rounded-lg border border-zinc-700 transition-colors focus:outline-none focus:ring-2 focus:ring-lapis-500 focus:ring-offset-2 focus:ring-offset-zinc-950 cursor-pointer"
          >
            Register
          </Link>
        </div>
      </main>
    </div>
  );
}
