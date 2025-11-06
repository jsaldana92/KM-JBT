# scenes/jbt_game.py
import os
import time
import random
import pygame
from pygame.locals import *

# ---------- optional joystick init ----------
pygame.joystick.init()
for i in range(pygame.joystick.get_count()):
    try:
        js = pygame.joystick.Joystick(i)
        js.init()
    except Exception:
        pass

# ---------- hardware pellet (optional) ----------
try:
    from Matts_Dual_Toolbox import pellet as _hw_pellet  # side: 0 (left), 1 (right)
except Exception:
    _hw_pellet = None

# --- tuning knobs ---
START_BASE   = (150, 75)   # legacy size at 800x600
STIM_BASE    = (200, 150)  # legacy size at 800x600

START_SCALE  = 0.70        # smaller start bar (1.0 = original)
STIM_SCALE   = 0.75        # smaller stimulus

CURSOR_SPEED_PER_W = 0.005 # cursor speed factor
JOYSTICK_DEADZONE  = 0.20  # horizontal axis deadzone

# ---------- sounds (cached) ----------
_SOUNDS = None
def _load_sounds():
    global _SOUNDS
    if _SOUNDS is not None:
        return _SOUNDS
    pygame.mixer.init()
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    start_chime    = pygame.mixer.Sound(os.path.join(base, "start_chime.wav"))  # not used in JBT
    correct_snd    = pygame.mixer.Sound(os.path.join(base, "correct.wav"))
    incorrect_snd  = pygame.mixer.Sound(os.path.join(base, "incorrect.wav"))
    _SOUNDS = {
        "start": start_chime,
        "correct": correct_snd,
        "incorrect": incorrect_snd,
    }
    return _SOUNDS

# ---------- profiles (easy to extend) ----------
PROFILES = {
    "Dark S+": {
        "S+":  (105,105,105),
        "NP":  (115,115,115),
        "INT": (125,125,125),
        "NN":  (135,135,135),
        "S-":  (145,145,145),
    },
    "Light S+": {
        "S+":  (145,145,145),
        "NP":  (135,135,135),
        "INT": (125,125,125),
        "NN":  (115,115,115),
        "S-":  (105,105,105),
    },
}

# ---------- helpers ----------
def _clamp(v, lo, hi): return max(lo, min(hi, v))

def _half_rects(screen_w, screen_h, mid_thickness=12):
    mid_x = screen_w // 2
    left  = pygame.Rect(0, 0, mid_x, screen_h)
    right = pygame.Rect(mid_x, 0, screen_w - mid_x, screen_h)
    mid   = pygame.Rect(mid_x - mid_thickness // 2, 0, mid_thickness, screen_h)
    return left, right, mid

def _move_horizontal(keys, joystick, left_key, right_key, speed):
    dx = 0
    if keys[left_key]:  dx -= 1
    if keys[right_key]: dx += 1
    if joystick and joystick.get_init():
        try:
            ax_x = joystick.get_axis(0)
        except Exception:
            ax_x = 0.0
        if abs(ax_x) > JOYSTICK_DEADZONE:
            dx += ax_x
    if dx:
        mag = max(1e-6, abs(dx))
        dx = dx / mag
    return int(dx * speed)

def _is_correct(label):  # Only S+ is “correct”
    return (label or "").upper() == "S+"

# ---- per-SIDE, block-balanced stimulus decks (left/right halves) ----
_BLOCK_TEMPLATE = ["S+","S+","S-","S-","NP","NN","INT"]

def _init_jbt_side_decks(state):
    """
    Ensures state['progress']['jbt_decks_sides'] exists with keys 'left' and 'right',
    each holding a list that functions as a per-side deck.
    """
    p = state.setdefault("progress", {})
    decks = p.setdefault("jbt_decks_sides", {})
    decks.setdefault("left", [])
    decks.setdefault("right", [])
    return decks

def _refill_and_shuffle(deck):
    deck[:] = list(_BLOCK_TEMPLATE)
    random.shuffle(deck)

def _next_label_for_side(state, side_key):
    """
    side_key: 'left' or 'right'
    Returns next label from that side's 7-trial block (refilling when empty).
    """
    decks = _init_jbt_side_decks(state)
    deck = decks[side_key]
    if not deck:
        _refill_and_shuffle(deck)
    return deck.pop().upper()

# =============== JBT Scene ===============
def run(screen, clock, state, player, stimulus_label=None):
    """
    Run one NoGo-like JBT for `player` ('leader' | 'follower').

    Stimulus selection (PER SIDE):
      - If `stimulus_label` is provided, it is used (testing/override).
      - Otherwise, the active side pulls from its own 7-trial block: 2 S+, 2 S-, 1 NP, 1 NN, 1 INT (random order).
        Sides ('left' and 'right') are tracked independently across the session.

    Visuals/flow:
      - Screen split like KM. Only the ACTIVE half has blue background; the other is white.
      - START bar: solid BLUE (0,0,255), thick BLACK border, square corners, 150x75@800x600 scaling.
      - Cursor spawns mid-right of active half; movement is HORIZONTAL ONLY.
      - Touch START -> it disappears; stimulus appears middle-far-right (square corners).
      - Stimulus visible up to 5s. If collided:
          * If S+: play correct, pellet, wait 1500ms, pellet, play correct, 2s ITI.
          * Else (S-, NP, NN, INT): no sound, no pellets, 2s ITI.
        If timeout on S+: play incorrect, 2s ITI (no pellets).
      - Returns dict or None on abort.
    """
    W, H = screen.get_size()
    scale = H / 600.0  # keeps “classic 800x600” proportions

    # colors
    WHITE = (255,255,255)
    BLACK = (0,0,0)
    BLUE_BG = (125,125,255)  # active half background
    START_FILL = (0,0,255)   # start bar fill (pure blue)

    # layout
    left_rect, right_rect, mid_rect = _half_rects(W, H, mid_thickness=12)

    # which side is leader (like KM)
    left_name  = state["config"].get("left_name", state["config"]["leader"])
    leader_is_left = (state["config"]["leader"] == left_name)

    # which half is ACTIVE for this call?
    active_half = left_rect if ((player == "leader" and leader_is_left) or (player == "follower" and not leader_is_left)) else right_rect
    side_key = "left" if active_half == left_rect else "right"

    # joysticks
    js_left  = pygame.joystick.Joystick(0) if pygame.joystick.get_count() > 0 else None
    js_right = pygame.joystick.Joystick(1) if pygame.joystick.get_count() > 1 else None
    use_wasd = (active_half == left_rect)
    js = js_left if use_wasd else js_right
    key_left, key_right = (K_a, K_d) if use_wasd else (K_LEFT, K_RIGHT)

    # cursor
    CURSOR_COLOR = (255,0,0)
    R = max(8, int(min(W, H) * 0.02))
    speed = max(3, int(W * CURSOR_SPEED_PER_W))
    cursor_pos = [active_half.x + int(active_half.width * 0.75), active_half.centery]

    # START bar — square corners, thick black border
    start_w = int(START_BASE[0] * scale * START_SCALE)
    start_h = int(START_BASE[1] * scale * START_SCALE)
    start_rect = pygame.Rect(0, 0, start_w, start_h)
    start_rect.center = (active_half.x + int(active_half.width * 0.25), active_half.centery)
    start_border_w = max(6, int(6 * scale))

    # STIM — square corners
    stim_w = int(STIM_BASE[0] * scale * STIM_SCALE)
    stim_h = int(STIM_BASE[1] * scale * STIM_SCALE)
    stim_rect = pygame.Rect(0, 0, stim_w, stim_h)
    stim_rect.center = (active_half.x + int(active_half.width * 0.80), active_half.centery)

    # profile color
    profile_name = state["config"].get("stimuli", "Dark S+")
    profile = PROFILES.get(profile_name, PROFILES["Dark S+"])

    # choose label: ALWAYS use per-side deck
    stim_label = _next_label_for_side(state, side_key)

    stim_color = profile.get(stim_label, profile["S+"])

    # which dispenser corresponds to this active side?
    dispense_side = 0 if side_key == "left" else 1

    sounds = _load_sounds()

    # -------- draw helpers (match look) --------
    def draw_base_only_active():
        """Other half stays white; only ACTIVE half is blue; show divider + borders."""
        screen.fill(WHITE)
        pygame.draw.rect(screen, BLUE_BG, active_half)
        pygame.draw.rect(screen, BLACK, mid_rect)
        pygame.draw.rect(screen, BLACK, left_rect, 2)
        pygame.draw.rect(screen, BLACK, right_rect, 2)

    def draw_start_phase():
        draw_base_only_active()
        pygame.draw.rect(screen, START_FILL, start_rect)             # fill
        pygame.draw.rect(screen, BLACK, start_rect, start_border_w)  # thick black border
        pygame.draw.circle(screen, CURSOR_COLOR, cursor_pos, R)
        pygame.display.flip()

    def draw_stim_phase():
        draw_base_only_active()
        pygame.draw.rect(screen, stim_color, stim_rect)
        pygame.draw.circle(screen, CURSOR_COLOR, cursor_pos, R)
        pygame.display.flip()

    def clear_active_half():
        draw_base_only_active()
        pygame.display.flip()

    # ----------------- Phase 1: Start (horizontal-only) -----------------
    start_touched = False
    while not start_touched:
        for ev in pygame.event.get():
            if ev.type == QUIT: return None
            if ev.type == KEYDOWN and ev.key in (K_ESCAPE, K_q): return None

        keys = pygame.key.get_pressed()
        dx = _move_horizontal(keys, js, key_left, key_right, speed)
        cursor_pos[0] = _clamp(cursor_pos[0] + dx, active_half.left + R, active_half.right - R - 1)

        draw_start_phase()

        if start_rect.collidepoint(cursor_pos):
            start_touched = True

        clock.tick(60)

    # after start: go to stim
    stim_onset = time.perf_counter()

    # ----------------- Phase 2: Stimulus (max 5s) -----------------
    selected = False
    max_stim_sec = 5.0

    # fields for CSV logging
    collided = False
    rt_ms = 0
    while not selected:
        for ev in pygame.event.get():
            if ev.type == QUIT: return None
            if ev.type == KEYDOWN and ev.key in (K_ESCAPE, K_q): return None

        keys = pygame.key.get_pressed()
        dx = _move_horizontal(keys, js, key_left, key_right, speed)
        cursor_pos[0] = _clamp(cursor_pos[0] + dx, active_half.left + R, active_half.right - R - 1)

        draw_stim_phase()

        # selection
        if stim_rect.collidepoint(cursor_pos):
            selected = True
            collided = True
            rt_ms = int((time.perf_counter() - stim_onset) * 1000)

            # Immediately hide BOTH stimulus and cursor
            clear_active_half()

            if _is_correct(stim_label):
                # 1) play correct
                if "correct" in sounds: sounds["correct"].play()
                # 2) first pellet
                if _hw_pellet is not None:
                    try: _hw_pellet(side=dispense_side, num=1)
                    except Exception: pass
                # 3) wait ~1500ms
                pygame.time.delay(1500)
                # 4) second pellet
                if _hw_pellet is not None:
                    try: _hw_pellet(side=dispense_side, num=1)
                    except Exception: pass
                # 5) play correct again
                if "correct" in sounds: sounds["correct"].play()
            break


        # timeout while showing stim (only matters for S+)
        if (time.perf_counter() - stim_onset) >= max_stim_sec:
            clear_active_half()
            collided = False
            rt_ms = int(max_stim_sec * 1000)
            if _is_correct(stim_label):
                if "incorrect" in sounds: sounds["incorrect"].play()
            selected = True
            break

        clock.tick(60)

    # 2s ITI before returning control (keeps 2s gap toward the next trio)
    pygame.time.delay(2000)

    return {
    "player": player,
    "stimulus": stim_label,
    "collided": collided,  # bool
    "rt_ms": rt_ms,        # int milliseconds to stimulus (not start button)
    }
