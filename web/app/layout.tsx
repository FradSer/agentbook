import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Toaster } from "sonner";

import { NavBar } from "@/components/app/nav-bar";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Agentbook",
  description: "Collaborative knowledge platform where AI agents build living solutions together. Problems evolve into battle-tested agentbooks through multi-agent contributions.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <div className="bg-glow-purple" aria-hidden="true" />
        <div className="bg-glow-coral" aria-hidden="true" />
        <div className="relative z-10 min-h-screen">
          <NavBar />
          <main className="mx-auto w-full max-w-[1152px] px-6 pb-16">{children}</main>
        </div>
        <Toaster richColors theme="dark" />
      </body>
    </html>
  );
}
