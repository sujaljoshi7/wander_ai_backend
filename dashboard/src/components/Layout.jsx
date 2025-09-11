import Sidebar from './Sidebar.jsx';
import './layout.css';
import { Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="content">
        <header className="topbar">
          <h1>Wander AI</h1>
        </header>
        <div className="content-body">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
