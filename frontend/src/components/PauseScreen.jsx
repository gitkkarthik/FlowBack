import { useState } from "react";

const API = "http://localhost:8000";

const STORAGE_KEY = "flowback_paths";

function loadPaths() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    return Array.isArray(saved) && saved.length > 0 ? saved : [""];
  } catch {
    return [""];
  }
}

export function PauseScreen({ onSaved }) {
  const [paths, setPaths] = useState(loadPaths);
  const [note, setNote] = useState("");
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [filesFound, setFilesFound] = useState(null);
  const [picking, setPicking] = useState(null); // index being picked

  function savePaths(next) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setPaths(next);
  }

  function updatePath(index, value) {
    savePaths(paths.map((p, i) => (i === index ? value : p)));
  }

  function addPath() {
    savePaths([...paths, ""]);
  }

  function removePath(index) {
    savePaths(paths.filter((_, i) => i !== index));
  }

  async function choosePath(index) {
    setPicking(index);
    try {
      const res = await fetch(`${API}/pick-folder`);
      if (res.ok) {
        const { path } = await res.json();
        savePaths(paths.map((p, i) => (i === index ? path : p)));
      }
      // 204 = user cancelled, do nothing
    } catch {
      // silently ignore — user can still type manually
    } finally {
      setPicking(null);
    }
  }

  async function handleSave() {
    const validPaths = paths.map((p) => p.trim()).filter(Boolean);
    if (validPaths.length === 0) {
      setError("Add at least one project folder.");
      return;
    }
    setStatus("saving");
    setError("");
    setFilesFound(null);

    try {
      const snapRes = await fetch(`${API}/snapshot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ watch_paths: validPaths, user_note: note || null }),
      });
      if (!snapRes.ok) throw new Error(`Snapshot failed: ${snapRes.status}`);
      const snap = await snapRes.json();
      setFilesFound(snap.files_changed.length);

      const briefRes = await fetch(`${API}/briefing/${snap.snapshot_id}`, {
        method: "POST",
      });
      if (!briefRes.ok) {
        const body = await briefRes.json().catch(() => ({}));
        throw new Error(body.detail || `Briefing failed: ${briefRes.status}`);
      }

      setStatus("done");
      if (onSaved) onSaved();
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="w-full max-w-lg space-y-6">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Taking a break?</h1>
          <p className="text-gray-500 mt-1">
            Point me at your projects — I'll figure out what you were doing.
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6 space-y-4">

          <div>
            <label className="block text-sm font-semibold text-gray-800 mb-2">
              Project folders <span className="text-red-400">*</span>
            </label>
            <div className="space-y-2">
              {paths.map((path, i) => (
                <div key={i} className="flex gap-2 items-center">
                  {/* Choose folder button */}
                  <button
                    onClick={() => choosePath(i)}
                    disabled={picking === i}
                    title="Browse for folder"
                    className="flex-shrink-0 px-3 py-2.5 text-xs font-medium border border-gray-200 rounded-xl text-gray-600 hover:bg-gray-50 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-40 transition-colors whitespace-nowrap"
                  >
                    {picking === i ? "…" : "Choose"}
                  </button>

                  {/* Path input */}
                  <input
                    className="flex-1 border border-gray-200 rounded-xl px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-400"
                    placeholder="/Users/you/projects/myapp"
                    value={path}
                    onChange={(e) => updatePath(i, e.target.value)}
                  />

                  {/* Remove */}
                  {paths.length > 1 && (
                    <button
                      onClick={() => removePath(i)}
                      className="flex-shrink-0 w-8 h-8 flex items-center justify-center rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                    >
                      ✕
                    </button>
                  )}
                </div>
              ))}
            </div>

            <button
              onClick={addPath}
              className="mt-2 flex items-center gap-1.5 text-sm text-indigo-600 hover:text-indigo-800 font-medium transition-colors"
            >
              <span className="text-lg leading-none">+</span> Add another folder
            </button>
            <p className="text-xs text-gray-400 mt-1.5">
              Scans up to 5 recently modified files per folder (last 2 hours).
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Anything to add?{" "}
              <span className="text-gray-400 font-normal">(optional)</span>
            </label>
            <textarea
              className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-400"
              rows={3}
              placeholder="e.g. Debugging auth middleware, kept getting 401s on token refresh"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>

          <button
            onClick={handleSave}
            disabled={status === "saving"}
            className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-300 text-white font-semibold py-3 rounded-xl transition-colors"
          >
            {status === "saving"
              ? filesFound === null
                ? "Scanning files…"
                : `Found ${filesFound} file${filesFound !== 1 ? "s" : ""} — generating briefing…`
              : "Save my context"}
          </button>

          {status === "done" && (
            <p className="text-center text-green-600 text-sm font-medium">
              Context saved! Come back when you're ready.
            </p>
          )}
          {error && status !== "saving" && (
            <p className="text-center text-red-500 text-sm">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
