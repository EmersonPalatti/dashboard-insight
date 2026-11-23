import { AbsoluteFill, Sequence, Track } from "remotion";
import { FadeOut } from "../components/FadeOut";
import { S11Close } from "../scenes/S11Close";
import { LIGHT, SANS } from "../theme";
import { CLOSE_FOOTER } from "./data";
import { A01Hook } from "./scenes/A01Hook";
import { A02Before } from "./scenes/A02Before";
import { A03Semantic } from "./scenes/A03Semantic";
import { A04Graph } from "./scenes/A04Graph";
import { A05March } from "./scenes/A05March";
import { A06Progressive } from "./scenes/A06Progressive";
import { A07Evals } from "./scenes/A07Evals";
import { A08Summary } from "./scenes/A08Summary";

/** Vídeo do agente (60 s). Frames de cada cena: src/agente/timing.ts (AGENT_SCENES). */
export const AgentVideo = () => (
  <AbsoluteFill style={{ background: LIGHT.field, fontFamily: SANS }}>
    <Track name="Cenas">
      <Sequence name="1 · Gancho" durationInFrames={150}>
        <A01Hook />
      </Sequence>
      <Sequence name="2 · Antes" from={150} durationInFrames={180}>
        <FadeOut duration={180}>
          <A02Before />
        </FadeOut>
      </Sequence>
      <Sequence name="3 · Camada semântica" from={330} durationInFrames={210}>
        <FadeOut duration={210}>
          <A03Semantic />
        </FadeOut>
      </Sequence>
      <Sequence name="4 · Grafo" from={540} durationInFrames={300}>
        <FadeOut duration={300}>
          <A04Graph />
        </FadeOut>
      </Sequence>
      <Sequence name="5 · Março real" from={840} durationInFrames={210}>
        <FadeOut duration={210}>
          <A05March />
        </FadeOut>
      </Sequence>
      <Sequence name="6 · Resposta e limites" from={1050} durationInFrames={240}>
        <FadeOut duration={240}>
          <A06Progressive />
        </FadeOut>
      </Sequence>
      <Sequence name="7 · Placar" from={1290} durationInFrames={240}>
        <FadeOut duration={240}>
          <A07Evals />
        </FadeOut>
      </Sequence>
      <Sequence name="8 · Antes e agora" from={1530} durationInFrames={150}>
        <A08Summary />
      </Sequence>
      <Sequence name="9 · Fechamento" from={1680} durationInFrames={120}>
        <S11Close footer={CLOSE_FOOTER} />
      </Sequence>
    </Track>
  </AbsoluteFill>
);
