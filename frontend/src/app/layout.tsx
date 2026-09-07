import type { Metadata } from "next";
import { Bricolage_Grotesque, Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/Sidebar";

const display = Bricolage_Grotesque({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
});

const sans = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Hive — AI Agent Platform",
  description: "Multi-agent orchestration platform",
};

/* Runs before first paint so a stored theme never flashes the wrong palette. */
const THEME_INIT = `(function(){try{var t=localStorage.getItem('hive-theme');if(t&&t!=='system')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
      </head>
      <body
        className={`${display.variable} ${sans.variable} ${mono.variable}`}
        style={{ margin: 0, padding: 0, WebkitFontSmoothing: "antialiased" }}
      >
        <Providers>
          <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
            <Sidebar />
            <main style={{ flex: 1, overflowY: "auto", background: "var(--c-base)" }}>
              {children}
            </main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
