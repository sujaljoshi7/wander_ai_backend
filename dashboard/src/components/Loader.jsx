export default function Loader({ visible, text = 'Loading...' }) {
  if (!visible) return null;
  return (
    <div className="position-fixed top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center" style={{ zIndex: 2000, background: 'rgba(0,0,0,0.15)' }}>
      <div className="d-flex flex-column align-items-center gap-2 bg-white p-3 rounded shadow-sm">
        <div className="spinner-border text-primary" role="status" aria-hidden="true"></div>
        <div className="small text-muted">{text}</div>
      </div>
    </div>
  );
}
