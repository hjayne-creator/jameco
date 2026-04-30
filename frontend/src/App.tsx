import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { NewRun } from "./pages/NewRun";
import { RunDetail } from "./pages/RunDetail";
import { RunHistory } from "./pages/RunHistory";
import { StyleGuides } from "./pages/StyleGuides";

export default function App() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h2>JameCo PDP</h2>
        <nav>
          <NavLink to="/new" className={({ isActive }) => (isActive ? "active" : "")}>
            New Run
          </NavLink>
          <NavLink to="/runs" className={({ isActive }) => (isActive ? "active" : "")}>
            Run History
          </NavLink>
          <NavLink to="/style-guides" className={({ isActive }) => (isActive ? "active" : "")}>
            Style Guides
          </NavLink>
        </nav>
      </aside>
      <main className="main">
        <Routes>
          <Route path="/" element={<Navigate to="/new" replace />} />
          <Route path="/new" element={<NewRun />} />
          <Route path="/runs" element={<RunHistory />} />
          <Route path="/runs/:id" element={<RunDetail />} />
          <Route path="/style-guides" element={<StyleGuides />} />
        </Routes>
      </main>
    </div>
  );
}
