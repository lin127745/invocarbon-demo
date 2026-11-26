import "./globals.css";

export const metadata = {
  title: "發票碳帳 Demo",
  description: "用電子發票與電費單，自動產出可回查的範疇一、二碳盤查",
};

export default function RootLayout({ children }) {
  return (
    <html lang="zh-Hant-TW">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap" rel="stylesheet" />
      </head>
      <body>
        <header className="topbar">
          <a href="/" className="brand">發票碳帳</a>
          <span className="demo-tag">Demo｜資料皆為虛構</span>
        </header>
        {children}
      </body>
    </html>
  );
}
