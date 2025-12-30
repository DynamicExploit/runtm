import type { Metadata } from 'next';
import { Instrument_Sans, JetBrains_Mono } from 'next/font/google';
import './globals.css';

const instrumentSans = Instrument_Sans({
  subsets: ['latin'],
  variable: '--font-geist-sans',
  display: 'swap',
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-geist-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'My Landing Page',
  description: 'A beautiful landing page built with Next.js and deployed on Runtm',
  keywords: ['landing page', 'next.js', 'runtm'],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${instrumentSans.variable} ${jetBrainsMono.variable}`}>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}

