import { Composition, Folder } from "remotion";
import { LinkedInVideo } from "./LinkedInVideo";
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

// Composição principal + cada cena isolada (mesmas durações de src/timing.ts) para revisar no Studio.
export const RemotionRoot = () => (
  <>
    <Composition id="LinkedIn" component={LinkedInVideo} durationInFrames={1740} fps={30} width={1080} height={1350} />
    <Folder name="Cenas">
      <Composition id="S01-Gancho" component={S01Hook} durationInFrames={150} fps={30} width={1080} height={1350} />
      <Composition id="S02-Apresentacao" component={S02Intro} durationInFrames={150} fps={30} width={1080} height={1350} />
      <Composition id="S03-Comandas" component={S03Comandas} durationInFrames={180} fps={30} width={1080} height={1350} />
      <Composition id="S04-ComandaAberta" component={S04Open} durationInFrames={210} fps={30} width={1080} height={1350} />
      <Composition id="S05-Investigacao" component={S05Investigation} durationInFrames={150} fps={30} width={1080} height={1350} />
      <Composition id="S06-DrillDown" component={S06Drill} durationInFrames={150} fps={30} width={1080} height={1350} />
      <Composition id="S07-Agente" component={S07Agent} durationInFrames={240} fps={30} width={1080} height={1350} />
      <Composition id="S08-Dado" component={S08Data} durationInFrames={120} fps={30} width={1080} height={1350} />
      <Composition id="S09-Automacao" component={S09Automation} durationInFrames={180} fps={30} width={1080} height={1350} />
      <Composition id="S10-Stack" component={S10Stack} durationInFrames={120} fps={30} width={1080} height={1350} />
      <Composition id="S11-Fechamento" component={S11Close} durationInFrames={90} fps={30} width={1080} height={1350} />
    </Folder>
  </>
);
