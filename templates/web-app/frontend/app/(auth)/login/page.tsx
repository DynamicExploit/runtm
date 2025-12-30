/**
 * Login page - basic scaffolding for authentication.
 *
 * This page provides email/password login with optional social providers.
 * Replace with your own design as needed.
 *
 * This page is ONLY used when features.auth is enabled.
 */

import { LoginForm, SocialButtons } from "@/components/auth";

export default function LoginPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-2xl shadow-lg p-8">
          {/* Header */}
          <div className="text-center mb-8">
            <h1 className="text-2xl font-bold text-gray-900">Welcome back</h1>
            <p className="text-gray-600 mt-2">Sign in to your account</p>
          </div>

          {/* Social login buttons */}
          <div className="mb-6">
            <SocialButtons />
          </div>

          {/* Divider */}
          <div className="relative mb-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-500">
                or continue with email
              </span>
            </div>
          </div>

          {/* Email/password form */}
          <div className="flex justify-center">
            <LoginForm allowSignup={true} />
          </div>
        </div>

        {/* Footer */}
        <p className="text-center text-sm text-gray-500 mt-6">
          By signing in, you agree to our Terms of Service and Privacy Policy.
        </p>
      </div>
    </main>
  );
}

