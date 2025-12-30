/**
 * Auth pages layout - minimal wrapper for auth pages.
 *
 * This layout is used for /login and other auth pages.
 * It provides a clean, centered layout without the main app chrome.
 */

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

