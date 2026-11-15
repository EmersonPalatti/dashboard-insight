// Marcas de efeito sonoro para quando houver trilha e SFX (ainda sem áudio).
// Cada cena exporta `sfx` com frames LOCAIS; aqui viram frames absolutos.
// Arquivos esperados em public/audio/: trilha.mp3 (100–110 BPM, sem vocal),
// impressora.wav, clique.wav, tick.wav, notificacao.wav.
import { SCENES } from "./timing";
import * as s01 from "./scenes/S01Hook";
import * as s02 from "./scenes/S02Intro";
import * as s03 from "./scenes/S03Comandas";
import * as s04 from "./scenes/S04Open";
import * as s05 from "./scenes/S05Investigation";
import * as s06 from "./scenes/S06Drill";
import * as s07 from "./scenes/S07Agent";
import * as s08 from "./scenes/S08Data";
import * as s09 from "./scenes/S09Automation";
import * as s10 from "./scenes/S10Stack";
import * as s11 from "./scenes/S11Close";

export type SfxKind = "impressora" | "clique" | "tick" | "notificacao";
export type SceneSfx = { frame: number; kind: SfxKind };

const byScene: [keyof typeof SCENES, SceneSfx[]][] = [
  ["s01Hook", s01.sfx],
  ["s02Intro", s02.sfx],
  ["s03Comandas", s03.sfx],
  ["s04Open", s04.sfx],
  ["s05Investigation", s05.sfx],
  ["s06Drill", s06.sfx],
  ["s07Agent", s07.sfx],
  ["s08Data", s08.sfx],
  ["s09Automation", s09.sfx],
  ["s10Stack", s10.sfx],
  ["s11Close", s11.sfx],
];

/** Todos os efeitos com frame absoluto, em ordem. */
export const SFX = byScene
  .flatMap(([scene, list]) => list.map((e) => ({ ...e, frame: e.frame + SCENES[scene].from, scene })))
  .sort((a, b) => a.frame - b.frame);
