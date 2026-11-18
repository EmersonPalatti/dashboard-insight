import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { Comanda01Open, OPEN_TOP } from "../components/Comanda01Open";
import { Cursor } from "../components/Cursor";
import { InvestigationStrip, STRIP_HEIGHT, STRIP_TOP } from "../components/s05-InvestigationStrip";
import { StagesChart } from "../components/s05-StagesChart";
import { SceneTitle } from "../components/Text";
import type { SceneSfx } from "../sfx";
import { EASE_IN, ms, SIDE, useTokens } from "../theme";
import { local } from "../timing";

/** Centro aproximado do botão "Ver no gráfico" no quadro (cena 4 → cena 5). */
const CHART_BTN = { x: 586, y: 979 };

const S05 = {
  cursorAppear: 1,
  cursorMove: 3,
  cursorDur: ms(380),
  click: 16,
  cursorHide: 24,
  comandaExit: 20,
  comandaExitDur: ms(220),
  titleOut: 26,
  titleIn: 24,
  stripIn: 22,
  chartIn: 28,
  barsAt: 36,
  highlightAt: local("s05Investigation", 25.5), // frame local 75
};

/** Efeitos sonoros desta cena (frames locais). */
export const sfx: SceneSfx[] = [{ frame: S05.click, kind: "clique" }];

/** Cena 5: Investigação. Clique em "Ver no gráfico" revela o gráfico de etapas por hub. */
export const S05Investigation = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const comandaExitP = progress(frame, S05.comandaExit, S05.comandaExitDur, EASE_IN);
  const showComanda = comandaExitP < 1;

  const stripStyle = enter(frame, S05.stripIn, { dist: -10, dur: ms(280) });
  const chartStyle = enter(frame, S05.chartIn, { dist: 14, dur: ms(320) });

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Frame 0 idêntico ao fim da cena 4; sai após o clique em "Ver no gráfico". */}
      {showComanda ? (
        <Comanda01Open
          timing={{
            annotate: { where: -100, what: -100, when: -100 },
            pressChartAt: S05.click,
          }}
          style={{
            position: "absolute",
            left: SIDE,
            top: OPEN_TOP,
            opacity: 1 - comandaExitP,
            scale: interpolate(comandaExitP, [0, 1], [1, 0.95]),
            translate: `0px ${interpolate(comandaExitP, [0, 1], [0, -28])}px`,
            filter: comandaExitP > 0 ? `blur(${comandaExitP * 2}px)` : undefined,
          }}
        />
      ) : null}

      {/* Tira do topo + gráfico "Onde o tempo vai, por hub" */}
      {frame >= S05.stripIn ? <InvestigationStrip style={stripStyle} /> : null}

      {frame >= S05.chartIn ? (
        <StagesChart
          barsAt={S05.barsAt}
          highlightAt={S05.highlightAt}
          style={{
            position: "absolute",
            left: SIDE,
            top: STRIP_TOP + STRIP_HEIGHT + 16,
            ...chartStyle,
          }}
        />
      ) : null}

      {/* Troca de título: cena 4 sai, cena 5 entra */}
      {frame < S05.titleOut ? (
        <SceneTitle from={-100} to={S05.titleOut} style={{ top: 96, height: 100, justifyContent: "flex-start" }}>
          Problema, número e ação.
        </SceneTitle>
      ) : null}
      <SceneTitle from={S05.titleIn} style={{ top: 96, height: 180, justifyContent: "flex-start" }}>
        O gráfico que prova a comanda sobe sozinho.
      </SceneTitle>

      <Cursor
        from={{ x: 840, y: 1120 }}
        to={CHART_BTN}
        appearAt={S05.cursorAppear}
        moveStart={S05.cursorMove}
        moveDur={S05.cursorDur}
        clickAt={S05.click}
        hideAt={S05.cursorHide}
      />
    </AbsoluteFill>
  );
};
