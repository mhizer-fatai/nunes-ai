import "./globals.css";

export const metadata = {
  title: "Nunes AI — the memory that makes an AI team safe with money",
  description:
    "Three AI agents — Planner, Policy, Payments — share one persistent memory that refuses whatever contradicts a past decision. Real USDC on Base.",
};

/* Set the theme before first paint so there is no light/dark flash.
   Dark is the default: the receipts-style ledger look lives there. */
const THEME_INIT = `
(function(){
  try {
    var t = localStorage.getItem('nunes-theme');
    if (!t) t = 'dark';
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&family=Playfair+Display:ital,wght@0,500;0,600;1,500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
