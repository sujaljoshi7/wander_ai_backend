import { NavLink, useLocation } from 'react-router-dom';
import { useState } from 'react';
import './sidebar.css';

// Independent top-level links (no dropdown)
const flatLinks = [
  { label: 'Dashboard', to: '/' },
  { label: 'Place', to: '/place' },
  { label: 'Restaurant', to: '/restaurant' },
  { label: 'Food', to: '/food' },
  { label: 'Hotel', to: '/hotel' },
  { label: 'Itinerary', to: '/itineraries' },
];

// Single dropdown section: Master
const masterSection = {
  title: 'Master',
  items: [
    { label: 'City', to: '/city' },
    { label: 'State', to: '/state' },
    { label: 'Country', to: '/country' },
  ],
};

export default function Sidebar() {
  const location = useLocation();
  const [open, setOpen] = useState({ Master: true });

  const toggle = (key) => setOpen((s) => ({ ...s, [key]: !s[key] }));

  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="logo">🧭</span>
        <span>Wander AI</span>
      </div>
      <nav className="nav">
        {/* Dashboard first */}
        <ul className="menu">
          {flatLinks
            .filter((l) => l.to === '/')
            .map((it) => (
              <li key={it.to}>
                <NavLink
                  to={it.to}
                  className={({ isActive }) =>
                    'link' + (isActive || location.pathname === it.to ? ' active' : '')
                  }
                  end
                >
                  {it.label}
                </NavLink>
              </li>
            ))}
        </ul>

        {/* Master second */}
        <div className="section">
          <button
            className="section-header"
            onClick={() => toggle(masterSection.title)}
            aria-expanded={open[masterSection.title]}
          >
            <span>{masterSection.title}</span>
            <span className={`chev ${open[masterSection.title] ? 'rot' : ''}`}>▾</span>
          </button>
          {open[masterSection.title] && (
            <ul className="menu">
              {masterSection.items.map((it) => (
                <li key={it.to}>
                  <NavLink
                    to={it.to}
                    className={({ isActive }) =>
                      'link' + (isActive || location.pathname === it.to ? ' active' : '')
                    }
                    end
                  >
                    {it.label}
                  </NavLink>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Remaining flat links */}
        <ul className="menu">
          {flatLinks
            .filter((l) => l.to !== '/')
            .map((it) => (
              <li key={it.to}>
                <NavLink
                  to={it.to}
                  className={({ isActive }) =>
                    'link' + (isActive || location.pathname === it.to ? ' active' : '')
                  }
                  end
                >
                  {it.label}
                </NavLink>
              </li>
            ))}
        </ul>
      </nav>
    </aside>
  );
}
