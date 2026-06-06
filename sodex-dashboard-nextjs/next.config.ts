import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.56.1', 'localhost:3000'],
  async rewrites() {
    return [
      {
        source: '/mainnet-api/:path*',
        destination: 'http://127.0.0.1:8000/:path*?network=mainnet',
      },
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
