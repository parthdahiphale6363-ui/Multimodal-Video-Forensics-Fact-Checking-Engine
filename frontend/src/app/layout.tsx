import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Video Forensics & OSINT Engine — AI-Powered Fact Verification",
  description: "Analyze any video URL with an 8-stage forensic pipeline: deepfake detection, OSINT intelligence, data mining, live fact-checking, and explainable AI verdicts.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
