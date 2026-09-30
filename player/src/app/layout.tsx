import type { Metadata } from "next";
import { Geist, Noto_Naskh_Arabic } from "next/font/google";
import "./globals.css";

const sans = Geist({ variable: "--font-sans-latin", subsets: ["latin"] });
const arabic = Noto_Naskh_Arabic({ variable: "--font-naskh", subsets: ["arabic"] });

export const metadata: Metadata = {
  title: { default: "Kallim", template: "%s · Kallim" },
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${sans.variable} ${arabic.variable} h-full antialiased`}>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
