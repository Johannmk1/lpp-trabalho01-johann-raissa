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
