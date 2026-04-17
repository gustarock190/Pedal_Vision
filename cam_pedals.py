
# =============================================================================
# CAM PEDALS — Pedais virtuais por câmera
# =============================================================================
# Rastreia dois objetos na câmera e mapeia o movimento como pedais de jogo.
# Usa template matching — clique no objeto e ele segue a textura, não a cor.
#
# Como usar:
#   1. pip install opencv-python vgamepad numpy
#   2. python cam_pedals.py
#   3. Clique no marcador do ACELERADOR
#   4. Clique no marcador do FREIO
#   5. Mova os objetos — os pedais respondem!
#
# Teclas: R = resetar | Q = sair
# =============================================================================

import cv2
import numpy as np

try:
    import vgamepad as vg
    gamepad = vg.VX360Gamepad()
    GAMEPAD = True
except:
    GAMEPAD = False
    print("vgamepad nao encontrado — rodando sem gamepad")

CAMERA        = 0
REGIAO        = 40    # tamanho do recorte capturado ao clicar (pixels)
SENSIBILIDADE = 80    # pixels de movimento = 100% do pedal
MARGEM_X      = 120   # cada marcador só busca dentro de ±MARGEM_X do X inicial

camera = cv2.VideoCapture(CAMERA)

marcadores = {
    "acelerador": {"template": None, "cx_inicial": None, "cy_inicial": None,
                   "cx": None, "cy": None, "pressao": 0.0, "cor": (0, 210, 0)},
    "freio":      {"template": None, "cx_inicial": None, "cy_inicial": None,
                   "cx": None, "cy": None, "pressao": 0.0, "cor": (0, 0, 210)},
}
ordem       = ["acelerador", "freio"]
passo       = 0
frame_atual = None


def capturar_template(frame, x, y):
    """Salva um recorte da região clicada como referência de rastreamento."""
    h, w = frame.shape[:2]
    x1 = max(0, x - REGIAO // 2)
    x2 = min(w, x + REGIAO // 2)
    y1 = max(0, y - REGIAO // 2)
    y2 = min(h, y + REGIAO // 2)
    return frame[y1:y2, x1:x2].copy()


def encontrar_objeto(frame, m):
    """
    Busca o template dentro de uma faixa horizontal limitada ao redor do
    X inicial do clique. Isso impede que um marcador "pule" para o outro.

    Retorna (cx, cy) do objeto encontrado, ou None se não achar.
    """
    if m["template"] is None or m["cx_inicial"] is None:
        return None

    h, w = frame.shape[:2]
    th, tw = m["template"].shape[:2]

    # Limitamos a busca a uma faixa horizontal em torno do X inicial
    x1_busca = max(0, m["cx_inicial"] - MARGEM_X - tw // 2)
    x2_busca = min(w, m["cx_inicial"] + MARGEM_X + tw // 2)

    regiao_busca = frame[:, x1_busca:x2_busca]

    # Verificamos se a região é grande o suficiente para o template
    if regiao_busca.shape[1] < tw or regiao_busca.shape[0] < th:
        return None

    resultado  = cv2.matchTemplate(regiao_busca, m["template"], cv2.TM_CCOEFF_NORMED)
    _, conf, _, pos = cv2.minMaxLoc(resultado)

    if conf < 0.5:
        return None

    # Convertemos a posição local da faixa de volta para coordenadas do frame
    cx = x1_busca + pos[0] + tw // 2
    cy =            pos[1] + th // 2
    return cx, cy


def ao_clicar(evento, x, y, flags, param):
    """Captura o clique e registra o template e posição inicial do marcador."""
    global passo
    if evento != cv2.EVENT_LBUTTONDOWN or frame_atual is None or passo >= 2:
        return

    nome = ordem[passo]
    marcadores[nome]["template"]   = capturar_template(frame_atual, x, y)
    marcadores[nome]["cx_inicial"] = x
    marcadores[nome]["cy_inicial"] = y
    marcadores[nome]["cx"]         = x
    marcadores[nome]["cy"]         = y
    marcadores[nome]["pressao"]    = 0.0
    print(f"[✓] {nome.upper()} marcado em ({x}, {y})")
    passo += 1
    if passo == 1:
        print("Clique no marcador do FREIO...")
    elif passo == 2:
        print("Rastreando! Mova os objetos.")


cv2.namedWindow("Cam Pedals")
cv2.setMouseCallback("Cam Pedals", ao_clicar)
print("Clique no marcador do ACELERADOR...")

while True:
    ok, frame = camera.read()
    if not ok:
        break

    frame       = cv2.flip(frame, 1)
    frame_atual = frame.copy()
    h, w        = frame.shape[:2]

    if passo < 2:
        # --- Setup ---
        instrucao = ("1. Clique no marcador do ACELERADOR"
                     if passo == 0 else "2. Clique no marcador do FREIO")
        cv2.putText(frame, instrucao, (20, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 220, 0), 2)

    else:
        # --- Rastreamento ---
        for nome, m in marcadores.items():
            resultado = encontrar_objeto(frame, m)

            if resultado is None:
                # Objeto perdido — mantém último valor e avisa
                cv2.putText(frame, f"! {nome.upper()} PERDIDO",
                            (10, 110 if nome == "acelerador" else 145),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 140, 255), 2)
            else:
                m["cx"], m["cy"] = resultado

                # Pressão = deslocamento vertical em relação ao Y inicial
                delta      = abs(m["cy"] - m["cy_inicial"])
                m["pressao"] = float(min(delta / SENSIBILIDADE, 1.0))

                # Desenha retângulo ao redor do objeto
                th, tw = m["template"].shape[:2]
                cv2.rectangle(frame,
                              (m["cx"] - tw // 2, m["cy"] - th // 2),
                              (m["cx"] + tw // 2, m["cy"] + th // 2),
                              m["cor"], 2)

                # Linha mostrando deslocamento desde o Y inicial
                cv2.circle(frame, (m["cx"], m["cy_inicial"]), 5, (120, 120, 120), -1)
                cv2.line(frame, (m["cx"], m["cy_inicial"]),
                                (m["cx"], m["cy"]), m["cor"], 2)

                # Percentual ao lado
                cv2.putText(frame, f"{int(m['pressao'] * 100)}%",
                            (m["cx"] + tw // 2 + 8, m["cy"]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.75, m["cor"], 2)

            # Envia ao gamepad (uma única vez, com o valor já calculado)
            if GAMEPAD:
                valor = int(m["pressao"] * 255)
                if nome == "acelerador":
                    gamepad.right_trigger(value=valor)
                else:
                    gamepad.left_trigger(value=valor)
                gamepad.update()

        # HUD com os valores finais (lê diretamente do dict — sem recalcular)
        p_acel  = marcadores["acelerador"]["pressao"]
        p_freio = marcadores["freio"]["pressao"]
        cv2.putText(frame, f"ACELERADOR: {int(p_acel  * 100):3d}%",
                    (10, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 210, 0), 2)
        cv2.putText(frame, f"FREIO:      {int(p_freio * 100):3d}%",
                    (10, 68), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 210), 2)

    cv2.putText(frame, "R=resetar | Q=sair", (20, h - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (130, 130, 130), 1)
    cv2.imshow("Cam Pedals", frame)

    tecla = cv2.waitKey(1) & 0xFF
    if tecla in (ord("q"), ord("Q")):
        break
    elif tecla in (ord("r"), ord("R")):
        passo = 0
        for m in marcadores.values():
            m["template"] = m["cx_inicial"] = m["cy_inicial"] = None
            m["cx"] = m["cy"] = None
            m["pressao"] = 0.0
        print("Resetado. Clique no marcador do ACELERADOR...")

camera.release()
cv2.destroyAllWindows()
