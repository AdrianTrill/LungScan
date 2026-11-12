import Dialog from "../ui/Dialog";

const GROUPS: { title: string; keys: [string, string][] }[] = [
  {
    title: "Anywhere",
    keys: [
      ["?", "Show these shortcuts"],
      ["T", "Switch between the dark and light themes"],
      ["N", "New study (worklist and patient pages)"],
      ["/", "Search the worklist"],
    ],
  },
  {
    title: "Worklist",
    keys: [
      ["J  K", "Next / previous study"],
      ["Enter", "Open the selected study"],
    ],
  },
  {
    title: "Reading a study",
    keys: [
      ["A", "Analyze the slice (again)"],
      ["[  ]", "Previous / next study in the worklist"],
      ["H", "Heat map on or off"],
      ["R", "Regions on or off"],
      ["I", "Invert"],
      ["P  W", "Drag pans / drag sets window and level"],
      ["+  -", "Zoom in / out"],
      ["F", "Fit the slice to the viewer"],
      ["0", "Reset zoom, window, and inversion"],
      ["E", "Export the report"],
    ],
  },
];

export default function ShortcutsDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <Dialog open={open} onClose={onClose} title="Keyboard shortcuts" wide>
      <div className="grid gap-6 sm:grid-cols-2">
        {GROUPS.map((group) => (
          <section
            key={group.title}
            className={group.title === "Reading a study" ? "sm:row-span-2" : ""}
          >
            <h3 className="eyebrow mb-2">{group.title}</h3>
            <dl className="space-y-1.5">
              {group.keys.map(([key, what]) => (
                <div key={key} className="flex items-center justify-between gap-4">
                  <dt className="text-[12.5px] text-ink-2">{what}</dt>
                  <dd className="flex flex-none gap-1">
                    {key.split("  ").map((k) => (
                      <kbd key={k} className="kbd">
                        {k}
                      </kbd>
                    ))}
                  </dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
