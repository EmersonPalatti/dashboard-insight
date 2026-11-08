import { useState, type CSSProperties } from "react";

/**
 * Número que muda pouco (transitions.dev, subtle change). Só os dígitos que
 * mudaram cruzam: o antigo sai, o novo entra, no sentido da mudança. Leitores
 * de tela ouvem só o valor novo (o dígito antigo é aria-hidden).
 */
export function SubtleNumber({ value }: { value: number }) {
  const [shown, setShown] = useState({ value, prev: value, dir: 1, version: 0 });
  // ajuste durante o render (sem effect): o número novo já nasce com o sentido certo
  if (value !== shown.value) {
    setShown({ value, prev: shown.value, dir: value > shown.value ? 1 : -1, version: shown.version + 1 });
  }

  const next = String(shown.value);
  const prev = String(shown.prev);
  const sameLength = prev.length === next.length;

  // a key muda a cada valor novo: a árvore remonta e a animação recomeça
  return (
    <span key={shown.version} className="recorte-number" style={{ "--dir": shown.dir } as CSSProperties}>
      {[...next].map((ch, i) => {
        const changed = shown.version > 0 && (!sameLength || prev[i] !== ch);
        if (!changed) return ch;
        return (
          <span key={i} className="recorte-digit">
            {sameLength && (
              <span className="recorte-digit-old" aria-hidden>
                {prev[i]}
              </span>
            )}
            <span className="recorte-digit-new">{ch}</span>
          </span>
        );
      })}
    </span>
  );
}
