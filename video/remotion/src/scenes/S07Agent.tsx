import { AbsoluteFill } from "remotion";
import { AgentPanel, S07_TIMING } from "../components/s07-AgentPanel";
import { Caption, SceneTitle } from "../components/Text";
import type { SceneSfx } from "../sfx";
import { SIDE, STAGE, useTokens } from "../theme";

/** Efeitos sonoros da cena 7 (frames locais). */
export const sfx: SceneSfx[] = [
  { frame: S07_TIMING.sendAt, kind: "clique" },
  { frame: S07_TIMING.printAt, kind: "impressora" },
];

/** Cena 7 (0:33–0:41, locais 0–240): agente do recorte com tool calling e resposta como comanda. */
export const S07Agent = () => {
  const t = useTokens();
  return (
    <AbsoluteFill style={{ background: t.field }}>
      <SceneTitle from={0} to={120} size={64}>
        Um agente que só vê o recorte filtrado.
      </SceneTitle>

      <AgentPanel style={{ position: "absolute", left: SIDE, top: STAGE.top }} />

      <Caption from={120} size={36}>
        LLM com tool calling. Sem API key, responde por regras locais.
      </Caption>
    </AbsoluteFill>
  );
};
