import { useEffect, useState } from "react";
import { BriefingCard } from "./BriefingCard";
import { TagPanel } from "./TagPanel";

const API = "http://localhost:8000";

function ProjectBriefing({ briefing }) {
  const [activeTag, setActiveTag] = useState(null);
  const projectName = briefing.project_path
    ? briefing.project_path.split("/").pop()
    : "Project";

  function handleTagClick(tag) {
    setActiveTag(activeTag === tag ? null : tag);
  }

  return (
    <div className="space-y-3">
      {/* Project label */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-semibold bg-gray-100 text-gray-600 px-2.5 py-1 rounded-lg font-mono">
          {projectName}
        </span>
        {briefing.project_path && (
          <span className="text-xs text-gray-400 font-mono truncate">
            {briefing.project_path}
          </span>
        )}
      </div>

      <BriefingCard title="Your goal">
        <p className="text-gray-800 text-base leading-relaxed">
          {briefing.goal || "—"}
        </p>
      </BriefingCard>

      <BriefingCard title="Where you were stuck">
        <p className="text-gray-800 text-base leading-relaxed">
          {briefing.stuck_point || "—"}
        </p>
      </BriefingCard>

      <BriefingCard title="Next 3 steps">
        {briefing.next_steps.length === 0 ? (
          <p className="text-gray-400 text-sm">No steps generated.</p>
        ) : (
          <ol className="space-y-3">
            {briefing.next_steps.map((step, i) => (
              <li key={i} className="flex gap-3">
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 text-xs font-bold flex items-center justify-center">
                  {i + 1}
                </span>
                <p className="text-gray-800 text-sm leading-relaxed">{step}</p>
              </li>
            ))}
          </ol>
        )}
      </BriefingCard>

      <BriefingCard title="Files changed" collapsible>
        {briefing.files_changed.length === 0 ? (
          <p className="text-gray-400 text-sm">No files recorded.</p>
        ) : (
          <ul className="space-y-1">
            {briefing.files_changed.map((f, i) => (
              <li
                key={i}
                className="text-xs font-mono text-gray-600 bg-gray-50 rounded-lg px-3 py-1.5"
              >
                {f}
              </li>
            ))}
          </ul>
        )}
      </BriefingCard>

      {briefing.tags && briefing.tags.length > 0 && (
        <div>
          <div className="flex flex-wrap gap-2">
            {briefing.tags.map((tag) => (
              <button
                key={tag}
                onClick={() => handleTagClick(tag)}
                className={`text-xs font-mono px-2.5 py-1 rounded-full border transition-colors ${
                  activeTag === tag
                    ? "bg-indigo-600 text-white border-indigo-600"
                    : "bg-white text-indigo-600 border-indigo-200 hover:border-indigo-400 hover:bg-indigo-50"
                }`}
              >
                #{tag}
              </button>
            ))}
          </div>
          {activeTag && (
            <TagPanel tag={activeTag} onClose={() => setActiveTag(null)} />
          )}
        </div>
      )}
    </div>
  );
}

function SessionEntry({ session, isLatest }) {
  const ts = new Date(session.created_at + "Z").toLocaleString();

  return (
    <div className="space-y-6">
      {/* Session header */}
      <div className="flex items-center gap-3">
        {isLatest && (
          <span className="text-xs font-semibold bg-indigo-600 text-white px-2.5 py-0.5 rounded-full">
            Latest
          </span>
        )}
        <span className="text-xs text-gray-400">{ts}</span>
        <span className="text-xs text-gray-300">
          {session.projects.length} project{session.projects.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* One block per project */}
      {session.projects.map((b, i) => (
        <div key={b.briefing_id}>
          <ProjectBriefing briefing={b} />
          {i < session.projects.length - 1 && (
            <div className="mt-6 border-t border-gray-100" />
          )}
        </div>
      ))}
    </div>
  );
}

export function ResumeScreen({ onBack }) {
  const [briefings, setBriefings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${API}/briefings`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load briefings");
        return r.json();
      })
      .then(setBriefings)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-400 text-sm animate-pulse">Loading briefings…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center space-y-3">
          <p className="text-red-500 text-sm">{error}</p>
          <button onClick={onBack} className="text-indigo-600 text-sm underline">
            Go back
          </button>
        </div>
      </div>
    );
  }

  if (briefings.length === 0) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
        <div className="text-center space-y-3">
          <p className="text-gray-500 text-sm">No briefings yet.</p>
          <button onClick={onBack} className="text-indigo-600 text-sm underline">
            Save context first
          </button>
        </div>
      </div>
    );
  }

  // Group briefings by snapshot_id → sessions (newest first)
  const sessions = Object.values(
    briefings.reduce((acc, b) => {
      if (!acc[b.snapshot_id]) {
        acc[b.snapshot_id] = { snapshot_id: b.snapshot_id, created_at: b.created_at, projects: [] };
      }
      acc[b.snapshot_id].projects.push(b);
      return acc;
    }, {})
  ).sort((a, b) => b.snapshot_id - a.snapshot_id);

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Welcome back.</h1>
            <p className="text-gray-400 text-sm mt-1">
              {sessions.length} session{sessions.length !== 1 ? "s" : ""} saved
            </p>
          </div>
          <button
            onClick={onBack}
            className="text-sm text-indigo-600 hover:underline"
          >
            ← Pause screen
          </button>
        </div>

        {/* Sessions — newest first, separated by a dashed divider */}
        {sessions.map((session, i) => (
          <div key={session.snapshot_id}>
            <SessionEntry session={session} isLatest={i === 0} />
            {i < sessions.length - 1 && (
              <div className="mt-8 border-t border-dashed border-gray-200" />
            )}
          </div>
        ))}

      </div>
    </div>
  );
}
