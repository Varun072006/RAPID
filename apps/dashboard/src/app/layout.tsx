import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAPID | Autonomous Payment Recovery Decision Engine",
  description: "Razorpay AI Buildathon 2026 — Track 03: AI Revenue Recovery",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased selection:bg-indigo-500 selection:text-white">
        {children}
      </body>
    </html>
  );
}
