import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "VIEWTV",
    short_name: "VIEWTV",
    description: "Tu biblioteca multimedia en casa",
    start_url: "/",
    display: "standalone",
    background_color: "#090b12",
    theme_color: "#090b12",
    orientation: "landscape",
    icons: [{ src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" }],
  };
}
