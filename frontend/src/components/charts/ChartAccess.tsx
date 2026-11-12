import { requestStoreRankingFocus } from "@/lib/filters";
import { prefersReducedMotion } from "@/lib/media";

interface Item {
  key: string;
  label: string;
  onSelect: () => void;
}

/**
 * Equivalente de teclado de um filtro que o gráfico só faz com o mouse.
 * Os botões ficam fora da tela até receberem foco; Tab e Enter disparam a ação.
 */
export function ChartAccess({ summary, items }: { summary: string; items: Item[] }) {
  if (!summary && items.length === 0) return null;
  return (
    <div className="mt-2">
      {summary && <p className="sr-only">{summary}</p>}
      {items.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="Filtrar pelo teclado">
          {items.map((item) => (
            <li key={item.key}>
              <button type="button" className="chart-key btn-ghost sr-only text-left" onClick={item.onSelect}>
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
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

