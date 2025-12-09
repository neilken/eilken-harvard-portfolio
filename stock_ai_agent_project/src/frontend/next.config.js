/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',  // ← ADD THIS LINE
    reactStrictMode: true,  // Keep only one
    webpack: (config) => {
        config.module.rules.push({
            test: /\.svg$/,
            use: ["@svgr/webpack"]
        });
        return config;
    },
};

module.exports = nextConfig;