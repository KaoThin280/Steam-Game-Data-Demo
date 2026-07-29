/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    typedRoutes: false,
  },

  /**
   * Proxy /api/v1/* requests to the backend.
   *
   * In local development, this rewrites API calls to the FastAPI server
   * running on port 8000. On Vercel, you can override this via
   * VERCEL_REWRITE_TARGET environment variable, or point to your deployed
   * backend URL.
   */
  async rewrites() {
    const target =
      process.env.NEXT_PUBLIC_API_PROXY_TARGET ||
      "http://localhost:8000";

    return [
      {
        source: "/api/v1/:path*",
        destination: `${target}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
