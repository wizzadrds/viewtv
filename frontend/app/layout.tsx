import type { Metadata, Viewport } from "next";
import "./globals.css";
import AppUpdateMonitor from "@/components/app-update-monitor";

export const metadata: Metadata = {
  title: "VIEWTV",
  description: "Tu biblioteca multimedia en casa.",
  applicationName: "VIEWTV",
  manifest: "/manifest.webmanifest",
};

export const viewport: Viewport = {
  themeColor: "#090b12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="es">
      <body>
        <AppUpdateMonitor />
        {children}
      </body>
    </html>
  );
}
