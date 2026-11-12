import type { Metadata, Viewport } from "next";
import { Toaster } from "react-hot-toast";
import AppShell from "@/components/shell/AppShell";
import { asset } from "@/lib/config";
import "../styles/globals.css";

const site = process.env.NEXT_PUBLIC_SITE_URL;
const description =
  "Read lung CT slices with a ResNet-50 and Grad-CAM, in a radiology-style worklist and viewer. " +
  "The live demo runs the model in your browser: scans never leave the page.";

export const metadata: Metadata = {
  title: { default: "LungScan", template: "%s · LungScan" },
  description,
  metadataBase: site ? new URL(site) : undefined,
  icons: { icon: asset("favicon.svg") },
  openGraph: site
    ? {
        type: "website",
        siteName: "LungScan",
        title: "LungScan · lung CT reading, on your own device",
        description,
        url: site,
        images: [{ url: `${site}/social.png`, width: 1200, height: 630, alt: "LungScan" }],
      }
    : undefined,
  twitter: site ? { card: "summary_large_image" } : undefined,
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#080b0f" },
    { media: "(prefers-color-scheme: light)", color: "#f1f4f8" },
  ],
};

// Applies the saved theme before the first paint, so the page never flashes the wrong one.
const themeScript = `try{var t=localStorage.getItem("lungscan-theme");if(!t)t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark";document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <AppShell>{children}</AppShell>
        <Toaster
          position="bottom-right"
          toastOptions={{
            className:
              "!rounded-xl !border !border-line !bg-raised !text-ink !shadow-pop !text-[13px]",
            success: {
              iconTheme: { primary: "rgb(var(--clear))", secondary: "rgb(var(--raised))" },
            },
            error: { iconTheme: { primary: "rgb(var(--flag))", secondary: "rgb(var(--raised))" } },
          }}
        />
      </body>
    </html>
  );
}
