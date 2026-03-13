/**
 * Login page: username/password form. On success, stores token and redirects to dashboard.
 */
"use client";

import { useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
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
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4">
      <div className="absolute inset-0 quaero-gradient-overlay" aria-hidden />

      <div className="relative w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-6xl font-bold font-cormorant italic text-lapis-400 mb-2">
            Quaero
          </h1>
          <p className="text-zinc-400 text-sm mt-3">Document Intelligence</p>
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
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="ui-input"
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
                className="ui-input"
                placeholder="Enter your password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="ui-btn ui-btn-primary ui-btn-md ui-btn-block"
            >
              {loading ? "Accessing..." : "Sign In"}
            </button>

            <button
              type="button"
              onClick={handleTryDemo}
              disabled={loading}
              className="ui-btn ui-btn-secondary ui-btn-md ui-btn-block"
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
      </div>
    </div>
  );
}
