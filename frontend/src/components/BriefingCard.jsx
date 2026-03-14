import { useState } from "react";

export function BriefingCard({ title, children, collapsible = false }) {
  const [open, setOpen] = useState(true);

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div
        className={`flex items-center justify-between px-5 py-4 ${
          collapsible ? "cursor-pointer select-none" : ""
        }`}
        onClick={collapsible ? () => setOpen((o) => !o) : undefined}
      >
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider">
          {title}
        </h2>
        {collapsible && (
          <span className="text-gray-400 text-lg">{open ? "▲" : "▼"}</span>
        )}
      </div>
      {open && <div className="px-5 pb-5">{children}</div>}
    </div>
  );
}
