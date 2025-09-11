import { useRef, useEffect } from 'react';
import Modal from './Modal.jsx';

/**
 * ConfirmDialog - reusable confirmation modal built on top of Modal.jsx
 * Props:
 * - id: string (required, must be unique on page)
 * - title: string
 * - message: string | ReactNode
 * - confirmText?: string (default 'Confirm')
 * - cancelText?: string (default 'Cancel')
 * - onConfirm: () => void
 * - onCancel?: () => void
 * - variant?: 'danger' | 'success' | 'warning' (controls accent + confirm button)
 */
export default function ConfirmDialog({
  id,
  title = 'Confirm',
  message = 'Are you sure?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'danger',
}) {
  const modalRef = useRef(null);

  // Expose a show() helper via window for imperative usage if desired
  useEffect(() => {
    if (!id) return;
    const el = document.getElementById(id);
    if (!el) return;
    modalRef.current = el;
  }, [id]);

  const handleConfirm = () => {
    try { onConfirm && onConfirm(); } finally {
      // Close modal after confirm
      if (modalRef.current) {
        const instance = window.bootstrap?.Modal.getInstance(modalRef.current) || new window.bootstrap.Modal(modalRef.current);
        instance.hide();
      }
    }
  };

  const handleCancel = () => {
    onCancel && onCancel();
  };

  const confirmBtnClass = variant === 'success'
    ? 'btn btn-success'
    : variant === 'warning'
    ? 'btn btn-warning'
    : 'btn btn-danger';

  // subtle colored accent box for different variants
  const accentStyles = variant === 'success'
    ? { background: 'rgba(16,185,129,0.12)', border: '1px solid rgba(16,185,129,0.35)' }
    : variant === 'warning'
    ? { background: 'rgba(245,158,11,0.12)', border: '1px solid rgba(245,158,11,0.35)' }
    : { background: 'rgba(239,68,68,0.12)', border: '1px solid rgba(239,68,68,0.35)' };

  const accentDot = variant === 'success' ? '#10b981' : variant === 'warning' ? '#f59e0b' : '#ef4444';

  return (
    <Modal
      id={id}
      title={title}
      headerGradient
      onClose={onCancel}
      footer={(
        <>
          <button type="button" className="btn btn-secondary" data-bs-dismiss="modal" onClick={handleCancel}>{cancelText}</button>
          <button type="button" className={confirmBtnClass} onClick={handleConfirm}>{confirmText}</button>
        </>
      )}
    >
      <div className="p-3 rounded" style={{ ...accentStyles }}>
        <div className="d-flex align-items-start gap-2">
          <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: accentDot, marginTop: 6 }} />
          <div className="flex-grow-1">
            {typeof message === 'string' ? <p className="mb-0">{message}</p> : message}
          </div>
        </div>
      </div>
    </Modal>
  );
}
