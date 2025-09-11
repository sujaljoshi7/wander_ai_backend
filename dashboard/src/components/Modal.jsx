import { useEffect, useRef } from 'react';

/**
 * Modal (Bootstrap) reusable component
 * Props:
 * - id: string (required)
 * - title: string
 * - children: ReactNode (modal body)
 * - footer: ReactNode (modal footer)
 * - onClose: () => void (called on hidden)
 * - centered: boolean (default true)
 * - headerGradient: boolean (apply gradient header)
 */
export default function Modal({ id, title, children, footer, onClose, centered = true, headerGradient = false }) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const handler = () => onClose && onClose();
    el.addEventListener('hidden.bs.modal', handler);
    return () => el.removeEventListener('hidden.bs.modal', handler);
  }, [onClose]);

  return (
    <div className="modal fade" id={id} tabIndex="-1" aria-hidden="true" ref={ref}>
      <div className={`modal-dialog ${centered ? 'modal-dialog-centered' : ''}`}>
        <div className="modal-content">
          <div className={`modal-header ${headerGradient ? 'header-gradient' : ''}`}>
            {title && <h5 className="modal-title">{title}</h5>}
            <button type="button" className="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div className="modal-body">{children}</div>
          {footer && <div className="modal-footer">{footer}</div>}
        </div>
      </div>
    </div>
  );
}
