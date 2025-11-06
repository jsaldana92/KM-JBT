# scenes/km_game.py
import os
import time
import random
import pygame
import math
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

# --- tuning knobs (match jbt_game.py where relevant) ---
CURSOR_SPEED_PER_W = 0.005   # lower = slower, higher = faster
JOYSTICK_DEADZONE  = 0.20    # horizontal/vertical stick deadzone

# START bar proportions (mirrors jbt_game look/feel)
START_BASE   = (150, 75)   # legacy size at 800x600
START_SCALE  = 0.70        # smaller start bar (1.0 = original)
START_FILL   = (0, 0, 255) # solid blue
START_BORDER = 6           # base border scale (multiplied by H/600 later)

# ---------- sounds (cached) ----------
_SOUNDS = None
def _load_sounds():
    """
    Loads and caches the start/select/pellet sounds from assets/.
    Safe to call repeatedly.
    """
    global _SOUNDS
    if _SOUNDS is not None:
        return _SOUNDS
    pygame.mixer.init()
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
    start_chime = pygame.mixer.Sound(os.path.join(base, "start_chime.wav"))
    select_snd  = pygame.mixer.Sound(os.path.join(base, "select.mp3"))
    pellet_snd  = pygame.mixer.Sound(os.path.join(base, "pellet_ding.mp3"))
    _SOUNDS = {
        "start": start_chime,
        "select": select_snd,
        "pellet": pellet_snd,
    }
    return _SOUNDS

# ---------- helpers ----------
def _clamp(v, lo, hi): return max(lo, min(hi, v))

def _half_rects(screen_w, screen_h, mid_thickness=12):
    mid_x = screen_w // 2
    left  = pygame.Rect(0, 0, mid_x, screen_h)
    right = pygame.Rect(mid_x, 0, screen_w - mid_x, screen_h)
    mid   = pygame.Rect(mid_x - mid_thickness // 2, 0, mid_thickness, screen_h)
    return left, right, mid

def _move_from_input(keys, joystick, up, down, left, right, speed):
    dx = dy = 0
    if keys[up]: dy -= 1
    if keys[down]: dy += 1
    if keys[left]: dx -= 1
    if keys[right]: dx += 1
    if joystick and joystick.get_init():
        try:
            ax_x = joystick.get_axis(0); ax_y = joystick.get_axis(1)
        except Exception:
            ax_x = ax_y = 0.0
        if abs(ax_x) > JOYSTICK_DEADZONE: dx += ax_x
        if abs(ax_y) > JOYSTICK_DEADZONE: dy += ax_y
    if dx or dy:
        mag = max(1e-6, (dx*dx + dy*dy) ** 0.5)
        dx /= mag; dy /= mag
    return int(dx * speed), int(dy * speed)

def _choice_to_pellets(choice): return 4 if choice == "K" else 1

def _draw_centered_text(surface, text, font, color, center):
    t = font.render(text, True, color)
    surface.blit(t, t.get_rect(center=center))

# ---- K/M stimulus drawing (new designs) ----
def _draw_K_box(surface, rect):
    """
    K = Dark PURPLE square with a BRIGHT ORANGE star in the middle.
    Includes a thin outline on the star for luminance contrast.
    """
    PURPLE_SQUARE   = (72, 0, 110)     # dark purple
    ORANGE_STAR     = (255, 160, 0)    # bright orange
    STAR_OUTLINE    = (0, 0, 0)        # thin black outline

    pygame.draw.rect(surface, PURPLE_SQUARE, rect, border_radius=10)

    cx, cy = rect.center
    r_outer = min(rect.width, rect.height) * 0.32
    r_inner = r_outer * 0.45

    # build 5-point star (10 points alternating outer/inner), pointing up
    def star_points(scale=1.0):
        pts = []
        for i in range(10):
            ang_deg = -90 + i * 36
            ang = math.radians(ang_deg)
            r = (r_outer if i % 2 == 0 else r_inner) * scale
            x = int(cx + r * math.cos(ang))
            y = int(cy + r * math.sin(ang))
            pts.append((x, y))
        return pts

    # outline first (slightly larger), then fill
    pygame.draw.polygon(surface, STAR_OUTLINE, star_points(scale=1.06))
    pygame.draw.polygon(surface, ORANGE_STAR, star_points(scale=1.0))



def _draw_M_box(surface, rect):
    """
    M = Dark TEAL square with a LIGHT YELLOW circle in the middle.
    Includes a thin outline on the circle for luminance contrast.
    """
    TEAL_SQUARE      = (0, 100, 110)   # dark teal
    YELLOW_CIRCLE    = (255, 245, 170) # light yellow
    CIRCLE_OUTLINE   = (0, 0, 0)       # thin black outline

    pygame.draw.rect(surface, TEAL_SQUARE, rect, border_radius=10)

    cx, cy = rect.center
    r = int(min(rect.width, rect.height) * 0.28)

    # outline ring (slightly larger), then fill
    pygame.draw.circle(surface, CIRCLE_OUTLINE, (cx, cy), r + 3)
    pygame.draw.circle(surface, YELLOW_CIRCLE, (cx, cy), r)


# ---- START bar draw (JBT style) ----
def _draw_start_bar(surface, rect, border_px):
    BLACK = (0, 0, 0)
    pygame.draw.rect(surface, START_FILL, rect)                    # fill
    pygame.draw.rect(surface, BLACK, rect, border_px)              # thick black border (square corners)

# ---- Pseudorandomization of K/M left-right per half ----
def _pick_km_layout(history_list):
    """
    history_list: list of previous assignments for this half, each 'K_left' or 'M_left'
    Rule: do not allow the same assignment more than 2 times consecutively.
    Returns: 'K_left' or 'M_left', and updates history_list in-place.
    """
    # candidates
    candidates = ["K_left", "M_left"]
    # block >2 in a row
    if len(history_list) >= 2 and history_list[-1] == history_list[-2]:
        blocked = history_list[-1]
        candidates = [c for c in candidates if c != blocked]

    choice = random.choice(candidates)
    history_list.append(choice)
    # cap history length
    if len(history_list) > 12:
        del history_list[:len(history_list) - 12]
    return choice


def _ensure_km_histories(state, left_key, right_key):
    p = state.setdefault("progress", {})
    if left_key not in p:
        p[left_key] = []
    if right_key not in p:
        p[right_key] = []

# =============== KM Scene ===============
def run(screen, clock, state):
    """
    KM trial scene. Returns dict with:
      leader_side: "L"/"R"
      leader_choice: "K"/"M"
      follower_choice: "K"/"M"
      leader_choice_time: float seconds
      follower_choice_time: float seconds
    or None if aborted (e.g., timeout or ESC).
    """
    W, H = screen.get_size()
    scale = H / 600.0

    # colors / fonts
    BG = (255,255,255)
    BLACK=(0,0,0)
    CURSOR_COLOR=(255,0,0)

    FONT = pygame.font.SysFont("Calibri", max(18, int(H*0.025)))
    BIG  = pygame.font.SysFont("Calibri", max(28, int(H*0.06)), bold=True)

    sounds = _load_sounds()

    # leader side per UI state (stored in launch)
    left_name  = state["config"].get("left_name", state["config"]["leader"])
    right_name = state["config"].get("right_name", state["config"]["follower"])
    leader_is_left = (state["config"]["leader"] == left_name)
    leader_side = "L" if leader_is_left else "R"

    left_rect, right_rect, mid_rect = _half_rects(W, H, mid_thickness=12)

    # cursors
    R = max(8, int(min(W, H) * 0.02))
    left_pos  = [left_rect.centerx,  H//2]
    right_pos = [right_rect.centerx, H//2]
    lower_y = int(H*0.70)

    # START bar (JBT style)
    start_w = int(START_BASE[0] * scale * START_SCALE)
    start_h = int(START_BASE[1] * scale * START_SCALE)
    start_rect = pygame.Rect(0,0,start_w,start_h); start_rect.center=(W//2, H//2)
    start_border_w = max(6, int(START_BORDER * scale))

    # K/M boxes
    box_w = max(90, int(W*0.10)); box_h = max(90, int(W*0.10))
    def choice_rects(for_left_half: bool):
        if for_left_half:
            cxL = left_rect.x + left_rect.width//4
            cxR = left_rect.x + (3*left_rect.width)//4
            top = int(H*0.15)
        else:
            cxL = right_rect.x + right_rect.width//4
            cxR = right_rect.x + (3*right_rect.width)//4
            top = int(H*0.15)
        rL = pygame.Rect(0,0,box_w,box_h); rL.center=(cxL, top+box_h//2)
        rR = pygame.Rect(0,0,box_w,box_h); rR.center=(cxR, top+box_h//2)
        return rL, rR  # left-spot, right-spot for this half

    # layout rect pairs (positions on each half)
    lead_Lspot, lead_Rspot = choice_rects(leader_is_left)
    foll_Lspot, foll_Rspot = choice_rects(not leader_is_left)

    # pseudorandomize K/M placement per half
    # histories are tracked per-side so each half respects the "no > 2 in a row" rule independently
    _ensure_km_histories(state, "km_history_leader_half", "km_history_follower_half")
    lead_layout = _pick_km_layout(state["progress"]["km_history_leader_half"])     # 'K_left' or 'M_left'
    foll_layout = _pick_km_layout(state["progress"]["km_history_follower_half"])   # 'K_left' or 'M_left'

    # for leader half
    if lead_layout == "K_left":
        rK_lead, rM_lead = lead_Lspot, lead_Rspot
    else:
        rK_lead, rM_lead = lead_Rspot, lead_Lspot
    # for follower half
    if foll_layout == "K_left":
        rK_follow, rM_follow = foll_Lspot, foll_Rspot
    else:
        rK_follow, rM_follow = foll_Rspot, foll_Lspot

    # joysticks (0 -> left, 1 -> right)
    js_left  = pygame.joystick.Joystick(0) if pygame.joystick.get_count()>0 else None
    js_right = pygame.joystick.Joystick(1) if pygame.joystick.get_count()>1 else None
    speed = max(3, int(W * CURSOR_SPEED_PER_W))

    def draw_base():
        screen.fill(BG)
        pygame.draw.rect(screen, BLACK, mid_rect)
        pygame.draw.rect(screen, BLACK, left_rect, 2)
        pygame.draw.rect(screen, BLACK, right_rect, 2)

    # ------------------ START phase (JBT-style bar) ------------------
    left_ready = right_ready = False
    t_first_touch = None
    played_start_chime = False

    left_pos  = [left_rect.centerx,  H//2]
    right_pos = [right_rect.centerx, H//2]

    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT: return None
            if ev.type == KEYDOWN and ev.key in (K_ESCAPE, K_q): return None

        keys = pygame.key.get_pressed()
        dx, dy = _move_from_input(keys, js_left, K_w, K_s, K_a, K_d, speed)
        left_pos[0] = _clamp(left_pos[0]+dx, left_rect.left+R, left_rect.right-R-1)
        left_pos[1] = _clamp(left_pos[1]+dy, left_rect.top +R, left_rect.bottom-R-1)
        dx, dy = _move_from_input(keys, js_right, K_UP, K_DOWN, K_LEFT, K_RIGHT, speed)
        right_pos[0] = _clamp(right_pos[0]+dx, right_rect.left+R, right_rect.right-R-1)
        right_pos[1] = _clamp(right_pos[1]+dy, right_rect.top +R, right_rect.bottom-R-1)

        draw_base()
        _draw_start_bar(screen, start_rect, start_border_w)  # no text, square corners
        pygame.draw.circle(screen, CURSOR_COLOR, left_pos,  R)
        pygame.draw.circle(screen, CURSOR_COLOR, right_pos, R)
        pygame.display.flip()

        if not played_start_chime:
            sounds["start"].play()
            played_start_chime = True

        if not left_ready and start_rect.collidepoint(left_pos):
            left_ready = True
            if t_first_touch is None: t_first_touch = time.perf_counter()
        if not right_ready and start_rect.collidepoint(right_pos):
            right_ready = True
            if t_first_touch is None: t_first_touch = time.perf_counter()

        if t_first_touch and not (left_ready and right_ready):
            if time.perf_counter() - t_first_touch > 2.0:
                left_ready = right_ready = False
                t_first_touch = None
                left_pos  = [left_rect.centerx,  H//2]
                right_pos = [right_rect.centerx, H//2]

        if left_ready and right_ready:
            break

        clock.tick(60)

    # ------------------ Leader phase (30s) ------------------
    leader_choice = follower_choice = None
    leader_time = follower_time = None

    leader_time = follower_time = None
    leader_time_ms = follower_time_ms = 0


    left_pos  = [left_rect.centerx,  lower_y]
    right_pos = [right_rect.centerx, lower_y]


    t0 = time.perf_counter()
    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT: return None
            if ev.type == KEYDOWN and ev.key in (K_ESCAPE, K_q): return None

        keys = pygame.key.get_pressed()
        if leader_is_left:
            dx, dy = _move_from_input(keys, js_left, K_w, K_s, K_a, K_d, speed)
            left_pos[0] = _clamp(left_pos[0]+dx, left_rect.left+R, left_rect.right-R-1)
            left_pos[1] = _clamp(left_pos[1]+dy, left_rect.top +R, left_rect.bottom-R-1)
        else:
            dx, dy = _move_from_input(keys, js_right, K_UP, K_DOWN, K_LEFT, K_RIGHT, speed)
            right_pos[0] = _clamp(right_pos[0]+dx, right_rect.left+R, right_rect.right-R-1)
            right_pos[1] = _clamp(right_pos[1]+dy, right_rect.top +R, right_rect.bottom-R-1)

        elapsed = time.perf_counter() - t0
        if elapsed > 30.0: return None

        draw_base()
        # draw leader choices with new designs
        _draw_K_box(screen, rK_lead)
        _draw_M_box(screen, rM_lead)

        # show ONLY leader cursor pre-choice
        if leader_is_left:
            pygame.draw.circle(screen, CURSOR_COLOR, left_pos,  R)
        else:
            pygame.draw.circle(screen, CURSOR_COLOR, right_pos, R)

        active_pos = left_pos if leader_is_left else right_pos
        if rK_lead.collidepoint(active_pos):
            leader_choice = "K"
            leader_time = elapsed
            leader_time_ms = int(elapsed * 1000)
            sounds["select"].play()
            break
        if rM_lead.collidepoint(active_pos):
            leader_choice = "M"
            leader_time = elapsed
            leader_time_ms = int(elapsed * 1000)
            sounds["select"].play()
            break

        pygame.display.flip()
        clock.tick(60)

    # After leader selects: show ONLY their chosen box, hide everything else.
    chosen_leader_rect = rK_lead if leader_choice == "K" else rM_lead
    def _draw_leader_choice_only():
        draw_base()
        if leader_choice == "K":
            _draw_K_box(screen, chosen_leader_rect)
        else:
            _draw_M_box(screen, chosen_leader_rect)
        pygame.display.flip()

    _draw_leader_choice_only()

    # ---- 0.5s ITI before follower receives reward ----
    pygame.time.delay(500)

    # ---------- Follower receives pellets FIRST ----------
    pellets_to_follower = _choice_to_pellets(leader_choice)
    follower_disp = 1 if leader_is_left else 0

    # Flicker = overlay on leader's chosen box while giving follower pellets (1s spacing)
    overlay_leader = pygame.Surface(chosen_leader_rect.size, pygame.SRCALPHA)
    overlay_leader.fill((255,255,255,200))

    def _blink_and_dispense(rect_to_blink, num_pellets, dispense_side, draw_baseline_fn, overlay_surface):
        """
        Each pellet is a 1.0s cadence:
        - show baseline
        - overlay flash for 0.25s
        - clear overlay (back to baseline immediately)
        - dispense pellet + ding
        - wait remaining 0.75s

        draw_baseline_fn: function that draws the proper baseline for the current context
                        (e.g., _draw_leader_choice_only or _draw_follower_choice_only).
        """
        for _ in range(num_pellets):
            # 1) baseline
            draw_baseline_fn()
            pygame.display.flip()

            # 2) show overlay for ~0.25s
            draw_baseline_fn()
            screen.blit(overlay_surface, rect_to_blink.topleft)
            pygame.display.flip()
            pygame.time.delay(250)

            # 3) clear overlay immediately (back to baseline)
            draw_baseline_fn()
            pygame.display.flip()

            # 4) dispense + ding
            if _hw_pellet is not None:
                try:
                    _hw_pellet(side=dispense_side, num=1)
                except Exception:
                    pass
            if "pellet" in sounds:
                sounds["pellet"].play()

            # 5) remainder of the 1.0s cadence
            pygame.time.delay(750)


    _blink_and_dispense(
    rect_to_blink=chosen_leader_rect,
    num_pellets=pellets_to_follower,
    dispense_side=follower_disp,
    draw_baseline_fn=_draw_leader_choice_only,
    overlay_surface=overlay_leader
    )


    # ------------------ Follower phase (30s) ------------------
    if leader_is_left:
        right_pos = [right_rect.centerx, lower_y]
    else:
        left_pos  = [left_rect.centerx,  lower_y]

    t1 = time.perf_counter()
    while True:
        for ev in pygame.event.get():
            if ev.type == QUIT: return None
            if ev.type == KEYDOWN and ev.key in (K_ESCAPE, K_q): return None

        keys = pygame.key.get_pressed()
        if leader_is_left:
            dx, dy = _move_from_input(keys, js_right, K_UP, K_DOWN, K_LEFT, K_RIGHT, speed)
            right_pos[0] = _clamp(right_pos[0]+dx, right_rect.left+R, right_rect.right-R-1)
            right_pos[1] = _clamp(right_pos[1]+dy, right_rect.top +R, right_rect.bottom-R-1)
        else:
            dx, dy = _move_from_input(keys, js_left, K_w, K_s, K_a, K_d, speed)
            left_pos[0] = _clamp(left_pos[0]+dx, left_rect.left+R, left_rect.right-R-1)
            left_pos[1] = _clamp(left_pos[1]+dy, left_rect.top +R, left_rect.bottom-R-1)

        elapsed = time.perf_counter() - t1
        if elapsed > 30.0: return None

        draw_base()
        # show leader's chosen box (context), but no cursors on leader side
        if leader_choice == "K":
            _draw_K_box(screen, chosen_leader_rect)
        else:
            _draw_M_box(screen, chosen_leader_rect)
        # follower options
        _draw_K_box(screen, rK_follow)
        _draw_M_box(screen, rM_follow)

        # ONLY follower cursor visible pre-choice
        if leader_is_left:
            pygame.draw.circle(screen, CURSOR_COLOR, right_pos, R)
        else:
            pygame.draw.circle(screen, CURSOR_COLOR, left_pos,  R)

        active_pos = right_pos if leader_is_left else left_pos
        if rK_follow.collidepoint(active_pos):
            follower_choice = "K"
            follower_time = elapsed
            follower_time_ms = int(elapsed * 1000)
            sounds["select"].play()
            break
        if rM_follow.collidepoint(active_pos):
            follower_choice = "M"
            follower_time = elapsed
            follower_time_ms = int(elapsed * 1000)
            sounds["select"].play()
            break

        pygame.display.flip()
        clock.tick(60)

    # After follower selects: show ONLY their chosen box, hide everything else.
    chosen_follower_rect = rK_follow if follower_choice=="K" else rM_follow
    def _draw_follower_choice_only():
        draw_base()
        # ALWAYS keep the leader's choice visible
        if leader_choice == "K":
            _draw_K_box(screen, chosen_leader_rect)
        else:
            _draw_M_box(screen, chosen_leader_rect)

        # Then draw the follower's chosen box
        if follower_choice == "K":
            _draw_K_box(screen, chosen_follower_rect)
        else:
            _draw_M_box(screen, chosen_follower_rect)

        pygame.display.flip()

    _draw_follower_choice_only()
    # 0.5s ITI, then leader receives pellets (1s spacing), blink follower choice
    pygame.time.delay(500)

    pellets_to_leader = _choice_to_pellets(follower_choice)
    leader_disp = 0 if leader_is_left else 1

    overlay_follower = pygame.Surface(chosen_follower_rect.size, pygame.SRCALPHA)
    overlay_follower.fill((255,255,255,200))

    _blink_and_dispense(
    rect_to_blink=chosen_follower_rect,
    num_pellets=pellets_to_leader,
    dispense_side=leader_disp,
    draw_baseline_fn=_draw_follower_choice_only,
    overlay_surface=overlay_follower
    )


    # After all pellets, show **both** choices for 2s
    def draw_both_choices():
        draw_base()
        if leader_choice == "K": _draw_K_box(screen, chosen_leader_rect)
        else:                    _draw_M_box(screen, chosen_leader_rect)
        if follower_choice == "K": _draw_K_box(screen, chosen_follower_rect)
        else:                       _draw_M_box(screen, chosen_follower_rect)
        pygame.display.flip()

    draw_both_choices()
    pygame.time.delay(2000)

    # Short ITI if you want to retain one (you asked to keep “all other parts essential the same”);
    # we’ll keep a light 2s ITI as before for pacing before JBT.
    pygame.time.delay(2000)

    paired = f"{leader_choice}{follower_choice}"

    return {
    "leader_side": leader_side,
    "leader_choice": leader_choice,
    "follower_choice": follower_choice,
    "leader_choice_time": round(leader_time or 0.0, 3),
    "follower_choice_time": round(follower_time or 0.0, 3),
    "leader_choice_time_ms": leader_time_ms,
    "follower_choice_time_ms": follower_time_ms,
    }
