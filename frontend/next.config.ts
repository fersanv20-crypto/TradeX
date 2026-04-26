import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /**
   * Default `.next` output is what Vercel uses. Avoid `output: "standalone"` here unless you
   * self-host in Docker: on Windows + OneDrive, standalone trace copying often fails (ENOTEMPTY / readlink).
   */
  /** Build lint runs separately; avoid flaky build-time lint on Windows OneDrive. */
  eslint: {
    ignoreDuringBuilds: true,
  },
  async redirects() {
    return [{ source: "/backtesting", destination: "/backtest", permanent: true }];
  },
};

export default nextConfig;
