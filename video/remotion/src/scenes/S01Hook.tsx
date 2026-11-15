import { useCurrentFrame } from "remotion";
import { HookStage, S01_TIMING } from "../components/s01-HookStage";
import type { SceneSfx } from "../sfx";

/** Efeitos sonoros desta cena (frames locais). */
export const sfx: SceneSfx[] = [{ frame: S01_TIMING.printStart, kind: "impressora" }];

/** Cena 1: Gancho (0:00–0:05). Gráfico genérico encolhe e sai como comanda da impressora. */
export const S01Hook = () => {
  const frame = useCurrentFrame();
  return <HookStage frame={frame} />;
};
