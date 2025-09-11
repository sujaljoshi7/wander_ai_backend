import './dashboard.css';

export default function Dashboard() {
  return (
    <div className="dashboard">
      <div className="cards">
        <div className="card stat">
          <div className="kpi">
            <span className="label">Cities Tracked</span>
            <span className="value">128</span>
          </div>
        </div>
        <div className="card stat">
          <div className="kpi">
            <span className="label">Places Curated</span>
            <span className="value">2,340</span>
          </div>
        </div>
        <div className="card stat">
          <div className="kpi">
            <span className="label">Restaurants Listed</span>
            <span className="value">950</span>
          </div>
        </div>
        <div className="card stat">
          <div className="kpi">
            <span className="label">Itineraries</span>
            <span className="value">312</span>
          </div>
        </div>

        <div className="card wide">
          <h3>Recent Activity</h3>
          <ul className="activity">
            <li>New itinerary added for Paris</li>
            <li>5 restaurants approved in Tokyo</li>
            <li>City profile updated: Barcelona</li>
          </ul>
        </div>

        <div className="card">
          <h3>Top Cities</h3>
          <ol>
            <li>Paris</li>
            <li>Tokyo</li>
            <li>New York</li>
          </ol>
        </div>

        <div className="card">
          <h3>Data Health</h3>
          <p>98.4% up to date</p>
        </div>
      </div>
    </div>
  );
}
