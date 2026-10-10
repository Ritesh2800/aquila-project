import { useCallback, useEffect, useState } from "react";
import { api, getKey, setKey } from "./api";
import TopBar from "./TopBar.jsx";
import Analyse from "./Analyse.jsx";
import Alerts from "./Alerts.jsx";

function Gate({ onUnlock }) {
  const [value, setValue] = useState("");
  const [err, setErr] = useState("");
  async function go(e) {
    e.preventDefault();
    setKey(value);
    try {
      await api.check();
      onUnlock();
    } catch {
      setKey("");
      setErr("That key was not accepted.");
    }
  }
  return (
    <div className="app">
      <div className="bg">
        <i></i><i></i><i></i>
      </div>
      <main className="gate">
        <form className="panel" onSubmit={go}>
          <h1>Aquila</h1>
          <p className="muted">Enter the access key for this server.</p>
          <input
            className="inp"
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoFocus
            aria-label="Access key"
          />
          {err && <div className="banner error">{err}</div>}
          <button className="btn amber" disabled={!value}>
            Unlock
          </button>
        </form>
      </main>
    </div>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [unlocked, setUnlocked] = useState(false);
  const [page, setPage] = useState("analyse");
  const [alerts, setAlerts] = useState([]);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    api
      .health()
      .then(async (h) => {
        setHealth(h);
        if (!h.auth_required) return setUnlocked(true);
        if (getKey()) {
          try {
            await api.check();
            setUnlocked(true);
          } catch {
            setKey("");
          }
        }
      })
      .catch(() => setOffline(true));
  }, []);

  const reload = useCallback(async () => {
    try {
      setAlerts(await api.alerts());
    } catch (e) {
      if (e.status === 401) {
        setKey("");
        setUnlocked(false);
      }
    }
  }, []);

  useEffect(() => {
    if (!unlocked) return;
    reload();
    const t = setInterval(reload, 10000);
    return () => clearInterval(t);
  }, [unlocked, reload]);

  // Keep model status fresh until server finishes loading
  useEffect(() => {
    if (!health || health.models_ready) return;
    const t = setInterval(() => api.health().then(setHealth).catch(() => {}), 3000);
    return () => clearInterval(t);
  }, [health?.models_ready]);

  if (offline) {
    return (
      <div className="app">
        <div className="bg">
          <i></i><i></i><i></i>
        </div>
        <main className="gate">
          <div className="panel">
            <h1>Aquila</h1>
            <p className="muted">
              The server is not reachable. Start the backend with{" "}
              <code>uvicorn main:app --port 8000</code> and reload this page.
            </p>
          </div>
        </main>
      </div>
    );
  }

  if (!health) {
    return (
      <div className="app">
        <div className="bg">
          <i></i><i></i><i></i>
        </div>
        <main className="gate">
          <div className="panel">
            <p className="muted">Connecting…</p>
          </div>
        </main>
      </div>
    );
  }

  if (!unlocked) return <Gate onUnlock={() => setUnlocked(true)} />;

  const pendingCount = alerts.filter((a) => a.status === "pending").length;

  return (
    <div className="app">
      <div className="bg">
        <i></i><i></i><i></i>
      </div>
      <TopBar
        page={page}
        setPage={setPage}
        pendingCount={pendingCount}
        health={health}
      />
      <Analyse
        health={health}
        onAlertsChanged={reload}
        hidden={page !== "analyse"}
      />
      <Alerts
        alerts={alerts}
        reload={reload}
        health={health}
        hidden={page !== "alerts"}
      />
    </div>
  );
}
