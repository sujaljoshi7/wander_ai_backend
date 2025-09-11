import './App.css'
import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Dashboard from './pages/Dashboard.jsx'
import City from './pages/city/City.jsx'
import State from './pages/state/State.jsx'
import Country from './pages/country/Country.jsx'
import Place from './pages/Place.jsx'
import Food from './pages/Food.jsx'
import Hotel from './pages/Hotel.jsx'
import Itineraries from './pages/Itineraries.jsx'
import PlaceCreate from './pages/PlaceCreate.jsx'
import Restaurant from './pages/restaurant/Restaurant.jsx'
import RestaurantCreate from './pages/restaurant/RestaurantCreate.jsx'

function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/city" element={<City />} />
        <Route path="/state" element={<State />} />
        <Route path="/country" element={<Country />} />
        <Route path="/place" element={<Place />} />
        <Route path="/place/new" element={<PlaceCreate />} />
        <Route path="/place/update/:id" element={<PlaceCreate />} />
        <Route path="/restaurant" element={<Restaurant />} />
        <Route path="/restaurant/new" element={<RestaurantCreate />} />
        <Route path="/restaurant/update/:id" element={<RestaurantCreate />} />
        <Route path="/food" element={<Food />} />
        <Route path="/hotel" element={<Hotel />} />
        <Route path="/itineraries" element={<Itineraries />} />
      </Route>
    </Routes>
  )
}

export default App
