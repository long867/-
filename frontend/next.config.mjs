/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  poweredByHeader: false,
  webpack(config, { isServer, dev }) {
    if (!isServer && !dev && config.optimization.splitChunks) {
      // Share one state engine instead of requesting several small query chunks.
      // Route-specific chart, map and dialog chunks retain their lazy boundaries.
      config.optimization.splitChunks.cacheGroups.miningQuery = {
        test: /[\\/]node_modules[\\/]@tanstack[\\/]/,
        name: "mining-query",
        chunks: "all",
        priority: 45,
        enforce: true,
      };
    }
    return config;
  },
  async rewrites() {
    return [
      {
        source: "/api-docs",
        destination: `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8001"}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8001"}/openapi.json`,
      },
      {
        source: "/api/:path*",
        destination: `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8001"}/api/:path*`,
      },
    ];
  },
};
export default nextConfig;
