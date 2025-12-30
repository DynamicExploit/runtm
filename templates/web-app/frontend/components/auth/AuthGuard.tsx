/**
 * Auth guard component - protects routes that require authentication.
 * This is scaffolding, not a production UI.
 */
"use client";

import { useSession } from "@/lib/auth-client";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

interface AuthGuardProps {
  children: React.ReactNode;
  /** Where to redirect if not authenticated */
  redirectTo?: string;
  /** Show loading state while checking auth */
  loadingComponent?: React.ReactNode;
}

export function AuthGuard({
  children,
  redirectTo = "/login",
  loadingComponent,
}: AuthGuardProps) {
  const { data: session, isPending } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (!isPending && !session?.user) {
      router.push(redirectTo);
    }
  }, [session, isPending, router, redirectTo]);

  // Still loading
  if (isPending) {
    return (
      loadingComponent || (
        <div className="flex items-center justify-center min-h-[200px]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
        </div>
      )
    );
  }

  // Not authenticated
  if (!session?.user) {
    return null;
  }

  // Authenticated
  return <>{children}</>;
}

