import "./globals.css";

export const metadata = {
  title: "OSS Copilot",
  description: "PR review and open-source contribution matching agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
