import { Composition, Folder } from "remotion";
import { AgentVideo } from "./agente/AgentVideo";
import { A01Hook } from "./agente/scenes/A01Hook";
import { A02Before } from "./agente/scenes/A02Before";
import { A03Semantic } from "./agente/scenes/A03Semantic";
import { A04Graph } from "./agente/scenes/A04Graph";
import { A05March } from "./agente/scenes/A05March";
import { A06Progressive } from "./agente/scenes/A06Progressive";
import { A07Evals } from "./agente/scenes/A07Evals";
import { A08Summary } from "./agente/scenes/A08Summary";
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

// Composições principais + cada cena isolada (mesmas durações de src/timing.ts e src/agente/timing.ts) para revisar no Studio.
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
    <Composition id="Agente" component={AgentVideo} durationInFrames={1800} fps={30} width={1080} height={1350} />
    <Folder name="Cenas-Agente">
      <Composition id="A01-Gancho" component={A01Hook} durationInFrames={150} fps={30} width={1080} height={1350} />
      <Composition id="A02-Antes" component={A02Before} durationInFrames={180} fps={30} width={1080} height={1350} />
      <Composition id="A03-CamadaSemantica" component={A03Semantic} durationInFrames={210} fps={30} width={1080} height={1350} />
      <Composition id="A04-Grafo" component={A04Graph} durationInFrames={300} fps={30} width={1080} height={1350} />
      <Composition id="A05-MarcoReal" component={A05March} durationInFrames={210} fps={30} width={1080} height={1350} />
      <Composition id="A06-RespostaLimites" component={A06Progressive} durationInFrames={240} fps={30} width={1080} height={1350} />
      <Composition id="A07-Placar" component={A07Evals} durationInFrames={240} fps={30} width={1080} height={1350} />
      <Composition id="A08-AntesAgora" component={A08Summary} durationInFrames={150} fps={30} width={1080} height={1350} />
    </Folder>
  </>
);
