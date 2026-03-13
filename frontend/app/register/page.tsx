/**
 * Register page: sign-up form (username, email, password). Creates account then
 * auto-logs in and redirects to dashboard.
 */
"use client";

import { useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <main className="relative mx-auto flex min-h-[calc(100vh-2rem)] w-full max-w-5xl items-center py-8 sm:py-12">
        <section className="grid w-full gap-8 lg:grid-cols-[1fr_0.95fr] lg:gap-10">
          <div className="space-y-5 self-center">
            <p className="text-label-accent">New Workspace</p>
            <h1 className="font-cormorant text-5xl font-bold italic text-lapis-300 sm:text-6xl">
              Quaero
            </h1>
            <p className="max-w-md text-2xl leading-tight text-zinc-100">
              Create an account and start asking better questions across your PDFs.
            </p>
            <p className="max-w-md text-sm text-zinc-400">
              Registration keeps auth flow unchanged while giving you a personal document and citation workspace.
            </p>
            <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 px-4 py-3 text-sm text-zinc-300">
              Existing user? <span className="text-zinc-100">Sign In</span> is the primary return path.
            </div>
          </div>

          <div className="ui-panel p-8">
            <div className="mb-6">
              <p className="text-zinc-100 text-xl font-semibold">Register</p>
              <p className="mt-2 text-sm text-zinc-400">Set up credentials and continue to your dashboard.</p>
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
                  className="ui-input"
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
                  className="ui-input"
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
                  className="ui-input"
                  placeholder="At least 8 characters"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="ui-btn ui-btn-primary ui-btn-md ui-btn-block"
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
