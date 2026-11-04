'use strict';

(() => {
  const storageKey = 'olivos.webui.theme';
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
  const modes = ['system', 'light', 'dark'];
  let mode = 'system';

  try {
    const saved = localStorage.getItem(storageKey);
    if (modes.includes(saved)) mode = saved;
  } catch {
    // Theme switching still works when browser storage is unavailable.
  }

  function effectiveTheme() {
    return mode === 'system' ? (systemTheme.matches ? 'dark' : 'light') : mode;
  }

  function applyTheme() {
    const theme = effectiveTheme();
    const dark = theme === 'dark';
    const label = dark ? '深色模式' : '浅色模式';
    const target = dark ? '浅色' : '深色';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.setAttribute('aria-pressed', String(dark));
      button.setAttribute('aria-label', `切换到${target}模式`);
      button.title = `切换到${target}模式`;
      const text = button.querySelector('[data-theme-label]');
      if (text) text.textContent = label;
    });
  }

  function toggleTheme() {
    mode = effectiveTheme() === 'dark' ? 'light' : 'dark';
    applyTheme();
    try {
      localStorage.setItem(storageKey, mode);
    } catch {
      // Keep the chosen theme for this page even if persistence is blocked.
    }
  }

  applyTheme();
  systemTheme.addEventListener('change', () => {
    if (mode === 'system') applyTheme();
  });
  window.addEventListener('storage', (event) => {
    if (event.key !== storageKey && event.key !== null) return;
    mode = modes.includes(event.newValue) ? event.newValue : 'system';
    applyTheme();
  });

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme();
    document.querySelectorAll('[data-theme-toggle]').forEach((button) => {
      button.addEventListener('click', toggleTheme);
    });
  });
})();
