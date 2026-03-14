import { useEffect, useState } from "react";

const API = "http://localhost:8000";

export function TagPanel({ tag, onClose }) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API}/tags/${encodeURIComponent(tag)}`)
      .then((r) => r.json())
      .then(setHistory)
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  }, [tag]);

  return (
    <div className="mt-3 bg-indigo-50 border border-indigo-100 rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-semibold text-indigo-700 bg-indigo-100 px-2 py-0.5 rounded-md">
            #{tag}
          </span>
          {!loading && (
            <span className="text-xs text-indigo-500 font-medium">
              {history.length === 1
                ? "first time — keep an eye on this"
                : `hit ${history.length} times`}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-indigo-300 hover:text-indigo-600 text-lg leading-none"
        >
          ✕
        </button>
      </div>

      {loading ? (
        <p className="text-xs text-indigo-400 animate-pulse">Loading history…</p>
      ) : history.length === 0 ? (
        <p className="text-xs text-indigo-400">No history found.</p>
      ) : (
        <ol className="space-y-2">
          {history.map((item, i) => {
            const ts = new Date(item.created_at + "Z").toLocaleString();
            const projectName = item.project_path
              ? item.project_path.split("/").pop()
              : null;
            return (
              <li key={item.briefing_id} className="flex gap-3 items-start">
                <span className="flex-shrink-0 w-5 h-5 rounded-full bg-indigo-200 text-indigo-700 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-xs text-gray-700 leading-snug">{item.goal}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-400">{ts}</span>
                    {projectName && (
                      <span className="text-xs font-mono text-gray-400">{projectName}</span>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
