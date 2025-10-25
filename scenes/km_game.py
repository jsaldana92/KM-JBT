# scenes/km_game.py
import os
import time
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

# --- tuning knobs (match jbt_game.py) ---
CURSOR_SPEED_PER_W = 0.005   # 0.006 was faster; lower = slower, higher = faster
JOYSTICK_DEADZONE  = 0.20    # horizontal/vertical stick deadzone

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

def _draw_centered_text(surface, text, font, color, center):
    t = font.render(text, True, color)
    surface.blit(t, t.get_rect(center=center))

def _draw_box(surface, rect, color, label, font, label_color=(255,255,255)):
    pygame.draw.rect(surface, color, rect, border_radius=10)
    _draw_centered_text(surface, label, font, label_color, rect.center)

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

    # colors / fonts
    BG = (255,255,255)
    BLACK=(0,0,0); BLUE=(0,90,180); ORANGE=(240,120,30); WHITE=(255,255,255)
    CURSOR_COLOR=(255,0,0)

    FONT = pygame.font.SysFont("Calibri", max(18, int(H*0.025)))
    BIG  = pygame.font.SysFont("Calibri", max(28, int(H*0.06)), bold=True)

    sounds = _load_sounds()

    # leader side per UI state
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

    # start button
    start_w = max(160, int(W*0.20)); start_h = max(60, int(H*0.08))
    start_rect = pygame.Rect(0,0,start_w,start_h); start_rect.center=(W//2, H//2)
    start_color = (0,60,140)

    # K/M boxes
    box_w = max(80, int(W*0.10)); box_h = max(80, int(W*0.10))
    def choice_rects(for_left_half: bool):
        if for_left_half:
            cxL = left_rect.x + left_rect.width//4
            cxR = left_rect.x + (3*left_rect.width)//4
            top = int(H*0.15)
        else:
            cxL = right_rect.x + right_rect.width//4
            cxR = right_rect.x + (3*right_rect.width)//4
            top = int(H*0.15)
        rK = pygame.Rect(0,0,box_w,box_h); rK.center=(cxL, top+box_h//2)
        rM = pygame.Rect(0,0,box_w,box_h); rM.center=(cxR, top+box_h//2)
        return rK, rM

    rK_lead,   rM_lead   = choice_rects(leader_is_left)
    rK_follow, rM_follow = choice_rects(not leader_is_left)

    # joysticks (0 -> left, 1 -> right)
    js_left  = pygame.joystick.Joystick(0) if pygame.joystick.get_count()>0 else None
    js_right = pygame.joystick.Joystick(1) if pygame.joystick.get_count()>1 else None
    speed = max(3, int(W * CURSOR_SPEED_PER_W))


    def draw_base():
        screen.fill(BG)
        pygame.draw.rect(screen, BLACK, mid_rect)
        pygame.draw.rect(screen, BLACK, left_rect, 2)
        pygame.draw.rect(screen, BLACK, right_rect, 2)

    # ------------------ START phase ------------------
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
        pygame.draw.rect(screen, start_color, start_rect, border_radius=10)
        _draw_centered_text(screen, "START", BIG, WHITE, start_rect.center)
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
        _draw_box(screen, rK_lead, ORANGE, "K", BIG)
        _draw_box(screen, rM_lead, BLUE,   "M", BIG)

        # show ONLY leader cursor pre-choice
        if leader_is_left:
            pygame.draw.circle(screen, CURSOR_COLOR, left_pos,  R)
        else:
            pygame.draw.circle(screen, CURSOR_COLOR, right_pos, R)

        active_pos = left_pos if leader_is_left else right_pos
        if rK_lead.collidepoint(active_pos):
            leader_choice = "K"; leader_time = elapsed; sounds["select"].play(); break
        if rM_lead.collidepoint(active_pos):
            leader_choice = "M"; leader_time = elapsed; sounds["select"].play(); break

        pygame.display.flip()
        clock.tick(60)

    # Freeze leader choice (NO cursors). 1s delay, **NO ding here** (follower starts silently).
    chosen_leader_rect = rK_lead if leader_choice == "K" else rM_lead
    draw_base()
    _draw_box(screen, chosen_leader_rect, ORANGE if leader_choice=="K" else BLUE, leader_choice, BIG)
    pygame.display.flip()
    pygame.time.delay(1000)  # keep the pause, but no sound

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
        # leader chosen (no cursor)
        _draw_box(screen, chosen_leader_rect, ORANGE if leader_choice=="K" else BLUE, leader_choice, BIG)
        # follower options
        _draw_box(screen, rK_follow, ORANGE, "K", BIG)
        _draw_box(screen, rM_follow, BLUE,   "M", BIG)

        # ONLY follower cursor visible pre-choice
        if leader_is_left:
            pygame.draw.circle(screen, CURSOR_COLOR, right_pos, R)
        else:
            pygame.draw.circle(screen, CURSOR_COLOR, left_pos,  R)

        active_pos = right_pos if leader_is_left else left_pos
        if rK_follow.collidepoint(active_pos):
            follower_choice = "K"; follower_time = elapsed; sounds["select"].play(); break
        if rM_follow.collidepoint(active_pos):
            follower_choice = "M"; follower_time = elapsed; sounds["select"].play(); break

        pygame.display.flip()
        clock.tick(60)

    # Freeze both choices (NO cursors). 1s delay + ding (keep this one).
    chosen_follower_rect = rK_follow if follower_choice=="K" else rM_follow
    draw_base()
    _draw_box(screen, chosen_leader_rect,   ORANGE if leader_choice=="K"   else BLUE,   leader_choice,   BIG)
    _draw_box(screen, chosen_follower_rect, ORANGE if follower_choice=="K" else BLUE,   follower_choice, BIG)
    pygame.display.flip()
    pygame.time.delay(1000)
    if "pellet" in sounds: sounds["pellet"].play()

    # ------------------ Rewards (blink only the chosen stimulus) ------------------
    # leader’s choice -> follower pellets; follower’s choice -> leader pellets
    pellets_to_follower = _choice_to_pellets(leader_choice)    # follower gets this many
    pellets_to_leader   = _choice_to_pellets(follower_choice)  # leader  gets this many

    # Which physical dispenser to use (0=left, 1=right)
    leader_disp   = 0 if leader_is_left else 1
    follower_disp = 1 if leader_is_left else 0

    # Colors for chosen boxes
    color_leader   = ORANGE if leader_choice   == "K" else BLUE
    color_follower = ORANGE if follower_choice == "K" else BLUE

    # Overlay to “opaque” the blinking box
    overlay_leader   = pygame.Surface(chosen_leader_rect.size,   pygame.SRCALPHA); overlay_leader.fill((255,255,255,200))
    overlay_follower = pygame.Surface(chosen_follower_rect.size, pygame.SRCALPHA); overlay_follower.fill((255,255,255,200))

    def draw_final_baseline():
        """Draw both chosen boxes in normal (non-blinking) state, no cursors."""
        draw_base()
        _draw_box(screen, chosen_leader_rect,   color_leader,   leader_choice,   BIG)
        _draw_box(screen, chosen_follower_rect, color_follower, follower_choice, BIG)

    def blink_box(rect_to_blink, overlay_surface, times, dispense_side):
        """
        Blink only the provided chosen box `times` times.
        Each blink: baseline -> (dispense+ding) overlay ~250ms -> baseline ~750ms (≈1s cadence).
        """
        for _ in range(times):
            # baseline (both boxes normal)
            draw_final_baseline()
            pygame.display.flip()

            # dispense one pellet + ding
            if _hw_pellet is not None:
                try:
                    _hw_pellet(side=dispense_side, num=1)
                except Exception:
                    pass
            if "pellet" in sounds:
                sounds["pellet"].play()

            # overlay on the blinking box ~250ms
            draw_final_baseline()
            screen.blit(overlay_surface, rect_to_blink.topleft)
            pygame.display.flip()
            pygame.time.delay(250)

            # back to baseline ~750ms
            draw_final_baseline()
            pygame.display.flip()
            pygame.time.delay(750)

    # Order: leader receives first -> blink follower’s chosen box;
    # then follower receives -> blink leader’s chosen box.
    blink_box(
        rect_to_blink=chosen_follower_rect,
        overlay_surface=overlay_follower,
        times=pellets_to_leader,
        dispense_side=leader_disp
    )

    blink_box(
        rect_to_blink=chosen_leader_rect,
        overlay_surface=overlay_leader,
        times=pellets_to_follower,
        dispense_side=follower_disp
    )

    # After all pellets, keep both boxes normal on screen for 1s before JBT starts
    draw_final_baseline()
    pygame.display.flip()
    pygame.time.delay(1000)

    # ITI 2s
    pygame.time.delay(2000)

    return {
        "leader_side": leader_side,
        "leader_choice": leader_choice,
        "follower_choice": follower_choice,
        "leader_choice_time": round(leader_time or 0.0, 3),
        "follower_choice_time": round(follower_time or 0.0, 3),
    }
