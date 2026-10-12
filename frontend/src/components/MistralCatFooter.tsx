'use client';

import React, { useEffect, useState } from 'react';

export default function MistralCatFooter() {
  const [theme, setTheme] = useState<'night' | 'day'>('night');

  useEffect(() => {
    // Check current theme
    const saved = localStorage.getItem('pixel_theme') as 'night' | 'day' | null;
    if (saved) setTheme(saved);

    const onThemeChange = (e: Event) => {
      const customEvent = e as CustomEvent<'night' | 'day'>;
      if (customEvent.detail) setTheme(customEvent.detail);
    };

    window.addEventListener('pixel-theme-change', onThemeChange);
    return () => window.removeEventListener('pixel-theme-change', onThemeChange);
  }, []);

  const toggleTheme = (newTheme: 'night' | 'day') => {
    setTheme(newTheme);
    localStorage.setItem('pixel_theme', newTheme);
    document.documentElement.setAttribute('data-theme', newTheme === 'night' ? 'dark' : 'light');
    window.dispatchEvent(new CustomEvent('pixel-theme-change', { detail: newTheme }));
  };

  return (
    <footer className="mistral-footer-root">
      <div className="mistral-nav-wrap">


        {/* ── Sub-bar: Copyright and Day/Night Pill Switch (Matches Mistral Screenshot) ── */}
        <div className="mistral-sub-bar">
          <div className="copyright-tag">
            TruthLens AI © 2026
          </div>

          <div className="footer-theme-pill">
            <button
              className={`theme-icon-btn ${theme === 'day' ? 'active' : ''}`}
              onClick={() => toggleTheme('day')}
              title="Switch to Daytime Meadow mode"
              aria-label="Switch to Daytime mode"
            >
              ☀
            </button>
            <button
              className={`theme-icon-btn ${theme === 'night' ? 'active' : ''}`}
              onClick={() => toggleTheme('night')}
              title="Switch to Starry Midnight mode"
              aria-label="Switch to Night mode"
            >
              ☾
            </button>
          </div>
        </div>
      </div>

      <style jsx>{`
        .mistral-footer-root {
          width: 100%;
          background: rgba(15, 23, 42, 0.85);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          color: var(--text-primary);
          position: relative;
          border-top: 1px solid var(--border);
          font-family: 'Inter', sans-serif;
          margin-top: 2.5rem;
          padding-bottom: 70px; /* Space for the walking cat meadow at the bottom */
          z-index: 2;
          transition: background 0.3s ease;
        }

        :global([data-theme='light']) .mistral-footer-root {
          background: rgba(255, 255, 255, 0.90);
        }

        .mistral-nav-wrap {
          max-width: 1200px;
          margin: 0 auto;
          padding: 1.25rem 2rem;
        }

        .mistral-sub-bar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 1.25rem;
        }

        .copyright-tag {
          font-size: 0.80rem;
          color: var(--text-muted);
          font-weight: 500;
        }

        .footer-theme-pill {
          display: inline-flex;
          align-items: center;
          background: rgba(255, 255, 255, 0.08);
          border: 1px solid var(--border);
          border-radius: 99px;
          padding: 0.22rem;
          gap: 0.2rem;
        }

        :global([data-theme='light']) .footer-theme-pill {
          background: rgba(0, 0, 0, 0.05);
        }

        .theme-icon-btn {
          background: transparent;
          border: none;
          color: var(--text-muted);
          width: 30px;
          height: 28px;
          border-radius: 99px;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.88rem;
          transition: all 0.2s ease;
        }

        .theme-icon-btn.active {
          background: var(--accent);
          color: #ffffff;
          box-shadow: 0 2px 8px var(--accent-glow);
        }
      `}</style>
    </footer>
  );
}
