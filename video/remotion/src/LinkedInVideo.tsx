import { AbsoluteFill, Sequence, Track } from "remotion";
import { FadeOut } from "./components/FadeOut";
import { S01Hook } from "./scenes/S01Hook";
import { S02Intro } from "./scenes/S02Intro";
import { S03Comandas } from "./scenes/S03Comandas";
import { S04Open } from "./scenes/S04Open";
import { S05Investigation } from "./scenes/S05Investigation";
import { S06Drill } from "./scenes/S06Drill";
import { S07Agent } from "./scenes/S07Agent";
import { S08Data } from "./scenes/S08Data";
import { S09Automation } from "./scenes/S09Automation";
import { S10Stack } from "./scenes/S10Stack";
import { S11Close } from "./scenes/S11Close";
import { LIGHT, SANS } from "./theme";

/** Vídeo completo (58 s). Frames de cada cena: src/timing.ts (SCENES). */
export const LinkedInVideo = () => (
  <AbsoluteFill style={{ background: LIGHT.field, fontFamily: SANS }}>
    <Track name="Cenas">
      <Sequence name="1 · Gancho" durationInFrames={150}>
        <S01Hook />
      </Sequence>
      <Sequence name="2 · Apresentação" from={150} durationInFrames={150}>
        <FadeOut duration={150}>
          <S02Intro />
        </FadeOut>
      </Sequence>
      <Sequence name="3 · Comandas" from={300} durationInFrames={180}>
        <S03Comandas />
      </Sequence>
      <Sequence name="4 · Comanda aberta" from={480} durationInFrames={210}>
        <S04Open />
      </Sequence>
      <Sequence name="5 · Investigação" from={690} durationInFrames={150}>
        <S05Investigation />
      </Sequence>
      <Sequence name="6 · Drill-down" from={840} durationInFrames={150}>
        <S06Drill />
      </Sequence>
      <Sequence name="7 · Agente" from={990} durationInFrames={240}>
        <FadeOut duration={240}>
          <S07Agent />
        </FadeOut>
      </Sequence>
      <Sequence name="8 · Cuidado com o dado" from={1230} durationInFrames={120}>
        <FadeOut duration={120}>
          <S08Data />
        </FadeOut>
      </Sequence>
      <Sequence name="9 · Automação" from={1350} durationInFrames={180}>
        <FadeOut duration={180}>
          <S09Automation />
        </FadeOut>
      </Sequence>
      <Sequence name="10 · Stack" from={1530} durationInFrames={120}>
        <S10Stack />
      </Sequence>
      <Sequence name="11 · Fechamento" from={1650} durationInFrames={90}>
        <S11Close />
      </Sequence>
    </Track>
  </AbsoluteFill>
);
