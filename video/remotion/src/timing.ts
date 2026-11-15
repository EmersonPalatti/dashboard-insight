// Janelas das cenas em frames absolutos (roteiro, seções 3 e 4). 30 fps, 1740 frames.
// Dentro de cada cena o frame é local (0 = início da cena).
export const SCENES = {
  s01Hook: { from: 0, duration: 150 },
  s02Intro: { from: 150, duration: 150 },
  s03Comandas: { from: 300, duration: 180 },
  s04Open: { from: 480, duration: 210 },
  s05Investigation: { from: 690, duration: 150 },
  s06Drill: { from: 840, duration: 150 },
  s07Agent: { from: 990, duration: 240 },
  s08Data: { from: 1230, duration: 120 },
  s09Automation: { from: 1350, duration: 180 },
  s10Stack: { from: 1530, duration: 120 },
  s11Close: { from: 1650, duration: 90 },
} as const;

export const TOTAL_FRAMES = 1740;
/** Capa do post: 0:19, comanda Nº 01 aberta com o bloco Ação. */
export const COVER_FRAME = 570;

/** Converte um tempo do roteiro (segundos, ex.: 19.5) em frame local da cena. */
export const local = (scene: keyof typeof SCENES, seconds: number) =>
  Math.round(seconds * 30) - SCENES[scene].from;
