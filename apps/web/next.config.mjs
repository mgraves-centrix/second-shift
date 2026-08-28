/** @type {import('next').NextConfig} */
const nextConfig = {
  // Static export: the capture app is served as files, by Tailscale Serve or by
  // the API itself. A second running server on the Spark is a second thing that
  // can be down at 2am when an idea arrives.
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
};
export default nextConfig;
