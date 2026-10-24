# Vila em Tempo Real: Mina

Trabalho 01 de Linguagem de Programação e Paradigmas (Programação Orientada a Eventos, 2026/2).
Tipo de vila sorteado: **3. Mina** (pedra e minério → barras; mineiros; expedição com prazo de retorno).

Vários jogadores entram na mesma mina. O Mestre abre, pausa e encerra a temporada; os Jogadores constroem fornalhas e depósitos, mandam mineiros em expedição e tentam erguer a **estátua de ouro**, o objetivo final. O servidor decide tudo e avisa todos na hora, sem recarregar a página.

As regras, a tabela de eventos e os cenários de teste estão em [docs/especificacao.md](docs/especificacao.md).

## Integrantes

- Johann Malkowski (@Johannmk1)
- Raíssa Sofka Mazzi (@Raissa-SM)

## Linguagem e bibliotecas

- **Servidor:** Python 3, `python-socketio` e `uvicorn` (`server.py`).
- **Tela:** HTML com Vue 3, Socket.IO (cliente) e Phaser 3, carregados por CDN (`client/index.html`).

## Créditos da arte

- **Chão, caminhos, água, árvores, arbustos e pedras:** tileset do Kit Inicial do professor (`client/assets/tileset-vila.png`). O mapa é montado por código a partir dele.
- **Fornalha, depósito, canteiro, mineiro, pedra, minério, barra, carrinho, fogueira, barril, caixote e lampião:** imagens geradas com o **Google Gemini** a partir de prompts da dupla. Depois foram recortadas, tiveram o fundo removido e foram reduzidas para pixel art de 16 px por script (`client/assets/sprites/`).
- **Barra de ouro e estátua de ouro:** derivadas desses sprites. A barra foi repintada em tons de ouro; a estátua é o mineiro ampliado, dourado, sobre um pedestal.
- **Morro e boca da mina, trilho, tablado e lotes:** desenhados por código na cena do Phaser.

Nenhuma arte foi copiada de jogos comerciais.

## Como instalar e executar

Precisa de Python 3 e acesso à internet (Vue, Socket.IO e Phaser vêm por CDN).

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn server:app --reload
```

No Linux ou macOS, ative com `source .venv/bin/activate`.

Abra http://localhost:8000 (não abra o arquivo direto com `file://`). O estado fica na memória do servidor: ao reiniciar o servidor, a mina volta ao começo. No Windows, se depois de salvar o `server.py` a tela abrir mas o estado não chegar, pare com Ctrl+C e suba de novo.

## Como testar com duas abas

Abra duas abas lado a lado em http://localhost:8000. Na primeira, digite um nome e clique **Entrar como Mestre**. Na segunda, **Entrar como Jogador**.

1. **Conexão:** as duas mostram pedra 150, minério 0, barras de ouro 0, mineiros 0/2 e 0/16 lotes. No Painel de eventos aparece `⬇ on estado.sincronizado` com `causa: conexao`.
2. **Recusa antes de abrir:** o Jogador clica **Construir fornalha**. Só a aba dele mostra "A temporada não está aberta" e a mina treme.
3. **Abertura:** o Mestre clica **Abrir temporada**. As duas abas mostram "Temporada: aberta" e a faixa "⛏️ Temporada aberta".
4. **Passagem do tempo:** sem ninguém clicar, a cada 5 s cada mineiro livre produz +5 pedras e +3 minérios (com 2 livres: +10 e +6), nas duas abas (`recurso.produzido`, `causa: temporizador`). O carrinho desce o trilho e as pilhas crescem.
5. **Fornalha:** o Jogador constrói uma fornalha. As duas abas mostram -50 pedras, mineiros 1/2 e um canteiro no primeiro lote; a produção cai, porque o mineiro em obra não minera. Depois de 8 s o canteiro vira uma fornalha acesa (`construcao.concluida`) e, a cada produção, ela funde 2 minérios em 1 barra de ouro.
6. **Limite de mineiros:** o Jogador clica três vezes seguidas em Construir. Duas obras começam e a terceira recebe "Sem mineiro livre", só na aba dele.
7. **Depósito:** com 5 barras, o Jogador constrói um depósito. Quando fica pronto, o limite sobe para 3 mineiros e aparece mais um mineiro no pátio.
8. **Expedição:** o Jogador clica **Enviar expedição** e, alguns segundos depois, **Chamar de volta**. Todos veem "voltou com N minérios" (2 por segundo fora). Se passar de 20 s sem chamar, todos veem "passou do prazo e perdeu a carga" (`expedicao.perdida`, `causa: expedicao.iniciada (temporizador)`).
9. **Disputa:** abra uma terceira aba como Jogador. Com 1 de 2 mineiros ocupado, os dois Jogadores clicam Construir quase ao mesmo tempo. Só um consegue; o outro recebe "Sem mineiro livre".
10. **Pausa:** o Mestre clica **Pausar temporada**. A produção para e pedidos novos são recusados, mas obras e expedições em andamento terminam. **Retomar temporada** volta ao normal.
11. **Espaço:** com os 16 lotes ocupados, mais uma fornalha ou depósito recebe "Sem lote livre".
12. **Objetivo:** com 500 pedras e 60 barras, o Jogador clica **Erguer estátua**. Depois de 15 s a estátua de ouro aparece na praça, o servidor emite `construcao.concluida` e `objetivo.cumprido`, e a temporada termina com vitória.
13. **Encerramento e recomeço:** o Mestre clica **Encerrar temporada** e a mina escurece; depois **Começar do zero** apaga tudo e volta a "Aguardando o Mestre".

Os contadores no alto do Painel de eventos mostram quantas vezes cada evento passou por aquela aba.

## Perguntas

### 1. Quais eventos o seu sistema emite e escuta?

| Evento | Quem emite | Quem escuta | Causa |
|---|---|---|---|
| `estado.sincronizado` | Servidor | Só quem conectou | conexão |
| `vila.abertura_solicitada` | Mestre | Servidor | pedido |
| `vila.iniciada` | Servidor | Todos | `vila.abertura_solicitada` |
| `vila.pausa_solicitada` | Mestre | Servidor | pedido |
| `vila.pausada` | Servidor | Todos | `vila.pausa_solicitada` |
| `construcao.solicitada` | Jogador | Servidor | pedido (fornalha, depósito ou estátua) |
| `construcao.iniciada` | Servidor | Todos | `construcao.solicitada` |
| `operacao.recusada` | Servidor | Só quem pediu | o pedido recusado |
| `recurso.produzido` | Servidor | Todos | temporizador |
| `construcao.concluida` | Servidor | Todos | `construcao.iniciada` (temporizador) |
| `objetivo.cumprido` | Servidor | Todos | `construcao.concluida` (estátua) |
| `expedicao.solicitada` | Jogador | Servidor | pedido |
| `expedicao.iniciada` | Servidor | Todos | `expedicao.solicitada` |
| `expedicao.retorno_solicitado` | Jogador | Servidor | pedido |
| `expedicao.retornada` | Servidor | Todos | `expedicao.retorno_solicitado` |
| `expedicao.perdida` | Servidor | Todos | `expedicao.iniciada` (temporizador) |
| `vila.encerramento_solicitado` | Mestre | Servidor | pedido |
| `vila.encerrada` | Servidor | Todos | `vila.encerramento_solicitado` |
| `vila.reinicio_solicitado` | Mestre | Servidor | pedido |
| `vila.reiniciada` | Servidor | Todos | `vila.reinicio_solicitado` |

Os nomes terminados em `_solicitada`/`_solicitado` são **pedidos** do cliente. Os outros são **fatos** que o servidor confirma.

### 2. Como o sistema sabe quando deve atualizar os outros jogadores?

O cliente nunca muda o estado sozinho nem fica perguntando se algo mudou. Só o servidor muda o estado, e toda vez que muda ele **emite um fato** com o estado novo. Cada tela escuta esses fatos e se redesenha quando um chega.

O servidor escolhe para quem mandar:

- **para todos** (`sio.emit(evento, dados)`): quando muda algo da mina inteira, como estoque, mineiros, lotes ou fase;
- **só para um** (`to=sid`): o `estado.sincronizado`, porque só quem acabou de entrar precisa do estado completo, e a `operacao.recusada`, porque a recusa não muda nada para os outros.

Os fatos que vêm do tempo (`recurso.produzido`, `construcao.concluida`, `expedicao.perdida`) saem de temporizadores do servidor (`sio.sleep`), e o `objetivo.cumprido` é emitido logo depois da conclusão da estátua. Ninguém clica: o servidor acorda e avisa todos.

### 3. Que parte do código mostra claramente o uso do paradigma orientado a eventos?

- **Servidor (`server.py`):** cada `@sio.on("..._solicitada")` é um handler que escuta um pedido, valida, muda o estado e emite um fato. Exemplo: `construir()` (linha 115) valida tudo antes de alterar o estado, sem `await` no meio, para que dois pedidos ao mesmo tempo sejam decididos um de cada vez; depois emite `construcao.iniciada` para todos ou `operacao.recusada` só para quem pediu.
- **Temporizadores como fonte de eventos:** `producao()` (linha 161), `obra()` (linha 184) e `prazo_expedicao()` (linha 318) rodam em segundo plano e emitem fatos sem nenhum clique. Em `obra()`, a conclusão da estátua encadeia mais um fato, o `objetivo.cumprido` (linha 208).
- **Tela (`client/index.html`):** a região ESCUTAS, a partir da linha 548, liga cada evento a uma reação com `ouvir(evento, reação, função)`. A região PEDIDOS, a partir da linha 647, tem uma função por botão, que só faz `pedir(evento)`. `ouvir` e `pedir` (linhas 531 e 535) envolvem `socket.on` e `socket.emit` e registram tudo no Painel de eventos, com a causa de cada fato.

## Uso de IA

Usamos o **Claude** (Anthropic), pelo Claude Code, durante todo o trabalho:

- leitura do enunciado, do guia e do kit, e montagem do plano de etapas;
- escrita da especificação (`docs/especificacao.md`) a partir das regras que a dupla escolheu para a Mina;
- escrita do código de cada etapa, seguindo o Guia de Implementação do professor e adaptando para a Mina;
- testes de cada etapa com duas ou mais abas, e testes por script das recusas, da disputa e da expedição;
- explicação de cada evento para os dois integrantes antes de cada commit.

O que a dupla decidiu e mudou: as regras da Mina (custos, tempos, limite de mineiros, a fornalha fundindo barras e a expedição com prazo como evento próprio), a divisão das etapas entre os dois e a revisão e o teste de cada etapa antes do commit. Cada integrante aplicou, testou e commitou as próprias etapas pela própria conta.

## Extras

- **Recurso refinado:** a fornalha pronta funde 2 minérios em 1 barra de ouro a cada produção.
- **Evento próprio com prazo:** a expedição (`expedicao.solicitada`, `expedicao.iniciada`, `expedicao.retorno_solicitado`, `expedicao.retornada`, `expedicao.perdida`), com o prazo controlado por um temporizador do servidor.
- **Contadores por evento** no Painel de eventos (obrigatório para dupla).
- **Depósito:** custa barras e dá mais um mineiro. Fecha o ciclo da mina: pedra → fornalha → barras → depósito → mais mineiros.
- **Produção pelos mineiros livres:** cada mineiro livre produz pedra e minério; quem está em obra ou expedição não produz.
- **Pausa, encerramento e começar do zero:** `vila.pausa_solicitada` → `vila.pausada` e `vila.reinicio_solicitado` → `vila.reiniciada`. Os botões do Mestre mudam com a fase.
- **16 lotes:** o servidor escolhe o lote de cada construção e recusa com "Sem lote livre" quando acabam. Todas as telas desenham a mina igual, inclusive quem entra no meio do jogo.
- **Objetivo final:** a estátua de ouro (`objetivo.cumprido`), que encerra a temporada com vitória.
- **Visual da mina:** mapa com o tileset do kit, sprites em pixel art, pilhas de estoque que crescem, fornalhas com fogo e fumaça, mineiros no pátio e na expedição.
