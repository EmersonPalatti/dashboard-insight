import { useRef, useState, type KeyboardEvent } from "react";
import { requestStoreRankingFocus } from "@/lib/filters";
import { prefersReducedMotion } from "@/lib/media";

interface Item {
  key: string;
  label: string;
  onSelect: () => void;
}

/**
 * Equivalente de teclado de um filtro que o gráfico só faz com o mouse.
 * Os botões ficam fora da tela até receberem foco; um único ponto de Tab usa setas entre os itens e Enter dispara a ação.
 */
export function ChartAccess({ summary, items }: { summary: string; items: Item[] }) {
  const [cursor, setCursor] = useState(0);
  const btnRefs = useRef<(HTMLButtonElement | null)[]>([]);
  if (!summary && items.length === 0) return null;

  const safeCursor = items.length === 0 ? 0 : Math.min(cursor, items.length - 1);

  const onListKeyDown = (e: KeyboardEvent<HTMLUListElement>) => {
    if (items.length <= 1) return;
    let next = safeCursor;
    if (e.key === "ArrowDown" || e.key === "ArrowRight") next = (safeCursor + 1) % items.length;
    else if (e.key === "ArrowUp" || e.key === "ArrowLeft") next = (safeCursor - 1 + items.length) % items.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = items.length - 1;
    else return;
    e.preventDefault();
    setCursor(next);
    btnRefs.current[next]?.focus();
  };

  return (
    <>
      {summary && <p className="sr-only">{summary}</p>}
      {items.length > 0 && (
        <ul className="flex flex-col gap-1 focus-within:mt-2" aria-label="Filtrar pelo teclado" onKeyDown={onListKeyDown}>
          {items.map((item, index) => (
            <li key={item.key}>
              <button
                ref={(el) => {
                  btnRefs.current[index] = el;
                }}
                type="button"
                tabIndex={index === safeCursor ? 0 : -1}
                className="chart-key btn-ghost sr-only text-left"
                onFocus={() => setCursor(index)}
                onClick={item.onSelect}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/**
 * Leva o foco ao ranking em Lojas. O gráfico de dispersão tem lojas demais
 * para repetir cada uma como botão; a tabela já filtra uma loja por linha.
 */
export function openStoreRanking() {
  requestStoreRankingFocus();
  document.getElementById("painel-ranking-do-recorte")?.scrollIntoView({
    behavior: prefersReducedMotion() ? "auto" : "smooth",
    block: "start",
  });
}

