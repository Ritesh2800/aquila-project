import { useEffect, useRef, useState } from "react";
import { api, mediaUrl } from "./api";
import { useSlidingIndicator } from "./useSlidingIndicator";

const FILTERS = ["pending", "confirmed", "dismissed", "all"];

const STEPS_LIST = [
  { name: "queued", label: "Queued" },
  { name: "initiated", label: "Initiated" },
  { name: "ringing", label: "Ringing" },
  { name: "in-progress", label: "In progress" },
  { name: "completed", label: "Completed" },
];

const TERMINAL = new Set(["completed", "busy", "no-answer", "failed", "canceled"]);

export default function Alerts({ alerts = [], reload, health, hidden }) {
  const [filter, setFilter] = useState("pending");
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  // Twilio call status state
  const [callSid, setCallSid] = useState(null);
  const [callStatus, setCallStatus] = useState(null);
  const [callBusy, setCallBusy] = useState(false);
  const [callErr, setCallErr] = useState("");
  const pollRef = useRef(null);
  const videoRef = useRef(null);
  const tabsRef = useRef(null);
  const tabsSliderStyle = useSlidingIndicator(filter, tabsRef, ".on");

  const shown = alerts.filter((a) => filter === "all" || a.status === filter);
  const current = shown.find((a) => a.id === selected) || shown[0] || null;

  useEffect(() => {
    setMessage("");
  }, [current?.id]);

  useEffect(() => {
    return () => clearInterval(pollRef.current);
  }, []);

  function startPolling(sid) {
    clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const r = await api.callStatus(sid);
        setCallStatus(r.status);
        if (TERMINAL.has(r.status)) {
          clearInterval(pollRef.current);
          setCallBusy(false);
        }
      } catch {
        clearInterval(pollRef.current);
        setCallBusy(false);
      }
    }, 2000);
  }

  async function sendTestCall() {
    setCallBusy(true);
    setCallErr("");
    setCallSid(null);
    setCallStatus(null);
    try {
      const r = await api.testCall();
      setCallSid(r.sid);
      setCallStatus(r.status);
      if (!TERMINAL.has(r.status)) {
        startPolling(r.sid);
      } else {
        setCallBusy(false);
      }
    } catch (e) {
      setCallErr(e.message);
      setCallBusy(false);
    }
  }

  async function act(kind) {
    if (!current) return;
    if (
      kind === "confirm" &&
      !window.confirm("Confirm this alert? This will trigger a Twilio voice call to the helpline.")
    ) {
      return;
    }

    setBusy(true);
    try {
      const r = kind === "confirm" ? await api.confirm(current.id) : await api.dismiss(current.id);
      setMessage(r.message);
      if (r.call_sid) {
        setCallSid(r.call_sid);
        setCallStatus("queued");
        startPolling(r.call_sid);
      }
      await reload();
    } catch (e) {
      setMessage(e.message);
    }
    setBusy(false);
  }

  async function cleanup() {
    try {
      const r = await api.cleanup();
      setMessage(r.message);
      await reload();
    } catch (e) {
      setMessage(e.message);
    }
  }

  const pendingCount = alerts.filter((a) => a.status === "pending").length;
  const confirmedCount = alerts.filter((a) => a.status === "confirmed").length;
  const dismissedCount = alerts.filter((a) => a.status === "dismissed").length;

  let activeStepIndex = -1;
  if (callStatus) {
    const statusMap = {
      queued: 0,
      initiated: 1,
      ringing: 2,
      "in-progress": 3,
      completed: 4,
    };
    activeStepIndex = statusMap[callStatus] ?? (TERMINAL.has(callStatus) ? 4 : 0);
  }

  return (
    <main className="main" hidden={hidden} style={hidden ? { display: "none" } : undefined}>
      <h1 className="t1">Alerts</h1>
      <p className="muted sub">
        Confirm a real threat and Aquila places the call and sends the clip.
      </p>

      {message && <div className="banner ok">{message}</div>}
      {callErr && <div className="banner error">Twilio call error: {callErr}</div>}

      <div ref={tabsRef} className="tabs">
        <span className="tabs-slider" style={tabsSliderStyle} />
        <button
          className={filter === "pending" ? "on" : ""}
          onClick={() => setFilter("pending")}
        >
          Pending {pendingCount}
        </button>
        <button
          className={filter === "confirmed" ? "on" : ""}
          onClick={() => setFilter("confirmed")}
        >
          Confirmed {confirmedCount}
        </button>
        <button
          className={filter === "dismissed" ? "on" : ""}
          onClick={() => setFilter("dismissed")}
        >
          Dismissed {dismissedCount}
        </button>
        <button
          className={filter === "all" ? "on" : ""}
          onClick={() => setFilter("all")}
        >
          All
        </button>
      </div>

      <div className="cols">
        <section className="left">
          {shown.map((a) => {
            const isSel = current?.id === a.id;
            const mins = Math.floor((a.video_time || 0) / 60);
            const secs = Math.floor((a.video_time || 0) % 60);
            const timeStr = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;

            return (
              <div
                key={a.id}
                className={`acard ${isSel ? "sel" : ""}`}
                onClick={() => setSelected(a.id)}
              >
                <div className="th">
                  {a.snapshot_url ? (
                    <img
                      src={mediaUrl(a.snapshot_url)}
                      alt=""
                      style={{
                        width: "100%",
                        height: "100%",
                        objectFit: "cover",
                        borderRadius: "8px",
                      }}
                    />
                  ) : (
                    <i
                      style={{
                        left: "34px",
                        top: "22px",
                        width: "16px",
                        height: "14px",
                      }}
                    />
                  )}
                </div>
                <div>
                  <b>{a.camera}</b>
                  <span className="muted mono">
                    Alert {a.id} - {timeStr}
                  </span>
                </div>
                <span className="sc">{a.score.toFixed(2)}</span>
              </div>
            );
          })}

          {!shown.length && (
            <div className="muted" style={{ padding: "20px 8px" }}>
              No {filter === "all" ? "" : filter} alerts.
            </div>
          )}

          <button
            className="btn ghost"
            style={{ width: "100%", margin: "6px 0 18px" }}
            onClick={cleanup}
          >
            Delete expired alerts
          </button>

          <div className="card">
            <h2 className="t2">Demo: Twilio voice alert</h2>
            <button
              className="btn amber"
              disabled={callBusy || !health?.twilio}
              onClick={sendTestCall}
            >
              {callBusy ? "Calling…" : "Send test alert call"}
            </button>
            {!health?.twilio && (
              <span
                className="muted"
                style={{ display: "block", fontSize: "12px", marginTop: "8px" }}
              >
                Twilio credentials not configured in .env
              </span>
            )}
          </div>
        </section>

        <section className="card right">
          {current ? (
            <>
              <div className="frame">
                {current.clip_url ? (
                  <video
                    ref={videoRef}
                    key={current.id}
                    src={mediaUrl(current.clip_url)}
                    controls
                    playsInline
                    autoPlay
                    loop
                    muted
                  />
                ) : (
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: "#8A98A8",
                    }}
                  >
                    <span>No video clip available</span>
                  </div>
                )}
              </div>

              <div className="rh" style={{ marginTop: "18px" }}>
                <h2 className="t2">
                  Alert {current.id} - {current.camera}
                </h2>
                {current.reasons.map((r, i) => (
                  <span key={i} className="chip hot">
                    {r}
                  </span>
                ))}
                <b className="sc">{current.score.toFixed(2)}</b>
              </div>

              <div className="acts">
                <button
                  className="btn red"
                  disabled={busy}
                  onClick={() => act("confirm")}
                >
                  Confirm - call for help
                </button>
                <button
                  className="btn ghost"
                  disabled={busy}
                  onClick={() => act("dismiss")}
                >
                  Dismiss
                </button>
              </div>

              <div className="row">
                <span className="muted">Call status</span>
                <span className="mono muted">
                  {callSid
                    ? callSid.length > 12
                      ? `${callSid.slice(0, 4)}...${callSid.slice(-4)}`
                      : callSid
                    : callStatus
                    ? callStatus
                    : "Ready"}
                </span>
              </div>

              <div className="steps">
                {STEPS_LIST.map((step, idx) => {
                  const isDoneOrActive =
                    activeStepIndex >= 0 && idx <= activeStepIndex;
                  const isCurrent = activeStepIndex === idx;

                  return (
                    <div
                      key={step.name}
                      className={isDoneOrActive ? "" : "inactive"}
                    >
                      <i />
                      {isCurrent ? <b>{step.label}</b> : step.label}
                    </div>
                  );
                })}
              </div>
            </>
          ) : (
            <div style={{ padding: "80px 24px", textAlign: "center" }} className="muted">
              <div
                style={{
                  width: "56px",
                  height: "56px",
                  borderRadius: "50%",
                  background: "rgba(255,181,71,0.12)",
                  border: "1px solid rgba(255,181,71,0.3)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  margin: "0 auto 18px",
                  color: "#FFB547",
                }}
              >
                <svg
                  width="28"
                  height="28"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </div>
              <h2 className="t2" style={{ color: "#E8EDF2", margin: "0 0 8px" }}>
                Nothing to review
              </h2>
              <p style={{ maxWidth: "400px", margin: "0 auto", lineHeight: "1.5" }}>
                When an analysis raises an alert above the threshold, it will appear here for review and dispatch.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
