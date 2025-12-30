/**
 * Basic login form - replace with your own design.
 * This is scaffolding, not a production UI.
 */
"use client";

import { useState } from "react";
import { signIn, signUp } from "@/lib/auth-client";

interface LoginFormProps {
  /** Called on successful authentication */
  onSuccess?: () => void;
  /** Show signup option */
  allowSignup?: boolean;
}

export function LoginForm({ onSuccess, allowSignup = true }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [isSignup, setIsSignup] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      if (isSignup) {
        await signUp.email({
          email,
          password,
          name: name || email.split("@")[0],
        });
      } else {
        await signIn.email({ email, password });
      }

      if (onSuccess) {
        onSuccess();
      } else {
        window.location.href = "/";
      }
    } catch (err: any) {
      setError(err?.message || (isSignup ? "Signup failed" : "Invalid credentials"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 w-full max-w-sm">
      {isSignup && (
        <div>
          <label htmlFor="name" className="block text-sm font-medium mb-1">
            Name
          </label>
          <input
            id="name"
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Your name"
            className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
      )}

      <div>
        <label htmlFor="email" className="block text-sm font-medium mb-1">
          Email
        </label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          required
          className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      <div>
        <label htmlFor="password" className="block text-sm font-medium mb-1">
          Password
        </label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="••••••••"
          required
          minLength={8}
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
        {loading ? "..." : isSignup ? "Create Account" : "Sign In"}
      </button>

      {allowSignup && (
        <p className="text-center text-sm text-gray-600">
          {isSignup ? "Already have an account?" : "Don't have an account?"}{" "}
          <button
            type="button"
            onClick={() => {
              setIsSignup(!isSignup);
              setError("");
            }}
            className="text-blue-600 hover:underline font-medium"
          >
            {isSignup ? "Sign in" : "Sign up"}
          </button>
        </p>
      )}
    </form>
  );
}

