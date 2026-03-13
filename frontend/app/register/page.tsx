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
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4">
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <div className="relative w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-6xl font-bold font-cormorant italic text-lapis-400 mb-2">
            Quaero
          </h1>
          <p className="text-zinc-400 text-sm mt-3">Create your account</p>
        </div>

        {/* Form Card */}
        <div className="ui-panel p-8">
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
      </div>
    </div>
  );
}
