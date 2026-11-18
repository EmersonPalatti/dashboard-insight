import type { CSSProperties, ReactNode } from "react";
import { useCurrentFrame } from "remotion";
import { enter, progress } from "../anim";
import { COMANDA_01 } from "../data";
import { FAST, SANS, useTokens } from "../theme";
import { ActionBlock } from "./ActionBlock";
import { Button } from "./Button";
import { Ticket, TicketHeader } from "./Ticket";

/** Topo da comanda aberta no quadro (cenas 4 e 5). O título da cena 4 ocupa y 96–190. */
export const OPEN_TOP = 214;

const ACTION_FONT = 34;
const ACTION_LINE = Math.round(ACTION_FONT * 1.32); // 45 px
const ACTION_LABEL = 46; // rótulo "Ação" (30 px × 1,2) + margem 10
const GUTTER = 150;

/** Trecho marcado em `series` (fundo que varre da esquerda para a direita). */
const Mark = ({ at, children }: { readonly at?: number; readonly children: ReactNode }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const p = at === undefined ? 0 : progress(frame, at, FAST);
  return (
    <span
      style={{
        backgroundImage: `linear-gradient(${t.series}, ${t.series})`,
        backgroundRepeat: "no-repeat",
        backgroundSize: `${p * 100}% 100%`,
        borderRadius: 4,
        padding: "2px 6px",
        margin: "0 -6px",
      }}
    >
      {children}
    </span>
  );
};

/** Rótulo da anotação (onde / o quê / quando) na calha à direita do bloco Ação. */
const Note = ({ at, line, children }: { readonly at?: number; readonly line: number; readonly children: string }) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  if (at === undefined) return null;
  const style: CSSProperties = enter(frame, at + 3, { dist: -10, axis: "x", dur: FAST });
  return (
    <div
      style={{
        position: "absolute",
        right: 0,
        top: ACTION_LABEL + line * ACTION_LINE + (ACTION_LINE - 42) / 2,
        height: 42,
        display: "flex",
        alignItems: "center",
        gap: 10,
        ...style,
      }}
    >
      <span style={{ width: 22, height: 2, background: t.seriesSoft }} />
      <span
        style={{
          background: t.series,
          color: "#FFFFFF",
          fontFamily: SANS,
          fontWeight: 600,
          fontSize: 28,
          lineHeight: "42px",
          padding: "0 12px",
          borderRadius: 4,
        }}
      >
        {children}
      </span>
    </div>
  );
};

export type Comanda01Timing = {
  /** Frame local em que a comanda desdobra (280 ms). Omitir = já aberta. */
  printAt?: number;
  /** Entrada do diagnóstico. */
  detailAt?: number;
  /** Entrada do bloco Ação (300 ms depois do diagnóstico no roteiro). */
  actionAt?: number;
  buttonsAt?: number;
  /** Anotações onde / o quê / quando. Omitir = sem anotações. */
  annotate?: { where: number; what: number; when: number };
  /** Compressão de clique nos botões. */
  pressPrimaryAt?: number;
  pressChartAt?: number;
};

/**
 * Comanda Nº 01 aberta (cena 4, capa do post). As linhas do bloco Ação são
 * quebradas à mão para as anotações caírem em linhas conhecidas.
 */
export const Comanda01Open = ({
  timing = {},
  style,
}: {
  readonly timing?: Comanda01Timing;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  const frame = useCurrentFrame();
  const { printAt, detailAt, actionAt, buttonsAt, annotate, pressPrimaryAt, pressChartAt } = timing;
  const show = (at?: number, dist = 10) => (at === undefined ? {} : enter(frame, at, { dist }));
  const a = COMANDA_01.action;
  const line: CSSProperties = { whiteSpace: "nowrap" };

  return (
    <Ticket printAt={printAt} style={style}>
      <TicketHeader severity="high" label="Nº 01 · SLA" />
      <div style={{ fontSize: 44, fontWeight: 600, lineHeight: 1.15, marginBottom: 16 }}>{COMANDA_01.title}</div>
      <div style={{ fontSize: 32, lineHeight: 1.32, color: t.ink, marginBottom: 26, ...show(detailAt) }}>
        {COMANDA_01.detail}
      </div>
      <ActionBlock fontSize={ACTION_FONT} style={{ position: "relative", marginBottom: 26, ...show(actionAt) }}>
        <div style={{ width: `calc(100% - ${GUTTER}px)` }}>
          <div style={line}>
            {a.a}
            <Mark at={annotate?.where}>{a.where}</Mark>
            {a.b.trim()}
          </div>
          <div style={line}>
            <Mark at={annotate?.what}>revisar fila de coleta e</Mark>
          </div>
          <div style={line}>
            <Mark at={annotate === undefined ? undefined : annotate.what + 5}>posicionamento de entregadores</Mark>
          </div>
          <div style={line}>
            {a.c.trimStart()}
            <Mark at={annotate?.when}>{a.when}</Mark>.
          </div>
          <div style={line}>Meta: expedição abaixo da mediana</div>
          <div style={line}>do recorte.</div>
        </div>
        {/* Calha das anotações: posicionada em relação ao texto (padding 28 do ActionBlock). */}
        <div style={{ position: "absolute", top: 28, right: 28, bottom: 28, width: GUTTER }}>
          <Note at={annotate?.where} line={0}>onde</Note>
          <Note at={annotate?.what} line={1.5}>o quê</Note>
          <Note at={annotate?.when} line={3}>quando</Note>
        </div>
      </ActionBlock>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, ...show(buttonsAt, 6) }}>
        <Button variant="primary" pressAt={pressPrimaryAt}>
          {COMANDA_01.buttons.primary}
        </Button>
        <Button pressAt={pressChartAt}>{COMANDA_01.buttons.chart}</Button>
        <Button>{COMANDA_01.buttons.agent}</Button>
      </div>
    </Ticket>
  );
};
