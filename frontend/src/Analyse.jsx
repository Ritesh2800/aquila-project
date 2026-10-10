import { useEffect, useRef, useState } from "react";
import { api, mediaUrl } from "./api";
import ScoreChart from "./ScoreChart.jsx";
import { useSlidingIndicator } from "./useSlidingIndicator";

const DEFAULTS = {
  enhance_mode: "auto",
  conf: 0.3,
  hold_s: 4,
  score_thr: 0.6,
  max_seconds: 60,
  camera: "CAM-01 (demo)",
  send_telegram: false,
};

export default function Analyse({ health, onAlertsChanged, hidden }) {
  const [file, setFile] = useState(null);
  const [opts, setOpts] = useState({
    ...DEFAULTS,
    camera: health?.camera || DEFAULTS.camera,
  });
  const [job, setJob] = useState(null);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);
  const segRef = useRef(null);
  const segSliderStyle = useSlidingIndicator(opts.enhance_mode, segRef, ".on");

  const set = (k) => (v) => setOpts((o) => ({ ...o, [k]: v }));
  const busy = job && (job.status === "queued" || job.status === "running");

  useEffect(() => {
    if (!job?.id || !busy) return;
    const timer = setInterval(async () => {
      try {
        const j = await api.job(job.id);
        setJob(j);
        if (j.status === "done") onAlertsChanged();
      } catch (e) {
        setError(e.message);
        setJob(null);
      }
    }, 1200);
    return () => clearInterval(timer);
  }, [job?.id, busy, onAlertsChanged]);

  async function submit() {
    if (!file) {
      setError("Please choose a video file first.");
      return;
    }
    setError("");
    const form = new FormData();
    form.append("video", file);
    Object.entries(opts).forEach(([k, v]) => form.append(k, String(v)));
    try {
      setJob(await api.analyze(form));
    } catch (e) {
      setError(e.message);
    }
  }

  const seek = (t) => {
    const v = videoRef.current;
    if (v) {
      v.currentTime = t;
      v.play().catch(() => {});
    }
  };

  const result = job?.status === "done" ? job.result : null;

  // Real data calculations when result is available
  const maxScore = result?.series?.length
    ? Math.max(...result.series.map((s) => s.score))
    : 0;
  const scoreColor = maxScore >= opts.score_thr ? "#FF9A9A" : "#3DD6B0";
  const meterWidth = Math.min(Math.round(maxScore * 100), 100);
  const meterThreshold = Math.min(Math.round(opts.score_thr * 100), 100);
  const thresholdText = opts.score_thr.toFixed(2);
  const displayScore = maxScore.toFixed(2);

  const triggers = result
    ? result.events.filter((e) => e.kind === "danger" && e.label === "triggered").map((e) => e.time_s)
    : [];
  const keyEvents = result
    ? result.events.filter((e) => e.kind !== "person")
    : [];

  const maxVideoDuration = result
    ? Math.max(result.series?.[result.series.length - 1]?.time_s || opts.max_seconds, 1)
    : opts.max_seconds;

  return (
    <main className="main" hidden={hidden} style={hidden ? { display: "none" } : undefined}>
      <h1 className="t1">Analyse video</h1>
      <p className="muted sub">
        Upload a clip. Aquila lifts the dark, scores the danger, and sends anything serious to review.
      </p>

      {error && <div className="banner error">{error}</div>}
      {job?.status === "error" && (
        <div className="banner error">Analysis failed: {job.error}</div>
      )}

      <div className="cols">
        {/* Left column: Video & Settings */}
        <section className="card left">
          <h2 className="t2">Video</h2>

          <div
            className="drop"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              style={{ display: "none" }}
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
            <svg
              width="30"
              height="30"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#FFB547"
              strokeWidth="1.8"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d="M12 16V4M7 9l5-5 5 5M4 20h16" />
            </svg>
            <b>{file ? file.name : "Drop a video here"}</b>
            <span className="muted">
              {file
                ? `${(file.size / 1048576).toFixed(1)} MB · Click to choose another`
                : "or click to choose one (.mp4 works best)"}
            </span>
          </div>

          {file && (
            <div className="file mono">
              <span>{file.name}</span>
              <span className="muted">{(file.size / 1048576).toFixed(1)} MB</span>
            </div>
          )}

          <h2 className="t2">Settings</h2>

          <div className="row">
            <span>Low-light enhance</span>
          </div>
          <div ref={segRef} className="seg">
            <span className="seg-slider" style={segSliderStyle} />
            {["auto", "on", "off"].map((m) => (
              <button
                key={m}
                type="button"
                className={opts.enhance_mode === m ? "on" : ""}
                onClick={() => set("enhance_mode")(m)}
              >
                {m === "auto" ? "Auto" : m === "on" ? "On" : "Off"}
              </button>
            ))}
          </div>

          <div className="row">
            <label htmlFor="s1">Detection confidence</label>
            <b>{opts.conf.toFixed(2)}</b>
          </div>
          <input
            className="rng"
            id="s1"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opts.conf}
            onChange={(e) => set("conf")(Number(e.target.value))}
          />

          <div className="row">
            <label htmlFor="s2">Hold time before alert</label>
            <b>{opts.hold_s} s</b>
          </div>
          <input
            className="rng"
            id="s2"
            type="range"
            min="1"
            max="10"
            step="1"
            value={opts.hold_s}
            onChange={(e) => set("hold_s")(Number(e.target.value))}
          />

          <div className="row">
            <label htmlFor="s3">Danger score threshold</label>
            <b>{opts.score_thr.toFixed(2)}</b>
          </div>
          <input
            className="rng"
            id="s3"
            type="range"
            min="0"
            max="1"
            step="0.05"
            value={opts.score_thr}
            onChange={(e) => set("score_thr")(Number(e.target.value))}
          />

          <div className="row">
            <label htmlFor="s4">Analyse first</label>
            <b>{opts.max_seconds} s</b>
          </div>
          <input
            className="rng"
            id="s4"
            type="range"
            min="10"
            max="120"
            step="10"
            value={opts.max_seconds}
            onChange={(e) => set("max_seconds")(Number(e.target.value))}
          />

          <label htmlFor="cam" className="muted">
            Camera name or location
          </label>
          <input
            className="inp"
            id="cam"
            value={opts.camera}
            onChange={(e) => set("camera")(e.target.value)}
          />

          <label className="chk">
            <input
              type="checkbox"
              checked={opts.send_telegram}
              disabled={!health?.telegram}
              onChange={(e) => set("send_telegram")(e.target.checked)}
            />
            <span>
              Send alerts to Telegram
              {!health?.telegram ? " (not set up on the server)" : ""}
            </span>
          </label>

          <button
            className="btn amber"
            disabled={!file || busy}
            onClick={submit}
          >
            {busy
              ? job?.progress
                ? `Analysing… ${Math.round(job.progress * 100)}%`
                : "Analysing…"
              : "Analyse video"}
          </button>
        </section>

        {/* Right column: Result card */}
        {result ? (
          <section className="card right">
            <div className="rh">
              <h2 className="t2">Result</h2>
              <span className="chip">
                Enhance: {result.enhanced_fraction > 0 ? "on" : "off"}
              </span>
              <span className="chip mono">{result.speed} fps</span>
              <span className="chip mono">first {opts.max_seconds} s</span>
            </div>

            {/* Video Player */}
            <div className="frame">
              <video
                ref={videoRef}
                src={mediaUrl(result.video_url)}
                controls
                playsInline
                autoPlay
              />
            </div>

            {/* Live Stats */}
            <div className="stats">
              <div className="tile">
                <span className="muted">Danger score</span>
                <b className="big" style={{ color: scoreColor }}>
                  {displayScore}
                </b>
                <div className="meter">
                  <i style={{ width: `${meterWidth}%` }}></i>
                  <u style={{ left: `${meterThreshold}%` }}></u>
                </div>
                <span className="muted mono">threshold {thresholdText}</span>
              </div>
              <div className="tile">
                <span className="muted">Events</span>
                <b className="big">{keyEvents.length}</b>
                <span className="muted">
                  in the first {opts.max_seconds} s
                </span>
              </div>
              <div className="tile">
                <span className="muted">Alerts raised</span>
                <b className="big" style={{ color: "#FFB547" }}>
                  {result.n_alerts || 0}
                </b>
                <span className="muted">sent to review</span>
              </div>
            </div>

            {/* Danger Score Graph */}
            <h2 className="t2" style={{ margin: "22px 0 10px" }}>
              Danger score over time
            </h2>
            <ScoreChart
              series={result.series}
              threshold={opts.score_thr}
              triggers={triggers}
              onSeek={seek}
            />
            <p className="legend" style={{ margin: "10px 0 18px" }}>
              <i className="k score" />Danger score
              <i className="k bright" />Brightness
              <i className="k thr" />Alert threshold
              <span className="mono" style={{ fontSize: "12px" }}>
                Click chart or event to jump
              </span>
            </p>

            {/* Interactive Timeline Track */}
            <div className="track">
              {keyEvents.map((e, i) => {
                const pct = Math.min(
                  Math.max((e.time_s / maxVideoDuration) * 100, 0),
                  100
                );
                const isRisky = e.kind === "danger" || e.conf >= opts.score_thr;
                return (
                  <s
                    key={i}
                    className={isRisky ? "h" : ""}
                    style={{ left: `${pct}%`, cursor: "pointer" }}
                    onClick={() => seek(e.time_s)}
                    title={`${e.label} at ${e.time_s}s`}
                  />
                );
              })}
            </div>

            <div className="ticks mono muted">
              <span>0s</span>
              <span>{Math.round(opts.max_seconds * 0.25)}s</span>
              <span>{Math.round(opts.max_seconds * 0.5)}s</span>
              <span>{Math.round(opts.max_seconds * 0.75)}s</span>
              <span>{opts.max_seconds}s</span>
            </div>

            {/* Events List */}
            {keyEvents.length > 0 ? (
              keyEvents.slice(0, 50).map((e, i) => {
                const mins = Math.floor(e.time_s / 60);
                const secs = Math.floor(e.time_s % 60);
                const timeStr = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
                const isRisky = e.kind === "danger" || e.conf >= opts.score_thr;
                return (
                  <div
                    key={i}
                    className="ev"
                    style={{ cursor: "pointer" }}
                    onClick={() => seek(e.time_s)}
                  >
                    <span className="mono">{timeStr}</span>
                    <span>{e.detail || e.label}</span>
                    <span className={`chip ${isRisky ? "hot" : ""}`}>
                      {e.conf.toFixed(2)}
                    </span>
                  </div>
                );
              })
            ) : (
              <div className="ev">
                <span className="muted">No events detected.</span>
              </div>
            )}
          </section>
        ) : busy ? (
          <section className="card right">
            <div className="rh">
              <h2 className="t2">Analysis in progress</h2>
            </div>
            <div style={{ padding: "60px 24px", textAlign: "center" }}>
              <h3
                style={{
                  font: "600 20px 'Bricolage Grotesque', sans-serif",
                  color: "#FFB547",
                  margin: "0 0 12px",
                }}
              >
                {job?.status === "queued"
                  ? "Waiting for analyser…"
                  : `Analysing video… ${Math.round((job?.progress || 0) * 100)}%`}
              </h3>
              <p className="muted" style={{ maxWidth: "420px", margin: "0 auto 20px", lineHeight: "1.5" }}>
                Lifting dark frames, running object & pose detection models, and evaluating danger thresholds...
              </p>
              <div
                style={{
                  height: "6px",
                  background: "rgba(255,255,255,0.1)",
                  borderRadius: "6px",
                  overflow: "hidden",
                  maxWidth: "360px",
                  margin: "0 auto",
                }}
              >
                <div
                  style={{
                    width: `${Math.round((job?.progress || 0) * 100)}%`,
                    height: "100%",
                    background: "#FFB547",
                    borderRadius: "6px",
                    transition: "width 0.3s",
                  }}
                />
              </div>
            </div>
          </section>
        ) : (
          <section className="card right">
            <div className="rh">
              <h2 className="t2">Result</h2>
            </div>
            <div style={{ padding: "80px 24px", textAlign: "center" }}>
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
                  <polygon points="23 7 16 12 23 17 23 7" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </svg>
              </div>
              <h3
                style={{
                  font: "600 20px 'Bricolage Grotesque', sans-serif",
                  color: "#E8EDF2",
                  margin: "0 0 8px",
                }}
              >
                No analysis yet
              </h3>
              <p
                className="muted"
                style={{
                  maxWidth: "420px",
                  margin: "0 auto",
                  lineHeight: "1.5",
                }}
              >
                Choose a video and click <b>Analyse video</b>. The annotated result, danger score metrics, interactive timeline graph, and detected events will appear here.
              </p>
            </div>
          </section>
        )}
      </div>
    </main>
  );
}
