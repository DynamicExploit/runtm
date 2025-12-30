/**
 * Magic link / passwordless login form.
 * This is scaffolding, not a production UI.
 */
"use client";

import { useState } from "react";

interface MagicLinkFormProps {
  /** Called after magic link is sent */
  onSent?: () => void;
}

export function MagicLinkForm({ onSent }: MagicLinkFormProps) {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      // Note: Magic link requires email service configuration
      // In development, the link is logged to console
      const response = await fetch("/api/auth/magic-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!response.ok) {
        throw new Error("Failed to send magic link");
      }

      setSent(true);
      if (onSent) {
        onSent();
      }
    } catch (err: any) {
      setError(err?.message || "Failed to send magic link");
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <div className="text-center p-6 bg-green-50 rounded-lg">
        <h3 className="font-medium text-green-800 mb-2">Check your email</h3>
        <p className="text-sm text-green-600">
          We sent a magic link to <strong>{email}</strong>
        </p>
        <button
          onClick={() => setSent(false)}
          className="mt-4 text-sm text-blue-600 hover:underline"
        >
          Use a different email
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-sm">
      <div>
        <label htmlFor="magic-email" className="block text-sm font-medium mb-1">
          Email
        </label>
        <input
          id="magic-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {error && (
        <p className="text-red-500 text-sm bg-red-50 p-2 rounded">{error}</p>
      )}

      <button
        type="submit"
        disabled={loading}
        className="w-full p-3 bg-black text-white rounded-lg font-medium hover:bg-gray-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? "Sending..." : "Send Magic Link"}
      </button>

      <p className="text-center text-xs text-gray-500">
        No password required. We&apos;ll email you a secure login link.
      </p>
    </form>
  );
}

