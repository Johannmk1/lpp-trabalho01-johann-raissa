# Especificação: Vila em Tempo Real (Mina)

**Integrantes:** Johann Malkowski (@Johannmk1) e Raíssa Sofka Mazzi (@Raissa-SM)
**Tipo de vila (sorteio):** 3. Mina

## 1. Regras da vila

### Papéis

- **Mestre:** abre e encerra a temporada.
- **Jogador:** constrói fornalhas e envia mineiros em expedição.

### Fases da temporada

`aguardando` → `aberta` → `encerrada`. Só com a temporada aberta os jogadores podem agir e o tempo passa.

### Recursos

| Recurso | Tipo | Início | Como entra |
|---|---|---|---|
| Pedra | primário | 150 | produção automática |
| Minério | primário | 0 | produção automática e retorno de expedição |
| Barras | refinado | 0 | fundidas pelas fornalhas prontas |

### Números

- Custo de uma construção (fornalha): **50 pedras**.
- Tempo da obra: **8 segundos**.
- Limite de mineiros: **2**. Cada obra e cada expedição ocupa 1 mineiro enquanto dura.
- Produção automática: a cada **5 segundos**, **+10 pedras** e **+5 minérios**.
- O que muda quando uma obra termina: a fornalha fica pronta e o mineiro fica livre. A cada produção, cada fornalha pronta funde **2 minérios em 1 barra**, enquanto houver minério.
- Expedição: não custa recurso, ocupa 1 mineiro e tem **prazo de 20 segundos** para retornar. Cada jogador tem no máximo uma expedição em andamento.
- Retorno a tempo: a expedição traz **2 minérios por segundo** que passou fora e o mineiro fica livre.
- Prazo vencido: a carga se perde e o mineiro volta livre, sem nada.

### Recusas (só quem pediu é avisado, nada muda no estado)

| Motivo | Quando |
|---|---|
| A temporada não está aberta | qualquer ação de jogador fora da fase `aberta`; encerrar fora da fase `aberta` |
| A temporada já foi aberta | o Mestre pede a abertura fora da fase `aguardando` |
| Só o Mestre pode abrir ou encerrar a temporada | um Jogador pede abertura ou encerramento |
| Só jogadores constroem e enviam expedições | o Mestre pede construção ou expedição |
| Pedras insuficientes | pedido de construção com menos de 50 pedras |
| Sem mineiro livre | pedido de construção ou expedição com todos os mineiros ocupados |
| Você já tem uma expedição em andamento | segundo pedido de expedição do mesmo jogador |
| Você não tem expedição em andamento | pedido de retorno sem expedição (inclusive quando o prazo acabou de vencer) |

### Ordem das decisões

Os pedidos são decididos um de cada vez, na ordem em que chegam. Cada pedido é validado e aplicado por inteiro antes do próximo. Assim, dois pedidos simultâneos pelo último mineiro ou pelas últimas pedras nunca passam os dois.

## 2. Eventos

Pedidos terminam em `_solicitada`/`_solicitado`. Fatos ficam no passado. Todo fato leva a sua **causa**: o pedido ou o temporizador que o gerou.

| Evento | Emite | Recebe | Causa | O que muda no estado |
|---|---|---|---|---|
| `estado.sincronizado` | Servidor | Só quem conectou | conexão | nada; entrega o estado atual |
| `vila.abertura_solicitada` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.iniciada` | Servidor | Todos | `vila.abertura_solicitada` | fase vira `aberta` e a produção começa |
| `construcao.solicitada` | Jogador | Servidor | pedido | é um pedido; nada muda |
| `construcao.iniciada` | Servidor | Todos | `construcao.solicitada` | -50 pedras, +1 mineiro ocupado, +1 fornalha em obra |
| `operacao.recusada` | Servidor | Só quem pediu | o pedido recusado | nada; informa o motivo |
| `recurso.produzido` | Servidor | Todos | temporizador | +10 pedras, +5 minérios; cada fornalha pronta funde 2 minérios em 1 barra |
| `construcao.concluida` | Servidor | Todos | `construcao.iniciada` (temporizador) | -1 mineiro ocupado, -1 em obra, +1 fornalha pronta |
| `expedicao.solicitada` | Jogador | Servidor | pedido | é um pedido; nada muda |
| `expedicao.iniciada` | Servidor | Todos | `expedicao.solicitada` | +1 mineiro ocupado, +1 expedição em andamento |
| `expedicao.retorno_solicitado` | Jogador | Servidor | pedido | é um pedido; nada muda |
| `expedicao.retornada` | Servidor | Todos | `expedicao.retorno_solicitado` | +2 minérios por segundo fora, -1 mineiro ocupado, -1 expedição |
| `expedicao.perdida` | Servidor | Todos | `expedicao.iniciada` (temporizador) | -1 mineiro ocupado, -1 expedição; a carga se perde |
| `vila.encerramento_solicitado` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.encerrada` | Servidor | Todos | `vila.encerramento_solicitado` | fase vira `encerrada`; produção, obras e expedições param |

## 3. Cenários de teste

### Recusa

Dado que a temporada está aberta, com 100 pedras e 2 de 2 mineiros ocupados, quando o Jogador A emite `construcao.solicitada`, então o servidor emite `operacao.recusada` apenas para A, com o motivo "Sem mineiro livre" e causa `construcao.solicitada`, as pedras continuam 100 e os outros jogadores não recebem nada.

### Passagem do tempo

Dado que a temporada está aberta, com 100 pedras, 10 minérios, 0 barras e 1 fornalha pronta, quando passam 5 segundos sem nenhum pedido, então o servidor emite `recurso.produzido` para todos com causa `temporizador`, e o estado passa a 110 pedras, 13 minérios e 1 barra.

Dado que a fornalha de A recebeu `construcao.iniciada`, quando passam 8 segundos, então o servidor emite `construcao.concluida` para todos com causa `construcao.iniciada (temporizador)`, o mineiro fica livre e a fornalha passa a fundir barras.

### Disputa entre dois jogadores

Dado que a temporada está aberta, com 200 pedras e 1 de 2 mineiros ocupados, quando os jogadores A e B emitem `construcao.solicitada` ao mesmo tempo, então o servidor emite `construcao.iniciada` para todos, com o nome de apenas um deles, e `operacao.recusada` com "Sem mineiro livre" apenas para o outro. Ao final há 2 de 2 mineiros ocupados e 150 pedras.

### Expedição vence o prazo (evento próprio)

Dado que o Jogador A emitiu `expedicao.solicitada` e recebeu `expedicao.iniciada`, quando passam 20 segundos sem A emitir `expedicao.retorno_solicitado`, então o servidor emite `expedicao.perdida` para todos com causa `expedicao.iniciada (temporizador)`, o mineiro fica livre e nenhum minério entra. Se A emitir `expedicao.retorno_solicitado` depois disso, recebe `operacao.recusada` com "Você não tem expedição em andamento".
