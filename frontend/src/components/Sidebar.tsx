import Link from "next/link";

const links = [
  { href: "/", label: "Overview" },
  { href: "/runs", label: "Runs" },
  { href: "/agents", label: "Agents" },
  { href: "/documents", label: "Documents" },
];

export function Sidebar() {
  return (
    <aside className="w-52 bg-neutral-900 border-r border-neutral-800 flex flex-col p-4 gap-1 shrink-0">
      <div className="mb-6 px-2">
        <span className="text-lg font-bold tracking-tight">Hive</span>
      </div>
      {links.map((l) => (
        <Link
          key={l.href}
          href={l.href}
          className="px-3 py-2 rounded-md text-sm text-neutral-300 hover:bg-neutral-800 hover:text-white transition-colors"
        >
          {l.label}
        </Link>
      ))}
    </aside>
  );
}
