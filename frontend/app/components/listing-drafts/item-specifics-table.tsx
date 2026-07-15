type SpecificRow = {
  label: string;
  value: string;
};

const COMMON_SPECIFICS = [
  {
    label: "Game",
    aliases: ["game", "detectedgame", "tradingcardgame"],
  },
  { label: "Card Name", aliases: ["cardname", "name"] },
  { label: "Set", aliases: ["set", "setname"] },
  { label: "Card Number", aliases: ["cardnumber", "number"] },
  { label: "Rarity", aliases: ["rarity"] },
  {
    label: "Condition",
    aliases: ["condition", "conditionsummary", "conditionguess"],
  },
  { label: "Language", aliases: ["language"] },
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeKey(value: string): string {
  return value.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function displayValue(value: unknown): string | null {
  if (typeof value === "string") {
    return value.trim() || null;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value) && value.every((item) => typeof item === "string")) {
    return value.join(", ");
  }
  return null;
}

function humanizeKey(key: string): string {
  return key
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function findSpecificValue(
  records: Record<string, unknown>[],
  aliases: readonly string[],
): string | null {
  for (const record of records) {
    for (const [key, value] of Object.entries(record)) {
      if (aliases.includes(normalizeKey(key))) {
        const displayed = displayValue(value);
        if (displayed) return displayed;
      }
    }
  }
  return null;
}

export function itemSpecificRows(
  raw: Record<string, unknown>,
  fallback: Record<string, string>,
): SpecificRow[] {
  const nestedSpecifics = isRecord(raw.item_specifics) ? raw.item_specifics : {};
  const records = [nestedSpecifics, raw];
  const rows: SpecificRow[] = [];
  const knownAliases = new Set<string>(
    COMMON_SPECIFICS.flatMap((specific) => [...specific.aliases]),
  );
  const displayedLabels = new Set<string>();

  for (const specific of COMMON_SPECIFICS) {
    const value =
      findSpecificValue(records, specific.aliases) ??
      (specific.label === "Language" ? null : fallback[specific.label]);
    if (value) {
      rows.push({ label: specific.label, value });
      displayedLabels.add(normalizeKey(specific.label));
    }
  }

  const remainingEntries = [
    ...Object.entries(nestedSpecifics),
    ...Object.entries(raw).filter(
      ([key]) => !["itemspecifics", "keywords"].includes(normalizeKey(key)),
    ),
  ];
  for (const [key, value] of remainingEntries) {
    if (knownAliases.has(normalizeKey(key))) continue;
    const displayed = displayValue(value);
    const label = humanizeKey(key);
    if (displayed && !displayedLabels.has(normalizeKey(label))) {
      rows.push({ label, value: displayed });
      displayedLabels.add(normalizeKey(label));
    }
  }

  return rows;
}

export function draftKeywords(raw: Record<string, unknown>): string[] {
  if (!Array.isArray(raw.keywords)) return [];
  return Array.from(
    new Set(
      raw.keywords
        .filter(
          (keyword): keyword is string =>
            typeof keyword === "string" && keyword.trim().length > 0,
        )
        .map((keyword) => keyword.trim()),
    ),
  );
}

type ItemSpecificsTableProps = {
  specifics: SpecificRow[];
};

export function ItemSpecificsTable({ specifics }: ItemSpecificsTableProps) {
  return (
    <section className="mt-6">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-400">
        Item Specifics
      </h4>
      {specifics.length > 0 ? (
        <div className="mt-2 overflow-hidden rounded-lg border border-zinc-700">
          <table className="w-full table-fixed text-left text-sm">
            <tbody className="divide-y divide-zinc-800">
              {specifics.map((specific) => (
                <tr key={specific.label}>
                  <th
                    scope="row"
                    className="w-2/5 bg-zinc-950/60 px-3 py-2 align-top font-medium text-zinc-400"
                  >
                    {specific.label}
                  </th>
                  <td className="break-words px-3 py-2 text-zinc-200">
                    {specific.value}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-2 text-sm text-zinc-500">No item specifics available.</p>
      )}
    </section>
  );
}
