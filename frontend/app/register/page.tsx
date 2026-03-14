/**
 * Register page: sign-up form (username, email, password). Creates account then
 * auto-logs in and redirects to dashboard.
 */
"use client";

import { useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Check } from "lucide-react";
import { authService } from "@/lib/services/authService";

/**
 * Renders centered registration form. On submit: register + auto-login via
 * auth service, then redirect. Link to login for existing users.
 */
export default function RegisterPage() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const inputClass =
    "w-full rounded-md border border-zinc-700 bg-zinc-950 px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50";
  const primaryButtonClass =
    "inline-flex w-full items-center justify-center rounded-md border border-lapis-500 bg-lapis-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-lapis-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lapis-400/50 disabled:cursor-not-allowed disabled:opacity-60";

  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      await authService.registerAndLogin({ username, email, password });
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
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
          <h1 className="lg:hidden font-cormorant text-5xl font-bold italic text-lapis-400 text-center pb-2">
            Quaero
          </h1>

          <div className="hidden lg:block w-full space-y-5">
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-400 sm:text-6xl pb-2">
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
              <p className="text-zinc-100 text-xl font-semibold">Register</p>
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
                  minLength={3}
                  maxLength={50}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={inputClass}
                  placeholder="Choose a username"
                />
              </div>

              <div>
                <label
                  htmlFor="email"
                  className="block text-sm font-medium text-zinc-300 mb-2"
                >
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                  placeholder="your@email.com"
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
                  minLength={8}
                  maxLength={100}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                  placeholder="At least 8 characters"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className={primaryButtonClass}
              >
                {loading ? "Creating account..." : "Register"}
              </button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-zinc-400 text-sm">
                Already have an account?{" "}
                <Link
                  href="/login"
                  className="text-lapis-400 hover:text-lapis-300 transition-colors cursor-pointer"
                >
                  Sign in
                </Link>
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
