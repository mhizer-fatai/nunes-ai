/** @type {import('next').NextConfig} */
const nextConfig = {
  // The Python agent backend serves the JSON API; the Next.js app proxies
  // /api/* to it so the browser never deals with CORS or ports.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8080/api/:path*" },
    ];
  },
};

module.exports = nextConfig;
