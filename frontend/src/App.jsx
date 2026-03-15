import { useEffect, useState } from "react";
import { PauseScreen } from "./components/PauseScreen";
import { ResumeScreen } from "./components/ResumeScreen";
import { ErrorGraph } from "./components/ErrorGraph";

const API = "http://localhost:8000";

export default function App() {
  const [screen, setScreen] = useState(null); // null = loading

  // On mount: if a briefing exists, go straight to Resume
  useEffect(() => {
    fetch(`${API}/briefing/latest`)
      .then((r) => setScreen(r.ok ? "resume" : "pause"))
      .catch(() => setScreen("pause"));
  }, []);

  if (screen === null) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-400 text-sm animate-pulse">Loading…</p>
      </div>
    );
  }

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-10 flex justify-center gap-2 py-3 bg-white border-b border-gray-100">
        <button
          onClick={() => setScreen("pause")}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            screen === "pause"
              ? "bg-indigo-600 text-white"
              : "text-gray-500 hover:text-gray-800"
          }`}
        >
          Pause
        </button>
        <button
          onClick={() => setScreen("resume")}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            screen === "resume"
              ? "bg-indigo-600 text-white"
              : "text-gray-500 hover:text-gray-800"
          }`}
        >
          Resume
        </button>
        <button
          onClick={() => setScreen("graph")}
          className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
            screen === "graph"
              ? "bg-red-600 text-white"
              : "text-gray-500 hover:text-gray-800"
          }`}
        >
          Graph
        </button>
      </nav>

      <div className="pt-14">
        {screen === "pause" ? (
          <PauseScreen onSaved={() => setScreen("resume")} />
        ) : screen === "graph" ? (
          <ErrorGraph />
        ) : (
          <ResumeScreen onBack={() => setScreen("pause")} />
        )}
      </div>
    </>
  );
}
