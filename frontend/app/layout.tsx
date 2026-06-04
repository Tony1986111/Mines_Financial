import type { Metadata } from "next";
import { Syne, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const syne = Syne({
  subsets: ["latin"],
  variable: "--font-syne",
  weight: ["400", "500", "600", "700", "800"],
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: "ASX Mining Financial Chatbot",
  description: "Chat with ASX mining company annual reports",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {/* Prevent theme flash on load */}
        <script dangerouslySetInnerHTML={{ __html: `
          (function(){var t=localStorage.getItem('theme')||'dark';
          document.documentElement.classList.toggle('dark',t==='dark')})()
        `}} />
      </head>
      <body className={`${syne.variable} ${jetbrainsMono.variable} font-sans bg-[#eef4fb] dark:bg-[#060c14] text-[#0d1e38] dark:text-[#dce8f8] antialiased`}>
        {children}
      </body>
    </html>
  );
}
