# Vídeo do LinkedIn: Central de Operações

Motion video de 58 s em Remotion, 4:5 (1080 × 1350, 30 fps, 1740 frames), com a interface do painel recriada em código. Roteiro, textos, números e tokens: [`../roteiro-linkedin.md`](../roteiro-linkedin.md).

## Comandos

```bash
cd video/remotion
npm install
npm run dev       # Remotion Studio em http://localhost:3000
npm run render    # ../out/linkedin.mp4
npm run capa      # ../out/capa.png (frame 0:19, comanda Nº 01 aberta)
npm run lint      # eslint + tsc
```

`out/linkedin.mp4` e `out/capa.png` são versionados: depois de `npm run render` ou `npm run capa`, faça o commit da versão nova. Os quadros de conferência (`out/check/`, `out/seams/`) ficam fora do git.

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

No Studio, a composição `LinkedIn` é o vídeo inteiro e a pasta "Cenas" tem cada cena isolada.

## Som

O vídeo ainda é mudo e foi pensado para ser entendido sem som. Para adicionar trilha e efeitos, coloque `trilha.mp3`, `impressora.wav`, `clique.wav`, `tick.wav` e `notificacao.wav` em `public/audio/` e monte uma faixa de áudio em `src/LinkedInVideo.tsx` a partir de `SFX` (`src/sfx.ts`).

## Desvios do roteiro

- Picote com furos de 7 px a cada 20 px (o app usa 5 a cada 14): no desktop o LinkedIn mostra o vídeo a ~550 px de largura e o recorte original some.
- Botões da comanda aberta em duas linhas: três numa linha só não cabem em 936 px com texto ≥ 28 px.
- Eixo do gráfico de etapas até 44 min: Coffee Shopping (42,7) e Hip Hop Shopping (42,4) passariam de 42.
- Cena 8: a comanda Nº 06 entra abaixo do 98,5%, não ao lado, para o texto ficar ≥ 28 px.
