# Benchmark do agente de insights

Placar que mede se o agente responde certo sobre o recorte, nos moldes dos benchmarks do Genie. Vale para as
regras locais (sempre) e para a cadeia com LLM (quando há `OPENROUTER_API_KEY`). Serve para provar que uma mudança
no agente melhorou alguma coisa e para pegar regressão.

## O que mede

Cada caso é uma pergunta de operador (formal, informal, com erro de digitação ou sem acento), um recorte e as
expectativas. **A verdade sai dos dados na hora**: `expect(repo, f)` roda as mesmas consultas do painel
(`metrics`, `breakdown`, `subslice_metrics`, `query_metrics`, `previous_period`) e escolhe "o hub com mais pedidos", "a loja que
mais cancela com 150+ pedidos" e assim por diante. Nenhum nome fica fixo no código, então o mesmo caso roda no
parquet sintético dos testes e nos 369 mil pedidos reais. Casos "por quê" usam uma decomposição exata da
variação (decomposição simétrica taxa + mix via `analytics.explain_change`, onde a soma dos grupos fecha exatamente com a variação total) para achar quem mais empurrou a taxa.

Verificações de cada resposta (peso entre parênteses):

| Verificação | O que exige |
|---|---|
| `action` (2) | Linha `**Ação:**`, campo `action` preenchido e específico: cita hub, loja, cidade, canal, forma de pagamento, faixa de horário ou dia |
| `entities` (3) | Nomeia a entidade certa no texto (sem diferenciar acento e caixa) ou oferece o atalho com o id dela |
| `numbers` (3) | O número certo aparece no texto, lido em pt-BR (`82,4%`, `R$ 1.234,56`, `38 min`, `−1,6 p.p.`, `369 mil`). Folga de 0,15 em %, p.p. e min; contagem e R$ por extenso precisam bater no arredondamento (abreviado como `369 mil` ganha meia unidade). Número de entidade precisa estar na mesma linha dela |
| `mentions` (1) | Conceitos obrigatórios (ex.: dizer que o dado não existe), a partir do início de uma palavra (`pico` não casa com `típico`; radical como `cancel` vale) |
| `forbidden` (2) | Sem severidade em inglês, nome de ferramenta (atual ou removida), flag ou campo interno (`low_sample`, `sla_below`…), `None`, JSON cru fora do bloco `leitura`, trecho do prompt |
| `drilldowns` (1) | Chaves só do `Filters` (sem período); hub, loja e cidade existem no dado |
| `scope` (2) | `base.n` igual aos pedidos do recorte |
| `format_ptbr` (1, aviso) | Sem `82.4%`, `R$ 1,234.56`, `38.5 min` |
| `latency` (1, aviso) | Abaixo do teto (5 s local; `max(chat_budget_s, investigation_budget_s) + 5` com LLM e investigação ativa, ou `chat_budget_s + 5` sem ela) |

Nota do caso = média ponderada das verificações (cada uma de 0 a 1). O caso **passa** quando nenhuma
verificação de erro fica abaixo de 1; aviso só desconta da nota.

## Como rodar

```bash
cd backend
python -m evals.run --engine local --out placar.md          # regras locais, sem rede
python -m evals.run --cases sla,why-* --json placar.json    # só SLA e os "por quê"
python -m evals.run --data caminho/outro.parquet            # outro dataset
```

Com LLM (`OPENROUTER_API_KEY` no `.env` ou no ambiente):

```bash
python -m evals.run --engine auto --repeat 3 --sleep 4 --out placar-llm.md
```

`--repeat` mede a variação do modelo (sem LLM a resposta é determinística e roda uma vez). `--sleep` espaça
as chamadas para a cota gratuita. Sem chave, `auto` avisa e cai nas regras locais. `--all-cases` ignora a marcação
`engines` e roda tudo. Flags auxiliares: `--log arquivo.log` grava o log `INFO` do agente (tokens, `finish_reason`,
fallbacks), `--max-latency SEGUNDOS` sobrescreve o teto de aviso de latência, `--quiet` omite a linha por caso e
`--min-pass-rate TAXA` (0 a 1, ex.: `1.0` no CI) encerra com código 1 se a aprovação ficar abaixo do piso ou houver
erro. O teste `tests/test_evals.py` roda o motor local no sintético e trava 100% de aprovação.

## Como ler o placar

- **Taxa de aprovação** e **nota média**: o número para comparar antes e depois de uma mudança.
- **Por categoria**: onde o agente é fraco (ex.: `por-que`, `fora-escopo`).
- **Por modo**: `llm-tools`, `llm-context` ou `local`. Com LLM, *Caiu nas regras locais* é a taxa de fallback.
- **Verificações que mais falham**: o tipo de erro mais comum.
- **Falhas e motivos**: por caso, o que faltou ("não cita hub 'X'", "faltou SLA de X = 80.00 pct") e a ação devolvida.
- **Fora do placar**: caso que os dados não sustentam (ex.: sem período anterior). Não conta como falha.

## Como adicionar um caso

Em `cases.py`, escreva uma função `expect(repo, f) -> Expectations` e acrescente um `Case` em `CASES`:

```python
def exp_pior_modal(repo, f):
    rows = [r for r in repo.breakdown(f, "modal", sort="sla_rate", desc=False) if r["key"]]
    worst = rows[0]
    return Expectations(
        entities=[Entity("modal", worst["key"], worst["label"])],
        numbers=[pct("SLA do modal", worst["sla_rate"], near=worst["label"])],
    )

Case("sla-pior-modal", "sla", "qual modal atrasa mais?", exp_pior_modal, filters=last_month)
```

- Tupla em `entities`, `numbers` ou `must_mention` significa "qualquer um serve".
- Sem dado para o caso, levante `CaseNotApplicable`: o caso sai do placar sem reprovar.
- `engines=("llm",)` só quando as regras locais não têm como responder; senão deixe os dois, para o placar local
  não sair inflado.
- Caso de "por quê" tira os grupos esperados de `analytics.explain_change` (`change_drivers`), a mesma régua
  do agente; não refaça a decomposição no caso.
- Nada de nome fixo: `test_cases_have_no_fixed_entity_names` reprova qualquer texto de `evals/*.py` que cite hub,
  loja ou cidade do parquet sintético ou do real (palavra inteira, rótulos de 4+ letras).
