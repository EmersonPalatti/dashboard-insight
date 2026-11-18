# Briefing diário no n8n

O arquivo `briefing-diario.json` é o workflow `briefing-diario` (id `briefingDiario01`). Ele consulta a API e manda o briefing e os alertas para um chat do Telegram. O que cada nó faz está em [COMO-FUNCIONA.md](COMO-FUNCIONA.md). Uma execução real está em [exemplo-briefing.md](exemplo-briefing.md).

O workflow chega inativo. O horário das 8h só passa a valer quando você ativa o workflow no editor.

## 1. Subir a API local

Com o ambiente do backend já instalado, como no README do repositório:

```text
cd backend
uvicorn app.main:app
```

A API fica em `http://127.0.0.1:8000` (`/docs` para o contrato). Use `127.0.0.1`, não `localhost`. No Windows, `localhost` resolveu para o IPv6 `::1`, e o uvicorn escuta só IPv4.

O workflow já vem apontado para a API no Render, `https://central-operacoes-api.onrender.com`. Para testar com a API local, o passo 5 troca esse valor.

## 2. Importar o workflow

No n8n, em `http://localhost:5678`: Workflows → menu ⋯ → Import from File, e escolha `n8n/briefing-diario.json`.

Pela CLI, na pasta do repositório:

```text
n8n import:workflow --input=n8n/briefing-diario.json
```

Para executar pela CLI:

```text
n8n execute --id=briefingDiario01
```

Se o servidor do n8n já estiver aberto, a CLI precisa de outra porta para o task broker. A 5679 já está ocupada. No PowerShell:

```text
$env:N8N_RUNNERS_BROKER_PORT = "5690"
n8n execute --id=briefingDiario01
```

No bash, o equivalente é `N8N_RUNNERS_BROKER_PORT=5690 n8n execute --id=briefingDiario01`.

## 3. Criar a credencial do Telegram

1. No Telegram, abra o @BotFather e envie `/newbot`. Siga o diálogo. Ele devolve o token do bot.
2. Abra o bot que você acabou de criar e aperte Start. Sem isso ele não entrega mensagem para você.
3. No n8n, abra `http://localhost:5678/home/credentials`, adicione uma credencial do tipo Telegram API e cole o token ali.

Não cole o token em nó, arquivo ou chat. O JSON do repositório deixa o id da credencial vazio de propósito. Se o token vazar, no BotFather use `/revoke`, gere outro e atualize a credencial no n8n. O token antigo deixa de valer.

## 4. Pegar o chat ID

1. No Telegram, abra o @userinfobot e aperte Start. A resposta traz o seu Id.
2. Esse número é o `chat_id`. No arquivo o campo está como `SEU_CHAT_ID`.

O número antes dos dois-pontos do token é o id do bot, não o seu. Colocar o id do bot em `chat_id` faz o envio falhar.

## 5. Preencher o Config e os três nós Telegram

Abra o workflow importado, no nó Config:

- `api_base`: vem com `https://central-operacoes-api.onrender.com`. Com a API local, troque por `http://127.0.0.1:8000`.
- `data_ref`: deixe a expressão como está. Ela escolhe o dia do dataset. A conta está em [COMO-FUNCIONA.md](COMO-FUNCIONA.md).
- `chat_id`: o id que o @userinfobot mostrou.

Nos cinco nós Telegram (briefing, alerta, as duas cópias "(texto puro)" e falha da API), selecione a credencial criada no passo 3. O nome gravado no arquivo é "Telegram account"; na sua instância você aponta a credencial real. Salve o workflow.

## 6. Executar

Com a API no ar, use Execute no editor (gatilho Executar manualmente) ou a CLI do passo 2.

O chat recebe o briefing e, em seguida, uma mensagem por alerta. Se a API não acordar (3 tentativas, espera de 30 s, mais 3 tentativas), a mensagem é `Briefing não gerado: API indisponível`. Se o briefing saiu e só o roteamento falhou, a mensagem é `Alertas não encaminhados: ...`.

## 7. Ativar o horário

No editor, ligue o workflow (Active). O nó Todo dia às 8h usa o fuso já gravado no workflow, `America/Sao_Paulo`. O processo do n8n precisa estar rodando nesse horário. Com o workflow inativo, só a execução manual roda.
