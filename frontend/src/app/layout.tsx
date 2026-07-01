import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Distributed Chat Application',
  description:
    'A horizontally scalable, real-time messaging platform built with Next.js, FastAPI, PostgreSQL, and Redis.',
  keywords: ['chat', 'real-time', 'distributed', 'websocket', 'messaging'],
  authors: [{ name: 'Kota Manohar' }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
