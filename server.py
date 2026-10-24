import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

# A partir da Etapa 1, adicione o seu código ABAIXO desta linha.

# Regras da Mina (docs/especificacao.md, seção 1)
CUSTO = 50          # pedras por fornalha
TEMPO_OBRA = 8      # segundos até a fornalha ficar pronta
INTERVALO = 5       # segundos entre as produções

# O estado da vila mora só aqui: o servidor é a fonte da verdade.
estado = {
    "fase": "aguardando",     # aguardando -> aberta -> encerrada
    "pedra": 150,
    "minerio": 0,
    "barras": 0,              # recurso refinado, fundido pelas fornalhas
    "mineiros": 0,            # ocupados agora (obras + expedições)
    "limite": 2,              # máximo de mineiros
    "producao_pedra": 10,     # pedras a cada INTERVALO
    "producao_minerio": 5,    # minérios a cada INTERVALO
    "intervalo": INTERVALO,
    "tempo_obra": TEMPO_OBRA,
    "custo": CUSTO,
    "concluidas": 0,          # fornalhas prontas
    "em_obra": 0,             # fornalhas em obra
    "expedicoes": 0,          # expedições em andamento
}
jogadores = {}                # sid -> {"nome": ..., "papel": ...}


def fato(causa, **extras):
    """Monta o payload de um FATO: o estado atual, a CAUSA (o evento ou o
    temporizador que gerou o fato) e dados extras."""
    return {"estado": dict(estado), "causa": causa, **extras}


@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    jogadores[sid] = {
        "nome": auth.get("nome", "Anônimo"),
        "papel": auth.get("papel", "jogador"),
    }
    # emit para UM cliente (to=sid): só quem acabou de chegar precisa do estado;
    # quem já estava conectado já o recebeu e acompanha pelos fatos seguintes.
    await sio.emit("estado.sincronizado", fato("conexao"), to=sid)


@sio.event
async def disconnect(sid):
    jogadores.pop(sid, None)


async def recusar(sid, motivo, causa):
    """Responde só a quem pediu."""
    # emit para UM cliente (to=sid): a recusa não muda o estado, então os
    # outros jogadores não têm nada para atualizar.
    await sio.emit("operacao.recusada", {"motivo": motivo, "causa": causa}, to=sid)


# on vila.abertura_solicitada: é um PEDIDO do Mestre; o servidor decide se aceita.
@sio.on("vila.abertura_solicitada")
async def abrir_vila(sid, dados=None):
    pedido = "vila.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir ou encerrar a temporada", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A temporada já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    sio.start_background_task(producao)   # o tempo começa a passar na mina
    # emit para TODOS: a fase mudou e todo mundo precisa saber que pode agir.
    await sio.emit("vila.iniciada", fato(pedido))


# on construcao.solicitada: é um PEDIDO do Jogador para construir uma fornalha.
@sio.on("construcao.solicitada")
async def construir(sid, dados=None):
    pedido = "construcao.solicitada"
    # Valida TUDO antes de alterar o estado e sem await no meio: o servidor
    # trata um evento por vez, então dois pedidos simultâneos são decididos
    # em sequência e só um leva o último mineiro ou as últimas pedras.
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores constroem e enviam expedições"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif estado["pedra"] < CUSTO:
        motivo = "Pedras insuficientes"
    elif estado["mineiros"] >= estado["limite"]:
        motivo = "Sem mineiro livre"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    estado["pedra"] -= CUSTO
    estado["mineiros"] += 1
    estado["em_obra"] += 1
    nome = jogadores[sid]["nome"]
    # emit para TODOS: pedras e mineiros mudaram para a vila inteira.
    await sio.emit("construcao.iniciada", fato(pedido, por=nome))
    sio.start_background_task(obra, nome)   # a obra termina sozinha depois de TEMPO_OBRA


# Temporizador: fonte de eventos sem clique de ninguém. Use sio.sleep (e não
# time.sleep), senão o servidor inteiro trava esperando.
async def producao():
    while estado["fase"] == "aberta":
        await sio.sleep(INTERVALO)
        if estado["fase"] != "aberta":
            break
        estado["pedra"] += estado["producao_pedra"]
        estado["minerio"] += estado["producao_minerio"]
        # emit para TODOS: o estoque subiu; os clientes não perguntam
        # "já produziu?", só escutam este fato.
        await sio.emit("recurso.produzido", fato("temporizador"))


async def obra(nome):
    await sio.sleep(TEMPO_OBRA)
    if estado["fase"] != "aberta":
        return
    estado["mineiros"] -= 1
    estado["em_obra"] -= 1
    estado["concluidas"] += 1
    # emit para TODOS: a fornalha ficou pronta e o mineiro voltou a ficar livre.
    causa = "construcao.iniciada (temporizador)"
    await sio.emit("construcao.concluida", fato(causa, por=nome))


# on vila.encerramento_solicitado: é um PEDIDO do Mestre para fechar a temporada.
@sio.on("vila.encerramento_solicitado")
async def encerrar_vila(sid, dados=None):
    pedido = "vila.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir ou encerrar a temporada", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    # Mudar a fase basta para parar tudo: producao() e obra() conferem a fase
    # depois de cada espera e não emitem mais nada.
    estado["fase"] = "encerrada"
    # emit para TODOS: ninguém pode mais agir, e todos precisam saber.
    await sio.emit("vila.encerrada", fato(pedido))
