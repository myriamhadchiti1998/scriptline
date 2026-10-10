import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Scriptline — ideation & scripting pipeline",
  description: "AI ideation → ICE scoring → human approval → scripting → quality gate → delivery",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
