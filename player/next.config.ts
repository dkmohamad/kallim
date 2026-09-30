import createMDX from "@next/mdx";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  pageExtensions: ["ts", "tsx", "md", "mdx"],
  // The site is for one learner and its URL is unlisted, so keep every page
  // and file out of search results.
  headers: async () => [
    { source: "/:path*", headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }] },
  ],
};

export default createMDX({})(nextConfig);
