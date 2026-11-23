// Janelas das cenas do vídeo do agente em frames absolutos (roteiro-agente-linkedin.md, seção 4).
// 30 fps, 1800 frames (60 s). Dentro de cada cena o frame é local (0 = início da cena).
export const AGENT_SCENES = {
  a01Hook: { from: 0, duration: 150 },
  a02Before: { from: 150, duration: 180 },
  a03Semantic: { from: 330, duration: 210 },
  a04Graph: { from: 540, duration: 300 },
  a05March: { from: 840, duration: 210 },
  a06Progressive: { from: 1050, duration: 240 },
  a07Evals: { from: 1290, duration: 240 },
  a08Summary: { from: 1530, duration: 150 },
  a09Close: { from: 1680, duration: 120 },
} as const;

export const AGENT_TOTAL_FRAMES = 1800;
/** Capa do post: 0:26, grafo completo com a faixa 3,4 → 1,4 chamadas. */
export const AGENT_COVER_FRAME = 780;
