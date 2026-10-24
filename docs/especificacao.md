# Especificação: Vila em Tempo Real (Mina)

**Integrantes:** Johann Malkowski (@Johannmk1) e Raíssa Sofka Mazzi (@Raissa-SM)
**Tipo de vila (sorteio):** 3. Mina

## 1. Regras da vila

### Papéis

- **Mestre:** controla a temporada: abre, pausa, encerra e começa do zero.
- **Jogador:** constrói fornalhas e depósitos e envia mineiros em expedição.

### Fases da temporada

```
aguardando --abrir--> aberta --pausar--> pausada --abrir--> aberta
                        |                   |
                        +-----encerrar------+--> encerrada --começar do zero--> aguardando
```

| Fase | O tempo passa? | Jogadores podem pedir? |
|---|---|---|
| `aguardando` | não | não |
| `aberta` | sim: produção, obras e expedições | sim |
| `pausada` | só para o que já estava em andamento: obras e expedições terminam normalmente; a produção para | só chamar a expedição de volta |
| `encerrada` | não: nada mais termina | não |

Começar do zero devolve a mina ao estado inicial. Obras e expedições da temporada anterior são descartadas e não terminam na temporada nova.

### Recursos e o ciclo da mina

| Recurso | Tipo | Início | Como entra | Para que serve |
|---|---|---|---|---|
| Pedra | primário | 150 | produção automática | construir fornalhas |
| Minério | primário | 0 | produção automática e retorno de expedição | ser fundido em barras |
| Barras | refinado | 0 | fundidas pelas fornalhas prontas | construir depósitos |

O ciclo: **pedra** constrói fornalhas → as fornalhas fundem **minério** em **barras** → as barras constroem depósitos → cada depósito dá **mais um mineiro** → mais mineiros fazem mais obras e expedições.

### Construções

| Construção | Custo | Tempo da obra | Efeito quando fica pronta |
|---|---|---|---|
| Fornalha | 50 pedras | 8 segundos | a cada produção, funde 2 minérios em 1 barra, enquanto houver minério |
| Depósito | 5 barras | 8 segundos | +1 no limite de mineiros |

### Números

- Limite inicial de mineiros: **2**. Cada obra e cada expedição ocupa 1 mineiro enquanto dura.
- Produção automática: a cada **5 segundos** com a temporada aberta, **+10 pedras** e **+5 minérios**.
- Expedição: não custa recurso, ocupa 1 mineiro e tem **prazo de 20 segundos** para retornar. Cada jogador tem no máximo uma expedição em andamento. O prazo continua correndo durante a pausa.
- Retorno a tempo: a expedição traz **2 minérios por segundo** que passou fora e o mineiro fica livre.
- Prazo vencido: a carga se perde e o mineiro volta livre, sem nada.

### Recusas (só quem pediu é avisado, nada muda no estado)

| Motivo | Quando |
|---|---|
| Só o Mestre controla a temporada | um Jogador pede abertura, pausa, encerramento ou começar do zero |
| A temporada já está aberta | abertura com a temporada aberta |
| A temporada foi encerrada; comece do zero | abertura com a temporada encerrada |
| A temporada não está aberta | pausa fora da fase `aberta`; construção ou expedição fora da fase `aberta`; retorno de expedição fora das fases `aberta` e `pausada` |
| A temporada não está em andamento | encerramento fora das fases `aberta` e `pausada` |
| Encerre a temporada antes de começar do zero | começar do zero fora da fase `encerrada` |
| Só jogadores constroem e enviam expedições | o Mestre pede construção ou expedição |
| Pedras insuficientes | fornalha com menos de 50 pedras |
| Barras insuficientes | depósito com menos de 5 barras |
| Sem mineiro livre | construção ou expedição com todos os mineiros ocupados |
| Você já tem uma expedição em andamento | segundo pedido de expedição do mesmo jogador |
| Você não tem expedição em andamento | pedido de retorno sem expedição (inclusive quando o prazo acabou de vencer) |

### Ordem das decisões

Os pedidos são decididos um de cada vez, na ordem em que chegam. Cada pedido é validado e aplicado por inteiro antes do próximo. Assim, dois pedidos simultâneos pelo último mineiro, pelas últimas pedras ou pelas últimas barras nunca passam os dois.

## 2. Eventos

Pedidos terminam em `_solicitada`/`_solicitado`. Fatos ficam no passado. Todo fato leva a sua **causa**: o pedido ou o temporizador que o gerou.

| Evento | Emite | Recebe | Causa | O que muda no estado |
|---|---|---|---|---|
| `estado.sincronizado` | Servidor | Só quem conectou | conexão | nada; entrega o estado atual |
| `vila.abertura_solicitada` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.iniciada` | Servidor | Todos | `vila.abertura_solicitada` | fase vira `aberta` e a produção começa (ou recomeça, depois de uma pausa) |
| `vila.pausa_solicitada` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.pausada` | Servidor | Todos | `vila.pausa_solicitada` | fase vira `pausada`; a produção para |
| `construcao.solicitada` | Jogador | Servidor | pedido (diz o tipo: fornalha ou depósito) | é um pedido; nada muda |
| `construcao.iniciada` | Servidor | Todos | `construcao.solicitada` | debita o custo do tipo, +1 mineiro ocupado, +1 obra daquele tipo |
| `operacao.recusada` | Servidor | Só quem pediu | o pedido recusado | nada; informa o motivo |
| `recurso.produzido` | Servidor | Todos | temporizador | +10 pedras, +5 minérios; cada fornalha pronta funde 2 minérios em 1 barra |
| `construcao.concluida` | Servidor | Todos | `construcao.iniciada` (temporizador) | -1 mineiro ocupado, -1 obra; +1 fornalha pronta, ou +1 depósito pronto e +1 no limite de mineiros |
| `expedicao.solicitada` | Jogador | Servidor | pedido | é um pedido; nada muda |
| `expedicao.iniciada` | Servidor | Todos | `expedicao.solicitada` | +1 mineiro ocupado, +1 expedição em andamento |
| `expedicao.retorno_solicitado` | Jogador | Servidor | pedido | é um pedido; nada muda |
| `expedicao.retornada` | Servidor | Todos | `expedicao.retorno_solicitado` | +2 minérios por segundo fora, -1 mineiro ocupado, -1 expedição |
| `expedicao.perdida` | Servidor | Todos | `expedicao.iniciada` (temporizador) | -1 mineiro ocupado, -1 expedição; a carga se perde |
| `vila.encerramento_solicitado` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.encerrada` | Servidor | Todos | `vila.encerramento_solicitado` | fase vira `encerrada`; produção, obras e expedições param |
| `vila.reinicio_solicitado` | Mestre | Servidor | pedido | é um pedido; nada muda |
| `vila.reiniciada` | Servidor | Todos | `vila.reinicio_solicitado` | o estado volta ao inicial e a fase vira `aguardando` |

## 3. Cenários de teste

### Recusa

Dado que a temporada está aberta, com 100 pedras e 2 de 2 mineiros ocupados, quando o Jogador A emite `construcao.solicitada` para uma fornalha, então o servidor emite `operacao.recusada` apenas para A, com o motivo "Sem mineiro livre" e causa `construcao.solicitada`, as pedras continuam 100 e os outros jogadores não recebem nada.

### Passagem do tempo

Dado que a temporada está aberta, com 100 pedras, 10 minérios, 0 barras e 1 fornalha pronta, quando passam 5 segundos sem nenhum pedido, então o servidor emite `recurso.produzido` para todos com causa `temporizador`, e o estado passa a 110 pedras, 13 minérios e 1 barra.

Dado que a fornalha de A recebeu `construcao.iniciada`, quando passam 8 segundos, então o servidor emite `construcao.concluida` para todos com causa `construcao.iniciada (temporizador)`, o mineiro fica livre e a fornalha passa a fundir barras.

### Disputa entre dois jogadores

Dado que a temporada está aberta, com 200 pedras e 1 de 2 mineiros ocupados, quando os jogadores A e B emitem `construcao.solicitada` para uma fornalha ao mesmo tempo, então o servidor emite `construcao.iniciada` para todos, com o nome de apenas um deles, e `operacao.recusada` com "Sem mineiro livre" apenas para o outro. Ao final há 2 de 2 mineiros ocupados e 150 pedras.

### Expedição vence o prazo (evento próprio)

Dado que o Jogador A emitiu `expedicao.solicitada` e recebeu `expedicao.iniciada`, quando passam 20 segundos sem A emitir `expedicao.retorno_solicitado`, então o servidor emite `expedicao.perdida` para todos com causa `expedicao.iniciada (temporizador)`, o mineiro fica livre e nenhum minério entra. Se A emitir `expedicao.retorno_solicitado` depois disso, recebe `operacao.recusada` com "Você não tem expedição em andamento".

### Depósito aumenta os mineiros

Dado que a temporada está aberta, com 5 barras e 0 de 2 mineiros ocupados, quando o Jogador A emite `construcao.solicitada` para um depósito, então o servidor emite `construcao.iniciada` para todos e as barras vão a 0. Quando passam 8 segundos, o servidor emite `construcao.concluida` com causa `construcao.iniciada (temporizador)` e o limite passa a 3 mineiros.

### Pausa

Dado que a temporada está aberta e uma fornalha está em obra, quando o Mestre emite `vila.pausa_solicitada`, então o servidor emite `vila.pausada` para todos, as pedras e os minérios param de subir, um `construcao.solicitada` de qualquer jogador recebe `operacao.recusada` com "A temporada não está aberta", e a obra que já estava em andamento ainda termina com `construcao.concluida`. Quando o Mestre emite `vila.abertura_solicitada`, o servidor emite `vila.iniciada` e a produção recomeça.

### Começar do zero

Dado que a temporada foi encerrada com uma obra em andamento, quando o Mestre emite `vila.reinicio_solicitado`, então o servidor emite `vila.reiniciada` para todos, o estado volta a 150 pedras, 0 minérios, 0 barras e 0 de 2 mineiros, e a obra da temporada anterior nunca emite `construcao.concluida`.
