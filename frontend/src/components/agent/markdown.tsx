import type { ReactNode } from "react";

/**
 * Um tokenizador para o markdown inline. Ordem importa: código, negrito, depois itálico.
 * _itálico_ só abre e fecha em fronteira de palavra, então snake_case fica intacto.
 */
const INLINE =
  /`([^`\n]+)`|\*\*([^*\n]+?)\*\*|(?<![\p{L}\p{N}])_([^_\s](?:[^_\n]*[^_\s])?)_(?![\p{L}\p{N}])|\*([^*\s](?:[^*\n]*[^*\s])?)\*/gu;

/** Markdown inline como ReactNode, sem innerHTML. Asterisco solto ("5 * 3") continua literal. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0;
  for (const match of text.matchAll(INLINE)) {
    const at = match.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    const key = out.length;
    const [, code, bold, underscore, star] = match;
    if (code !== undefined) {
      out.push(
        <code key={key} className="rounded-[4px] bg-sunken px-1 text-[0.9em]">
          {code}
        </code>,
      );
    } else if (bold !== undefined) {
      out.push(<strong key={key}>{inline(bold)}</strong>);
    } else {
      out.push(<em key={key}>{inline(underscore ?? star)}</em>);
    }
    last = at + match[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** Remove os marcadores inline, mantendo o conteúdo. */
function stripMarks(text: string): string {
  return text.replace(INLINE, (_match, code, bold, underscore, star) => code ?? stripMarks(bold ?? underscore ?? star));
}

/** Texto puro para leitor de tela: sem marcadores, títulos, marcas de lista ou tabela. */
export function plainText(md: string): string {
  const flat = md
    .replace(/^\s*(?:#{1,4}\s+|[-*•]\s+|\d+\.\s+)/gm, "")
    .replace(/^\s*\|[\s:|-]+\|\s*$/gm, "")
    .replace(/\|/g, " ");
  return stripMarks(flat).replace(/\s+/g, " ").trim();
}

export function clip(text: string, max = 200): string {
  return text.length > max ? `${text.slice(0, max).trimEnd()}…` : text;
}

/** Lista numerada continua `<ol>`. Traço vira `<ul>`. As duas não se misturam no mesmo bloco. */
export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const ListTag = list.ordered ? "ol" : "ul";
    const items = list.items;
    blocks.push(
      <ListTag key={`list-${blocks.length}`} className={`ml-4 space-y-0.5 ${list.ordered ? "list-decimal" : "list-disc"}`}>
        {items.map((item, index) => (
          <li key={index}>{inline(item)}</li>
        ))}
      </ListTag>,
    );
    list = null;
  };
  let table: string[][] = [];
  const flushTable = () => {
    if (!table.length) return;
    const [head, ...body] = table;
    blocks.push(
      <div key={`t-${blocks.length}`} className="overflow-x-auto">
        <table className="w-full text-aux tabular-nums">
          <thead>
            <tr>
              {head.map((cell, index) => (
                <th key={index} className="border-b border-rule px-1.5 py-1 text-left font-semibold">
                  {inline(cell)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {body.map((row, index) => (
              <tr key={index}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="border-b border-rule/60 px-1.5 py-1">
                    {inline(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>,
    );
    table = [];
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    if (/^\s*\|.*\|\s*$/.test(line)) {
      flush();
      if (!/^\s*\|[\s:|-]+\|\s*$/.test(line)) table.push(line.trim().slice(1, -1).split("|").map((cell) => cell.trim()));
      continue;
    }
    flushTable();
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(line)) continue;
    const item = line.match(/^\s*(?:([-*•])|(\d+)\.)\s+(.*)$/);
    if (item) {
      const ordered = item[2] !== undefined;
      if (list && list.ordered !== ordered) flush();
      list = list ?? { ordered, items: [] };
      list.items.push(item[3]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const heading = line.match(/^#{1,4}\s+(.*)$/);
    blocks.push(
      <p key={`p-${blocks.length}`} className={heading ? "font-semibold" : ""}>
        {inline(heading ? heading[1] : line)}
      </p>,
    );
  }
  flush();
  flushTable();
  return <div className="space-y-1.5">{blocks}</div>;
}

export function readingNote(status: "rules" | "upgraded" | "cancelled" | "failed", toolLabels: string[]): string {
  if (status === "cancelled") return "Leitura do modelo cancelada. Vale a leitura pelas regras.";
  if (status === "failed") return "A leitura do modelo não chegou. Vale a leitura pelas regras.";
  if (status === "upgraded") {
    return toolLabels.length
      ? `Leitura do modelo. Consultou: ${toolLabels.join(", ")}.`
      : "Leitura do modelo com o contexto do recorte.";
  }
  return "Leitura pelas regras.";
}
