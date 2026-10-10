import { useRef } from "react";
import { useSlidingIndicator } from "./useSlidingIndicator";

export default function TopBar({ page, setPage, pendingCount = 0, health }) {
  const modelsReady = health?.models_ready ?? true;
  const device = health?.device === "cuda" ? "GPU" : (health?.device || "cpu");
  const navRef = useRef(null);
  const sliderStyle = useSlidingIndicator(page, navRef, ".tab.on");

  return (
    <header className="top">
      <div className="pill glass pl">
        <svg width="28" height="28" viewBox="0 0 30 30" aria-hidden="true">
          <circle cx="15" cy="15" r="13" fill="none" stroke="#FFB547" strokeWidth="2" />
          <circle cx="15" cy="15" r="5" fill="#FFB547" />
          <path d="M2 15h6M22 15h6" stroke="#FFB547" strokeWidth="2" />
        </svg>
        <b>Aquila</b>
      </div>

      <nav ref={navRef} className="pill glass pn" aria-label="Main">
        <span className="pill-slider" style={sliderStyle} />
        <button
          className={`tab ${page === "analyse" ? "on" : ""}`}
          onClick={() => setPage("analyse")}
        >
          Analyse video
        </button>
        <button
          className={`tab ${page === "alerts" ? "on" : ""}`}
          onClick={() => setPage("alerts")}
        >
          Alerts {pendingCount > 0 && <span className="badge">{pendingCount}</span>}
        </button>
      </nav>

      <div className="pill glass ps">
        <i
          style={
            !modelsReady
              ? { background: "#FFB547", boxShadow: "0 0 10px #FFB547" }
              : undefined
          }
        />
        <span>{modelsReady ? "Models ready" : "Loading models…"}</span>
        <u></u>
        <span>Running on {device}</span>
      </div>
    </header>
  );
}
