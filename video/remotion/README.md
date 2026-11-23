# Vídeos do LinkedIn: Central de Operações

Dois motion videos em Remotion, 4:5 (1080 × 1350, 30 fps), com a interface do painel recriada em código:

| Composição | Duração | Roteiro |
|---|---|---|
| `LinkedIn` | 58 s (1740 frames) | [`../roteiro-linkedin.md`](../roteiro-linkedin.md): o painel, as comandas e a automação |
| `Agente` | 60 s (1800 frames) | [`../roteiro-agente-linkedin.md`](../roteiro-agente-linkedin.md): o agente antes e depois (camada semântica, grafo, limites, placar) |

## Comandos

```bash
cd video/remotion
npm install
npm run dev       # Remotion Studio em http://localhost:3000
npm run render    # ../out/linkedin.mp4
npm run capa      # ../out/capa.png (frame 0:19, comanda Nº 01 aberta)
npm run render:agente  # ../out/agente.mp4
npm run capa:agente    # ../out/capa-agente.png (frame 0:26, grafo com 3,4 → 1,4 chamadas)
npm run lint      # eslint + tsc
```

`out/linkedin.mp4`, `out/capa.png`, `out/agente.mp4` e `out/capa-agente.png` são versionados: depois de renderizar, faça o commit da versão nova. Os quadros de conferência (`out/check/`, `out/seams/`) ficam fora do git.

## Estrutura

| Arquivo | Papel |
|---|---|
| `src/data.ts` | Todos os textos e números das cenas, conferidos no parquet. Mude aqui, não nas cenas |
| `src/theme.ts` | Tokens do mundo "Comanda" (claro e escuro), fontes, easings, áreas seguras |
| `src/timing.ts` | Janela de cada cena em frames absolutos |
| `src/anim.ts` | Entrada e saída padrão (deslocamento + fade + blur 2 px) |
| `src/components/` | Comanda (`Ticket`), marcas de severidade, bloco Ação, botão, cursor, título e legenda. Prefixo `sNN-` = componente de uma cena só |
| `src/scenes/` | Uma cena por arquivo (`S01Hook` … `S11Close`), cada uma com frames locais |
| `src/sfx.ts` | Frames dos efeitos sonoros (impressora, clique, tick, notificação) |
| `src/agente/` | Vídeo do agente: `data.ts` (textos e números, com a origem no roteiro), `timing.ts`, `AgentVideo.tsx`, `scenes/A01Hook` … `A08Summary` e `sfx.ts`. Reaproveita tema, animações, `Ticket`, `ActionBlock`, `SeverityMark`, `SceneTitle`/`Caption` e a cena de fechamento (`S11Close` com outro rodapé) |

No Studio, `LinkedIn` e `Agente` são os vídeos inteiros; as pastas "Cenas" e "Cenas-Agente" têm cada cena isolada.

Números em Zilla Slab com seta ("86,1% → 84,9%") passam por `src/agente/components/FromTo.tsx`: a seta não está nos subconjuntos da fonte e o glifo de reserva faz o Chrome voltar aos algarismos de estilo antigo no trecho inteiro.

## Som

O vídeo ainda é mudo e foi pensado para ser entendido sem som. Para adicionar trilha e efeitos, coloque `trilha.mp3`, `impressora.wav`, `clique.wav`, `tick.wav` e `notificacao.wav` em `public/audio/` e monte uma faixa de áudio em `src/LinkedInVideo.tsx` a partir de `SFX` (`src/sfx.ts`).

## Desvios do roteiro

- Picote com furos de 7 px a cada 20 px (o app usa 5 a cada 14): no desktop o LinkedIn mostra o vídeo a ~550 px de largura e o recorte original some.
- Botões da comanda aberta em duas linhas: três numa linha só não cabem em 936 px com texto ≥ 28 px.
- Eixo do gráfico de etapas até 44 min: Coffee Shopping (42,7) e Hip Hop Shopping (42,4) passariam de 42.
- Cena 8: a comanda Nº 06 entra abaixo do 98,5%, não ao lado, para o texto ficar ≥ 28 px.
