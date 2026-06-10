import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MenuScan Dashboard",
  description: "Управление цифровым меню",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
