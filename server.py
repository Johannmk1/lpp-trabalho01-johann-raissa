import copy
import time

import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # tileset do kit e sprites da mina
})

# A partir da Etapa 1, adicione o seu código ABAIXO desta linha.

# Regras da Mina (docs/especificacao.md, seção 1)
# Cada construção custa recursos diferentes: é o que fecha o ciclo da mina
# (pedra -> fornalha -> barras -> depósito -> mais mineiros -> estátua de ouro).
CONSTRUCOES = {
    "fornalha": {"custo": {"pedra": 50}, "tempo": 8, "usa_lote": True,
                 "falta": {"pedra": "Pedras insuficientes"}},
    "deposito": {"custo": {"barras": 5}, "tempo": 8, "usa_lote": True,
                 "falta": {"barras": "Barras insuficientes"}},
    "estatua": {"custo": {"pedra": 500, "barras": 60}, "tempo": 15, "usa_lote": False,
                "falta": {"pedra": "Pedras insuficientes para a estátua", "barras": "Barras insuficientes"}},
}
LOTES = 16          # espaço da mina: cada fornalha ou depósito ocupa um lote
INTERVALO = 5       # segundos entre as produções
PRAZO_EXPEDICAO = 20      # segundos para a expedição voltar antes de se perder
MINERIO_POR_SEGUNDO = 2   # carga que a expedição junta por segundo fora

# O estado da vila mora só aqui: o servidor é a fonte da verdade.
# ESTADO_INICIAL é a mina zerada; "começar do zero" volta para ele.
ESTADO_INICIAL = {
    "fase": "aguardando",     # aguardando -> aberta <-> pausada -> encerrada -> aguardando
    "pedra": 150,
    "minerio": 0,
    "barras": 0,              # recurso refinado, fundido pelas fornalhas
    "mineiros": 0,            # ocupados agora (obras + expedições)
    "limite": 2,              # máximo de mineiros
    "pedra_por_mineiro": 5,   # cada mineiro LIVRE produz isso a cada INTERVALO
    "minerio_por_mineiro": 3, # (quem está em obra ou expedição não minera)
    "intervalo": INTERVALO,
    "custos": {tipo: regra["custo"] for tipo, regra in CONSTRUCOES.items()},
    "tempos": {tipo: regra["tempo"] for tipo, regra in CONSTRUCOES.items()},
    "fornalhas": 0,           # fornalhas prontas
    "depositos": 0,           # depósitos prontos (cada um deu +1 no limite)
    "em_obra": 0,             # obras em andamento, de qualquer tipo
    "lotes": [None] * LOTES,  # None ou {"tipo": ..., "pronta": ...}: todas as telas desenham igual
    "estatua": None,          # None, "obra" ou "pronta"
    "expedicoes": 0,          # expedições em andamento
    "rodada": 1,              # sobe a cada recomeço; temporizador de rodada velha não vale
}
estado = copy.deepcopy(ESTADO_INICIAL)
ciclo_producao = 0            # sobe a cada abertura; só o laço de produção mais novo produz
jogadores = {}                # sid -> {"nome": ..., "papel": ...}
expedicoes = {}               # sid -> {"nome": ..., "saida": ...}; no máximo uma por jogador


def fato(causa, **extras):
    """Monta o payload de um FATO: o estado atual, a CAUSA (o evento ou o
    temporizador que gerou o fato) e dados extras."""
    return {"estado": copy.deepcopy(estado), "causa": causa, **extras}


# on connect: evento do próprio Socket.IO quando alguém entra. É aqui que o
# servidor fica sabendo o nome e o papel (Mestre ou Jogador) de cada aba.
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


# on disconnect: a aba fechou; o jogador sai da lista (a mina continua igual).
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
    global ciclo_producao
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre controla a temporada", pedido)
        return
    if estado["fase"] == "aberta":
        await recusar(sid, "A temporada já está aberta", pedido)
        return
    if estado["fase"] == "encerrada":
        await recusar(sid, "A temporada foi encerrada; comece do zero", pedido)
        return
    estado["fase"] = "aberta"             # vale para a primeira abertura e para sair da pausa
    ciclo_producao += 1
    sio.start_background_task(producao, ciclo_producao)   # o tempo (re)começa a passar
    # emit para TODOS: a fase mudou e todo mundo precisa saber que pode agir.
    await sio.emit("vila.iniciada", fato(pedido))


# on construcao.solicitada: é um PEDIDO do Jogador; os dados dizem o tipo
# ("fornalha", "deposito" ou "estatua").
@sio.on("construcao.solicitada")
async def construir(sid, dados=None):
    pedido = "construcao.solicitada"
    tipo = (dados or {}).get("tipo", "fornalha")
    regra = CONSTRUCOES.get(tipo)
    # Valida TUDO antes de alterar o estado e sem await no meio: o servidor
    # trata um evento por vez, então dois pedidos simultâneos são decididos
    # em sequência e só um leva o último mineiro ou as últimas pedras.
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores constroem e enviam expedições"
    elif regra is None:
        motivo = "Construção desconhecida"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif regra["usa_lote"] and None not in estado["lotes"]:
        motivo = "Sem lote livre"
    elif not regra["usa_lote"] and estado["estatua"] is not None:
        motivo = "A estátua já foi começada"
    elif any(estado[recurso] < qtd for recurso, qtd in regra["custo"].items()):
        motivo = next(regra["falta"][recurso] for recurso, qtd in regra["custo"].items() if estado[recurso] < qtd)
    elif estado["mineiros"] >= estado["limite"]:
        motivo = "Sem mineiro livre"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    for recurso, qtd in regra["custo"].items():
        estado[recurso] -= qtd
    estado["mineiros"] += 1
    estado["em_obra"] += 1
    if regra["usa_lote"]:
        lote = estado["lotes"].index(None)          # o primeiro lote livre
        estado["lotes"][lote] = {"tipo": tipo, "pronta": False}
    else:
        lote = None                                  # a estátua vai para a praça
        estado["estatua"] = "obra"
    nome = jogadores[sid]["nome"]
    # emit para TODOS: o estoque, os mineiros e os lotes mudaram para a vila inteira.
    await sio.emit("construcao.iniciada", fato(pedido, por=nome, tipo=tipo, lote=lote))
    sio.start_background_task(obra, nome, tipo, lote, estado["rodada"])   # termina sozinha


# Temporizador: fonte de eventos sem clique de ninguém. Use sio.sleep (e não
# time.sleep), senão o servidor inteiro trava esperando.
async def producao(ciclo):
    # Sai quando a temporada deixa de estar aberta ou quando uma abertura mais
    # nova começou outro laço (pausar e retomar rápido não pode produzir em dobro).
    while estado["fase"] == "aberta" and ciclo == ciclo_producao:
        await sio.sleep(INTERVALO)
        if estado["fase"] != "aberta" or ciclo != ciclo_producao:
            break
        livres = estado["limite"] - estado["mineiros"]
        pedra = livres * estado["pedra_por_mineiro"]
        minerio = livres * estado["minerio_por_mineiro"]
        estado["pedra"] += pedra
        estado["minerio"] += minerio
        # Recurso refinado: cada fornalha pronta funde 2 minérios em 1 barra,
        # enquanto houver minério.
        fundidas = min(estado["fornalhas"], estado["minerio"] // 2)
        estado["minerio"] -= fundidas * 2
        estado["barras"] += fundidas
        # emit para TODOS: o estoque subiu; os clientes não perguntam
        # "já produziu?", só escutam este fato.
        await sio.emit("recurso.produzido",
                       fato("temporizador", pedra=pedra, minerio=minerio, barras_fundidas=fundidas))


async def obra(nome, tipo, lote, rodada):
    await sio.sleep(CONSTRUCOES[tipo]["tempo"])
    # Na pausa a obra termina normalmente; encerrada ou de uma rodada antiga, não.
    if estado["fase"] not in ("aberta", "pausada") or estado["rodada"] != rodada:
        return
    estado["mineiros"] -= 1
    estado["em_obra"] -= 1
    if tipo == "estatua":
        estado["estatua"] = "pronta"
    else:
        estado["lotes"][lote]["pronta"] = True
    if tipo == "fornalha":
        estado["fornalhas"] += 1          # passa a fundir barras na próxima produção
    elif tipo == "deposito":
        estado["depositos"] += 1
        estado["limite"] += 1             # o depósito abriga mais um mineiro
    # emit para TODOS: a obra ficou pronta e o mineiro voltou a ficar livre.
    causa = "construcao.iniciada (temporizador)"
    await sio.emit("construcao.concluida", fato(causa, por=nome, tipo=tipo, lote=lote))
    if tipo == "estatua":
        # A estátua é o objetivo final: a temporada termina com vitória. Mudar a
        # fase para tudo, como no encerramento pelo Mestre.
        estado["fase"] = "encerrada"
        # emit para TODOS: um fato novo, causado pela conclusão da estátua.
        await sio.emit("objetivo.cumprido", fato("construcao.concluida (estátua)", por=nome))


# on vila.encerramento_solicitado: é um PEDIDO do Mestre para fechar a temporada.
@sio.on("vila.encerramento_solicitado")
async def encerrar_vila(sid, dados=None):
    pedido = "vila.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre controla a temporada", pedido)
        return
    if estado["fase"] not in ("aberta", "pausada"):
        await recusar(sid, "A temporada não está em andamento", pedido)
        return
    # Mudar a fase basta para parar tudo: producao() e obra() conferem a fase
    # depois de cada espera e não emitem mais nada.
    estado["fase"] = "encerrada"
    # emit para TODOS: ninguém pode mais agir, e todos precisam saber.
    await sio.emit("vila.encerrada", fato(pedido))


# on vila.pausa_solicitada: PEDIDO do Mestre para parar o tempo sem acabar o jogo.
@sio.on("vila.pausa_solicitada")
async def pausar_vila(sid, dados=None):
    pedido = "vila.pausa_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre controla a temporada", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    # A produção para sozinha (o laço confere a fase). Obras e expedições que
    # já estavam em andamento terminam normalmente.
    estado["fase"] = "pausada"
    # emit para TODOS: ninguém pode pedir nada novo até o Mestre reabrir.
    await sio.emit("vila.pausada", fato(pedido))


# on vila.reinicio_solicitado: PEDIDO do Mestre para começar do zero depois de encerrar.
@sio.on("vila.reinicio_solicitado")
async def reiniciar_vila(sid, dados=None):
    pedido = "vila.reinicio_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre controla a temporada", pedido)
        return
    if estado["fase"] != "encerrada":
        await recusar(sid, "Encerre a temporada antes de começar do zero", pedido)
        return
    rodada = estado["rodada"] + 1
    estado.clear()
    estado.update(copy.deepcopy(ESTADO_INICIAL), rodada=rodada)   # obras antigas conferem a rodada e não terminam
    expedicoes.clear()                             # prazos antigos não acham mais a expedição
    # emit para TODOS: a mina inteira voltou ao começo e todas as telas redesenham.
    await sio.emit("vila.reiniciada", fato(pedido))


# on expedicao.solicitada: PEDIDO do Jogador para mandar um mineiro buscar minério.
@sio.on("expedicao.solicitada")
async def enviar_expedicao(sid, dados=None):
    pedido = "expedicao.solicitada"
    # Mesma regra da construção: valida tudo e só depois altera, sem await no
    # meio, para a disputa pelo último mineiro ter um vencedor só.
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores constroem e enviam expedições"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif sid in expedicoes:
        motivo = "Você já tem uma expedição em andamento"
    elif estado["mineiros"] >= estado["limite"]:
        motivo = "Sem mineiro livre"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    nome = jogadores[sid]["nome"]
    expedicao = {"nome": nome, "saida": time.monotonic()}
    expedicoes[sid] = expedicao
    estado["mineiros"] += 1
    estado["expedicoes"] += 1
    # emit para TODOS: um mineiro saiu e ficou ocupado para a vila inteira.
    await sio.emit("expedicao.iniciada", fato(pedido, por=nome, prazo=PRAZO_EXPEDICAO))
    sio.start_background_task(prazo_expedicao, sid, expedicao)


# on expedicao.retorno_solicitado: PEDIDO do Jogador para chamar o mineiro de volta.
@sio.on("expedicao.retorno_solicitado")
async def retornar_expedicao(sid, dados=None):
    pedido = "expedicao.retorno_solicitado"
    if estado["fase"] not in ("aberta", "pausada"):   # na pausa ainda dá para chamar de volta
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    expedicao = expedicoes.pop(sid, None)
    if expedicao is None:
        # Também cai aqui quem pede o retorno logo depois do prazo vencer: o
        # temporizador chegou primeiro e a expedição já foi perdida.
        await recusar(sid, "Você não tem expedição em andamento", pedido)
        return
    segundos = int(time.monotonic() - expedicao["saida"])
    trazido = segundos * MINERIO_POR_SEGUNDO
    estado["minerio"] += trazido
    estado["mineiros"] -= 1
    estado["expedicoes"] -= 1
    # emit para TODOS: o minério entrou no estoque e o mineiro está livre.
    await sio.emit("expedicao.retornada",
                   fato(pedido, por=expedicao["nome"], segundos=segundos, minerio=trazido))


# Temporizador do prazo: se a expedição não voltou a tempo, a carga se perde.
async def prazo_expedicao(sid, expedicao):
    await sio.sleep(PRAZO_EXPEDICAO)
    # Só perde se for ESTA expedição e ela ainda estiver fora (o jogador pode
    # ter chamado de volta antes, ou já ter mandado outra depois).
    if estado["fase"] not in ("aberta", "pausada") or expedicoes.get(sid) is not expedicao:
        return
    del expedicoes[sid]
    estado["mineiros"] -= 1
    estado["expedicoes"] -= 1
    # emit para TODOS: o mineiro voltou sem nada e ficou livre de novo.
    causa = "expedicao.iniciada (temporizador)"
    await sio.emit("expedicao.perdida", fato(causa, por=expedicao["nome"]))
