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

  function applyTheme() {
    document.documentElement.dataset.theme =
      mode === 'system' ? (systemTheme.matches ? 'dark' : 'light') : mode;
    document.querySelectorAll('[data-theme-select]').forEach((select) => {
      select.value = mode;
    });
  }

  applyTheme();
  systemTheme.addEventListener('change', applyTheme);
  window.addEventListener('storage', (event) => {
    if (event.key !== storageKey && event.key !== null) return;
    mode = modes.includes(event.newValue) ? event.newValue : 'system';
    applyTheme();
  });

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme();
    document.querySelectorAll('[data-theme-select]').forEach((select) => {
      select.addEventListener('change', () => {
        mode = modes.includes(select.value) ? select.value : 'system';
        applyTheme();
        try {
          localStorage.setItem(storageKey, mode);
        } catch {
          // Keep the chosen theme for this page even if persistence is blocked.
        }
      });
    });
  });
})();
