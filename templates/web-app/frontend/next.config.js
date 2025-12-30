/** @type {import('next').NextConfig} */
const nextConfig = {
  // Standalone output for minimal Docker image (no npm ci needed in final stage)
  // This bundles only the required node_modules into .next/standalone
  output: 'standalone',
  images: {
    unoptimized: true,
  },
  // Proxy API requests to the backend in development
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: process.env.BACKEND_URL 
          ? `${process.env.BACKEND_URL}/api/:path*`
          : 'http://localhost:8080/api/:path*',
      },
      {
        source: '/health',
        destination: process.env.BACKEND_URL 
          ? `${process.env.BACKEND_URL}/health`
          : 'http://localhost:8080/health',
      },
    ];
  },
};

module.exports = nextConfig;

