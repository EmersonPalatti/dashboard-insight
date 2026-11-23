// Marcas de efeito sonoro do vídeo do agente (ainda sem áudio), no mesmo formato de src/sfx.ts.
// Cada cena exporta `sfx` com frames LOCAIS; aqui viram frames absolutos.
import type { SceneSfx } from "../sfx";
import { AGENT_SCENES } from "./timing";
import * as a01 from "./scenes/A01Hook";
import * as a02 from "./scenes/A02Before";
import * as a03 from "./scenes/A03Semantic";
import * as a04 from "./scenes/A04Graph";
import * as a05 from "./scenes/A05March";
import * as a06 from "./scenes/A06Progressive";
import * as a07 from "./scenes/A07Evals";
import * as a08 from "./scenes/A08Summary";

const byScene: [keyof typeof AGENT_SCENES, SceneSfx[]][] = [
  ["a01Hook", a01.sfx],
  ["a02Before", a02.sfx],
  ["a03Semantic", a03.sfx],
  ["a04Graph", a04.sfx],
  ["a05March", a05.sfx],
  ["a06Progressive", a06.sfx],
  ["a07Evals", a07.sfx],
  ["a08Summary", a08.sfx],
];

/** Todos os efeitos com frame absoluto, em ordem. */
export const AGENT_SFX = byScene
  .flatMap(([scene, list]) => list.map((e) => ({ ...e, frame: e.frame + AGENT_SCENES[scene].from, scene })))
  .sort((a, b) => a.frame - b.frame);
