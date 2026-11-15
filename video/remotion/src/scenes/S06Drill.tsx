import { AbsoluteFill, useCurrentFrame } from "remotion";
import { enter, exit, mergeStyles } from "../anim";
import { Cursor } from "../components/Cursor";
import { FilterChip } from "../components/FilterChip";
import { InvestigationStrip, STRIP_HEIGHT, STRIP_PRIMARY_CENTER, STRIP_TOP } from "../components/s05-InvestigationStrip";
import { StagesChart } from "../components/s05-StagesChart";
import { KpiCard } from "../components/s06-KpiCard";
import { Caption, SceneTitle } from "../components/Text";
import { KPIS } from "../data";
import type { SceneSfx } from "../sfx";
import { ms, SANS, SIDE, STAGE, STAGGER, useTokens } from "../theme";

const S06 = {
  cursorAppear: 1,
  cursorMove: 3,
  cursorDur: ms(380),
  click: 16,
  cursorHide: 24,
  prevExit: 18,
  titleOut: 25,
  titleIn: 23,
  filterIn: 22,
  kpisIn: 24,
  rollAt: [46, 49, 52] as const,
  captionIn: 50,
  sceneOut: 144,
  outDur: ms(200), // 6 frames (144–150)
};

/** Efeitos sonoros desta cena (frames locais). */
export const sfx: SceneSfx[] = [
  { frame: S06.click, kind: "clique" },
  { frame: S06.rollAt[0], kind: "tick" },
  { frame: S06.rollAt[1], kind: "tick" },
  { frame: S06.rollAt[2], kind: "tick" },
];

/** Cena 6: Drill-down. Clique em "Ver só Color Shopping" filtra KPIs, gráficos e vereditos. */
export const S06Drill = () => {
  const t = useTokens();
  const frame = useCurrentFrame();

  const prevExitStyle = exit(frame, S06.prevExit, { dur: ms(200), dist: -10 });
  const showPrev = frame < S06.prevExit + ms(200);

  const stageOutStyle = exit(frame, S06.sceneOut, { dur: S06.outDur, dist: -10 });
  const filterStyle = mergeStyles(enter(frame, S06.filterIn, { dist: 8, dur: ms(260) }), stageOutStyle);

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Costura com o fim da cena 5: tira do topo + gráfico destacado; sai após o clique */}
      {showPrev ? (
        <>
          <InvestigationStrip pressPrimaryAt={S06.click} style={prevExitStyle} />
          <StagesChart
            barsAt={-100}
            highlightAt={-100}
            style={{
              position: "absolute",
              left: SIDE,
              top: STRIP_TOP + STRIP_HEIGHT + 16,
              ...prevExitStyle,
            }}
          />
        </>
      ) : null}

      {/* Barra de filtro ativo: chip "Hub Color Shopping ×" + link "Desfazer filtro" */}
      {frame >= S06.filterIn ? (
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: STAGE.top,
            display: "flex",
            alignItems: "center",
            gap: 22,
            ...filterStyle,
          }}
        >
          <FilterChip label="Hub" value="Color Shopping" />
          <span
            style={{
              fontFamily: SANS,
              fontSize: 28,
              fontWeight: 500,
              color: t.muted,
              textDecoration: "underline",
              textUnderlineOffset: 5,
            }}
          >
            Desfazer filtro
          </span>
        </div>
      ) : null}

      {/* Três cartões KPI em coluna larga */}
      {frame >= S06.kpisIn ? (
        <div
          style={{
            position: "absolute",
            left: SIDE,
            top: STAGE.top + 76,
            display: "flex",
            flexDirection: "column",
            gap: 18,
          }}
        >
          {KPIS.map((kpi, i) => {
            const cardEnter = enter(frame, S06.kpisIn + i * STAGGER * 2, { dist: 12, dur: ms(280) });
            const cardStyle = mergeStyles(cardEnter, stageOutStyle);
            return <KpiCard key={kpi.label} kpi={kpi} rollAt={S06.rollAt[i]} style={cardStyle} />;
          })}
        </div>
      ) : null}

      {/* Títulos e legenda */}
      {frame < S06.titleOut ? (
        <SceneTitle from={-100} to={S06.titleOut} style={{ top: 96, height: 180, justifyContent: "flex-start" }}>
          O gráfico que prova a comanda sobe sozinho.
        </SceneTitle>
      ) : null}
      <SceneTitle from={S06.titleIn} to={150}>
        Um clique filtra tudo.
      </SceneTitle>

      <Caption from={S06.captionIn} to={150} size={32}>
        KPIs, gráficos, alertas e agente no mesmo recorte.
      </Caption>

      <Cursor
        from={{ x: 640, y: 560 }}
        to={STRIP_PRIMARY_CENTER}
        appearAt={S06.cursorAppear}
        moveStart={S06.cursorMove}
        moveDur={S06.cursorDur}
        clickAt={S06.click}
        hideAt={S06.cursorHide}
      />
    </AbsoluteFill>
  );
};
