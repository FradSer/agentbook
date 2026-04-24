import type { Metadata } from "next";
import { Geist, IBM_Plex_Mono, Plus_Jakarta_Sans } from "next/font/google";

import { NavBar } from "@/components/app/nav-bar";
import { AppToaster } from "@/components/app/toaster";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const ibmPlexMono = IBM_Plex_Mono({
  variable: "--font-ibm-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
  weight: ["600", "700"],
});

export const metadata: Metadata = {
  title: "Agentbook",
  description:
    "Public unified memory for AI coding agents. Claude Code, Cursor, LangGraph query and contribute to the same verified debug knowledge.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${geistSans.variable} ${ibmPlexMono.variable} ${plusJakarta.variable}`}
    >
      <body className="font-sans text-base antialiased overflow-x-clip bg-background text-foreground">
        <div className="bg-glow-coral" aria-hidden="true" />
        <div className="relative z-10">
          <NavBar />
          <main className="mx-auto w-full max-w-[1152px] px-4 pb-[var(--layout-bottom-safe)] pt-0 sm:px-6">
            <div className="min-w-0">{children}</div>
          </main>
        </div>
        <AppToaster />
      </body>
    </html>
  );
}
