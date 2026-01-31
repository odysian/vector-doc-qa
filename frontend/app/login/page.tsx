/**
 * Login page: username/password form. On success, stores token and redirects to dashboard.
 */
"use client";

import { useState, type SyntheticEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";

/**
 * Renders centered login form. Submits to api.login, saves access_token to
 * localStorage, then redirects to /dashboard. Link to register for new users.
 */
export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleSubmit = async (e: SyntheticEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await api.login({ username, password });

      localStorage.setItem("token", response.access_token);

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
        <div className="bg-zinc-900 border border-zinc-800 rounded-lg p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-900/20 border border-red-900/50 text-red-400 p-3 rounded text-sm">
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
                className="w-full px-4 py-3 bg-zinc-950 border border-zinc-700 rounded-lg text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-lapis-500/50 focus:border-lapis-500 transition-all"
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
                className="w-full px-4 py-3 bg-zinc-950 border border-zinc-700 rounded-lg text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-lapis-500/50 focus:border-lapis-500 transition-all"
                placeholder="Enter your password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-lapis-600 hover:bg-lapis-500 disabled:bg-lapis-800 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors shadow-lg shadow-lapis-900/20 cursor-pointer"
            >
              {loading ? "Accessing..." : "Sign In"}
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
