import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Link, Route, Routes } from "react-router";

import Admin from "./routes/Admin";
import ClaimsPro from "./routes/ClaimsPro";
import Panel from "./routes/Panel";

function Home() {
  return (
    <main>
      <h1>Meridian demo</h1>
      <ul>
        <li><Link to="/admin">Admin monitor</Link></li>
        <li><Link to="/claimspro/IS-CLM-2025004222">Mock ClaimsPro (claim 4222)</Link></li>
        <li><Link to="/panel">Side panel</Link></li>
      </ul>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/claimspro/:claimId" element={<ClaimsPro />} />
        <Route path="/panel" element={<Panel />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
