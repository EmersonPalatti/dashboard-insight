# Exemplo de briefing gerado

Mensagens reais da execução manual do workflow `briefing-diario` em 11/11/2026, com `data_ref` = `2021-02-22` e a API local. É o texto exato enviado ao Telegram (parse mode Markdown: `*negrito*`).

## 1. Briefing para o operador

```text
📋 Briefing de 22/02/2021

*Briefing do recorte* (22/02/2021 a 22/02/2021)

- 2.143 pedidos · GMV R$ 157.520,18 · ticket R$ 77,48
- SLA 86,9% · ciclo mediano 39,0 min (p90 66,5 min)
- Cancelamento 5,1% · subsídio de frete R$ 1,65 por entrega

*Alertas e ações*
- *SLA cai no horário de pico*: No pico (11h–13h e 19h–21h), 84,1% dos pedidos no prazo contra 90,5% fora dele (−6,4 p.p.). *Ação:* Antecipar a escala de entregadores em 30 min antes das 11h nos hubs com pior SLA e segurar promoções nesse intervalo.
- *Pedidos presos no fluxo*: 120 entregas (5,9%) com ciclo acima de 4h; pior hub: Pagode Shopping com 19,0%. Ficam fora das medianas de tempo. *Ação:* Conferir a rotina de finalização desses pedidos (baixa manual, agendamento ou goods com retirada posterior) antes de cobrar SLA do hub.
```

## 2. Encaminhamento dos alertas (2 mensagens)

Uma mensagem por alerta, prefixada com o responsável. No portfólio todas vão para o mesmo chat, simulando o encaminhamento.

### Alerta 1

```text
🟠 *Para: Time de operações da praça*

SLA cai no horário de pico. No pico (11h–13h e 19h–21h), 84,1% dos pedidos no prazo contra 90,5% fora dele (−6,4 p.p.). Ação: Antecipar a escala de entregadores em 30 min antes das 11h nos hubs com pior SLA e segurar promoções nesse intervalo.
```

### Alerta 2

```text
🟠 *Para: Líder do hub 31*

Pedidos presos no fluxo. 120 entregas (5,9%) com ciclo acima de 4h; pior hub: Pagode Shopping com 19,0%. Ficam fora das medianas de tempo. Ação: Conferir a rotina de finalização desses pedidos (baixa manual, agendamento ou goods com retirada posterior) antes de cobrar SLA do hub.
```

## 3. Quando a API não responde

Execução de teste com `api_base` apontando para uma porta sem serviço: 3 tentativas em ~10 s no nó **Acordar API**, depois a saída de erro manda:

```text
Briefing não gerado: API indisponível
```
