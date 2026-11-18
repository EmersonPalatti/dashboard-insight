import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { exit, progress } from "../anim";
import { Comanda01Open, OPEN_TOP } from "../components/Comanda01Open";
import { StackHeader } from "../components/StackHeader";
import { SceneTitle } from "../components/Text";
import { TicketStub, PRINT_DUR } from "../components/Ticket";
import { COMANDAS, stubTop } from "../data";
import type { SceneSfx } from "../sfx";
import { ms, SIDE, STAGGER, useTokens } from "../theme";

/** Frames locais da cena 4 (0:16–0:23). Também usados pela cena 5 e pela capa (0:19 = local 90). */
export const S04 = {
  othersExit: 0, // as outras comandas somem para cima em 150 ms
  lift: 4, // a Nº 01 sobe até o topo do palco
  liftDur: 10,
  unfold: 14, // desdobra (280 ms)
  title: 8,
  detail: 14 + PRINT_DUR,
  action: 14 + PRINT_DUR + ms(300),
  buttons: 14 + PRINT_DUR + ms(300) + ms(250),
  // Anotações 0:19,5–0:23 → locais 105, 120, 135.
  annotate: { where: 105, what: 120, when: 135 },
};

export const sfx: SceneSfx[] = [{ frame: S04.unfold, kind: "impressora" }];

/** Cena 4: a comanda aberta. Problema, número e ação: quem faz o quê, onde e quando. */
export const S04Open = () => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const first = COMANDAS[0];
  const others = COMANDAS.slice(1);
  const lift = progress(frame, S04.lift, S04.liftDur);
  const stubFade = interpolate(frame, [S04.unfold, S04.unfold + 4], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ background: t.field }}>
      {/* Pilha herdada da cena 3: cabeçalho e comandas 02–06 saem para cima. */}
      {frame < 12 ? (
        <>
          <StackHeader style={exit(frame, S04.othersExit, { dur: ms(150), dist: -24 })} />
          {others.map((c, i) => (
            <TicketStub
              key={c.number}
              {...c}
              style={{
                position: "absolute",
                left: SIDE,
                top: stubTop(i + 1),
                ...exit(frame, S04.othersExit + i * STAGGER, { dur: ms(150), dist: -24 }),
              }}
            />
          ))}
        </>
      ) : null}

      {/* A Nº 01 sobe e dá lugar à versão aberta. */}
      {stubFade > 0 ? (
        <TicketStub
          {...first}
          style={{
            position: "absolute",
            left: SIDE,
            top: interpolate(lift, [0, 1], [stubTop(0), OPEN_TOP]),
            opacity: stubFade,
          }}
        />
      ) : null}

      {frame >= S04.unfold ? (
        <Comanda01Open
          timing={{
            printAt: S04.unfold,
            detailAt: S04.detail,
            actionAt: S04.action,
            buttonsAt: S04.buttons,
            annotate: S04.annotate,
          }}
          style={{ position: "absolute", left: SIDE, top: OPEN_TOP }}
        />
      ) : null}

      <SceneTitle from={S04.title} style={{ top: 96, height: 100, justifyContent: "flex-start" }}>
        Problema, número e ação.
      </SceneTitle>
    </AbsoluteFill>
  );
};
