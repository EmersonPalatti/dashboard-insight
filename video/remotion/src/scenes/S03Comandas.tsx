import { AbsoluteFill, useCurrentFrame } from "remotion";
import { between, enter } from "../anim";
import { SeverityMark } from "../components/SeverityMark";
import { StackHeader } from "../components/StackHeader";
import { Caption, SceneTitle } from "../components/Text";
import { TicketStub } from "../components/Ticket";
import { COMANDAS, STACK, stubTop } from "../data";
import type { SceneSfx } from "../sfx";
import { SANS, SIDE, STAGGER, useTokens } from "../theme";
import { local } from "../timing";

const PRINT_START = 14;
const printAt = (i: number) => PRINT_START + i * STAGGER;
const LEGEND_START = local("s03Comandas", 13); // frame local 90

export const sfx: SceneSfx[] = COMANDAS.map((_, i) => ({
  frame: printAt(i),
  kind: "tick",
}));

/** Cena 3: As comandas (0:10–0:16). Fila de 6 comandas fechadas com costura exata para a Cena 4. */
export const S03Comandas = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Título 64 px (sai nos últimos 6 frames para a costura com a Cena 4) */}
      <SceneTitle from={0} to={179} size={64}>
        Cada alerta vira uma comanda.
      </SceneTitle>

      {/* Cabeçalho da pilha: no frame 179 fica exatamente na posição padrão sem transformação */}
      <StackHeader style={frame < 16 ? enter(frame, 4, { dist: 8 }) : undefined} />

      {/* Contagem à direita na mesma linha do StackHeader; sai em 174–179 */}
      <div
        style={{
          position: "absolute",
          right: SIDE,
          top: STACK.headerTop,
          height: 36,
          display: "flex",
          alignItems: "center",
          fontFamily: SANS,
          fontWeight: 500,
          fontSize: 28,
          lineHeight: "36px",
          color: t.muted,
          ...between(frame, 4, 179, { enter: { dist: 8 }, exit: { dur: 5 } }),
        }}
      >
        3 críticas · 3 em atenção
      </div>

      {/* Seis comandas fechadas em coluna */}
      {COMANDAS.map((c, i) => (
        <TicketStub
          key={c.number}
          {...c}
          printAt={printAt(i)}
          style={{
            position: "absolute",
            left: SIDE,
            top: stubTop(i),
          }}
        />
      ))}

      {/* Legenda de severidade a partir de 0:13 (frame local 90), sai em 174–179 */}
      <Caption from={LEGEND_START} to={179} size={32} align="center">
        <span style={{ display: "inline-flex", alignItems: "center", gap: 40 }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
            <SeverityMark severity="high" scale={2.2} />
            <span>crítico</span>
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
            <SeverityMark severity="medium" scale={2.2} />
            <span>atenção</span>
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
            <SeverityMark severity="low" scale={2.2} />
            <span>observar</span>
          </span>
        </span>
      </Caption>
    </AbsoluteFill>
  );
};
