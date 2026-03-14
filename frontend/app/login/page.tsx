/**
 * Login page: username/password form. On success, stores token and redirects to dashboard.
 */
"use client";

import { useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Check } from "lucide-react";
import { authService } from "@/lib/services/authService";

/**
 * Renders centered login form. Submits via auth service and redirects to
 * /dashboard. Link to register for new users.
 */
export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const inputClass =
    "w-full rounded-md border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50";
  const primaryButtonClass =
    "inline-flex w-full items-center justify-center rounded-md border border-lapis-500 bg-lapis-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-lapis-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50 disabled:cursor-not-allowed disabled:opacity-60";
  const secondaryButtonClass =
    "inline-flex w-full items-center justify-center rounded-md border border-lapis-500/40 px-4 py-2.5 text-sm font-medium text-lapis-200 transition hover:bg-lapis-500/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50 disabled:cursor-not-allowed disabled:opacity-60";

  const submitLogin = async (nextUsername: string, nextPassword: string) => {
    setError("");
    setLoading(true);

    try {
      await authService.login({
        username: nextUsername,
        password: nextPassword,
      });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault();
    await submitLogin(username, password);
  };

  const handleTryDemo = async () => {
    setUsername("demo");
    setPassword("demo");
    setError("");
    setLoading(true);

    try {
      await authService.loginDemo();
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 p-4 sm:p-6">
      <div className="absolute inset-0 quaero-bg-grid" aria-hidden />
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <main className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-5xl items-center py-6 sm:py-8">
        <section className="grid w-full items-center gap-8 lg:grid-cols-[1fr_0.95fr] lg:gap-10">
          <h1 className="lg:hidden font-cormorant text-5xl font-bold italic text-lapis-300 text-center pb-2">
            Quaero
          </h1>

          <div className="hidden lg:block w-full space-y-5">
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-300 sm:text-6xl pb-2">
              Quaero
            </h1>
            <p className="mt-2 text-sm text-zinc-400">
              Document intelligence for serious researchers.
            </p>
            <ul className="mt-6 space-y-3 list-none">
              {[
                "Upload once, query forever",
                "Answers grounded in your sources",
                "Cite the exact passage",
              ].map((feature) => (
                <li key={feature} className="flex items-center gap-2 text-sm text-zinc-300">
                  <Check className="h-3.5 w-3.5 shrink-0 text-lapis-400" />
                  {feature}
                </li>
              ))}
            </ul>
          </div>

          <div className="w-full max-w-md mx-auto rounded-xl border border-zinc-800 bg-zinc-900/70 p-8 lg:max-w-none lg:mx-0">
            <div className="mb-6">
              <p className="text-zinc-100 text-xl font-semibold">Sign In</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="ui-alert-error text-sm">
                  {error}
                </div>
              )}

              <div>
                <label
                  htmlFor="username"
                  className="block text-sm font-medium text-zinc-300 mb-2"
                >
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={inputClass}
                  placeholder="Enter your username"
                />
              </div>

              <div>
                <label
                  htmlFor="password"
                  className="block text-sm font-medium text-zinc-300 mb-2"
                >
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                  placeholder="Enter your password"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className={primaryButtonClass}
              >
                {loading ? "Accessing..." : "Sign In"}
              </button>

              <button
                type="button"
                onClick={handleTryDemo}
                disabled={loading}
                className={secondaryButtonClass}
              >
                Try Demo
              </button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-zinc-400 text-sm">
                Don&apos;t have access?{" "}
                <Link
                  href="/register"
                  className="text-lapis-400 hover:text-lapis-300 transition-colors cursor-pointer"
                >
                  Register
                </Link>
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
