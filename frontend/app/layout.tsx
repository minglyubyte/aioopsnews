import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI Reality Check",
  description: "Bootstrap scaffold for the AI Reality Check MVP.",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: Readonly<RootLayoutProps>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
