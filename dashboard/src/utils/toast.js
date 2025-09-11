// Lightweight toast utility without external deps.
// Usage: import { showToast } from '../utils/toast'; showToast('Saved', 'success');

const ensureContainer = () => {
  let container = document.getElementById('app-toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'app-toast-container';
    Object.assign(container.style, {
      position: 'fixed',
      top: '16px',
      right: '16px',
      zIndex: 1080,
      display: 'flex',
      flexDirection: 'column',
      gap: '8px',
      pointerEvents: 'none',
    });
    document.body.appendChild(container);
  }
  return container;
};

export function showToast(message, variant = 'success', timeout = 3000) {
  const container = ensureContainer();
  const el = document.createElement('div');

  const bg = variant === 'success'
    ? 'linear-gradient(135deg,#16a34a,#22c55e,#4ade80)'
    : variant === 'error'
    ? 'linear-gradient(135deg,#b91c1c,#ef4444,#f87171)'
    : 'linear-gradient(135deg,#92400e,#f59e0b,#fbbf24)';

  Object.assign(el.style, {
    background: bg,
    color: '#fff',
    padding: '10px 14px',
    borderRadius: '10px',
    boxShadow: '0 10px 20px rgba(0,0,0,0.15)',
    pointerEvents: 'auto',
    minWidth: '220px',
    maxWidth: '420px',
    fontSize: '0.95rem',
  });
  el.textContent = message || (variant === 'success' ? 'Success' : 'Something went wrong');

  container.appendChild(el);

  window.setTimeout(() => {
    el.style.transition = 'opacity 200ms ease';
    el.style.opacity = '0';
    window.setTimeout(() => {
      container.removeChild(el);
      if (!container.childElementCount) container.remove();
    }, 220);
  }, timeout);
}
