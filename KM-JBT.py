import pygame
from pygame.locals import *
import sys, os, json
from datetime import datetime

# =============================
# Persistence (JSON state)
# =============================
STATE_DIR = os.path.join(os.path.dirname(__file__), "state", "KM_JBT")
ARCHIVE_DIR = os.path.join(STATE_DIR, "archive")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

INCOMPLETE = {}  # uid -> state dict

def make_uid(leader, follower, stimuli, sessions_total, version="v1"):
    return f"KMJBT_{version}__Leader-{leader}__Follower-{follower}__Stim-{stimuli}__Sessions-{int(sessions_total)}"

def state_path(uid):
    return os.path.join(STATE_DIR, f"{uid}.json")

def save_state(state):
    state["progress"]["last_saved_iso"] = datetime.now().isoformat(timespec="seconds")
    tmp = state_path(state["uid"]) + ".tmp"
    final = state_path(state["uid"])
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, final)

def load_all_states():
    INCOMPLETE.clear()
    for name in os.listdir(STATE_DIR):
        if not name.endswith(".json"):
            continue
        p = os.path.join(STATE_DIR, name)
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("status") != "complete":
                INCOMPLETE[data["uid"]] = data
        except Exception:
            pass

def new_or_resume_state(uid, config):
    p = state_path(uid)
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f), True
    state = {
        "version": 1,
        "uid": uid,
        "status": "incomplete",
        "config": {
            "leader": config["leader"],
            "follower": config["follower"],
            "stimuli": config["stimuli"],
            "sessions_total": int(config["sessions_total"])
        },
        "progress": {
            "session_index": 1,
            "block_index": 1,
            "trio_index": 1,
            "stage": "KM",
            "completed_trios": 0,
            "last_saved_iso": datetime.now().isoformat(timespec="seconds")
        }
    }
    save_state(state)
    return state, False

def set_next_trial(state, session_index, next_trial):  # next_trial: 1..28
    next_trial = max(1, min(28, int(next_trial)))
    block_index = ((next_trial - 1) // 7) + 1
    trio_index = ((next_trial - 1) % 7) + 1
    state["progress"]["session_index"] = int(session_index)
    state["progress"]["block_index"] = block_index
    state["progress"]["trio_index"] = trio_index
    state["progress"]["completed_trios"] = next_trial - 1
    state["progress"]["stage"] = "KM"

def archive_or_delete_if_complete(state, delete=True):
    if state.get("status") != "complete":
        return
    src = state_path(state["uid"])
    if delete:
        try:
            os.remove(src)
        except FileNotFoundError:
            pass
    else:
        dst = os.path.join(ARCHIVE_DIR, os.path.basename(src))
        try:
            os.replace(src, dst)
        except FileNotFoundError:
            pass

def ensure_fake_incomplete_examples():
    # Create a couple of test JSONs if none exist (for testing the resume screen)
    if INCOMPLETE:
        return
    samples = [
        dict(leader="Ira",   follower="Irene",  stimuli="Dark S+",  sessions_total=6, session_index=1, next_trial=11),
        dict(leader="Paddy", follower="Ingrid", stimuli="Light S+", sessions_total=6, session_index=3, next_trial=16),
    ]
    for s in samples:
        uid = make_uid(s["leader"], s["follower"], s["stimuli"], s["sessions_total"])
        st = {
            "version": 1,
            "uid": uid,
            "status": "incomplete",
            "config": {
                "leader": s["leader"],
                "follower": s["follower"],
                "stimuli": s["stimuli"],
                "sessions_total": s["sessions_total"]
            },
            "progress": {
                "session_index": s["session_index"],
                "block_index": ((s["next_trial"] - 1) // 7) + 1,
                "trio_index": ((s["next_trial"] - 1) % 7) + 1,
                "stage": "KM",
                "completed_trios": s["next_trial"] - 1,
                "last_saved_iso": datetime.now().isoformat(timespec="seconds")
            }
        }
        save_state(st)
    load_all_states()

# =============================
# Pygame UI
# =============================
pygame.init()
screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
pygame.display.set_caption("KM + JBT — Launch")
W, H = screen.get_size()
clock = pygame.time.Clock()

def s(x):
    return int((x / 800) * H)

PAD = s(20)
GROUP_SPACING = s(40)
FONT = pygame.font.SysFont("Calibri", s(28))
FONT_SMALL = pygame.font.SysFont("Calibri", s(24))
TITLE_FONT = pygame.font.SysFont("Calibri", s(44), bold=True)

BG = (240, 242, 245)
FG = (20, 20, 20)
ACCENT = (30, 120, 255)
LINE = (200, 200, 200)
BTN_BG = (255, 255, 255)
BTN_BORDER = (180, 180, 180)
BTN_BG_HOVER = (248, 248, 248)
ERROR = (200, 30, 30)
OKGREEN = (0, 120, 0)

MONKEYS = ["Ira", "Paddy", "Irene", "Ingrid", "Griffin", "Lily", "Wren", "Nkima", "Lychee"]
SESSIONS = [str(n) for n in range(1, 13)]
STIMULI = ["Dark S+", "Light S+"]

def draw_text(surface, text, font, color, x, y, anchor="topleft"):
    t = font.render(text, True, color)
    r = t.get_rect(**{anchor: (x, y)})
    surface.blit(t, r)
    return r

def elide(text, font, max_width):
    """Return text clipped with … so that its rendered width <= max_width."""
    if font.size(text)[0] <= max_width:
        return text
    if max_width <= font.size("…")[0]:
        return "…"
    left, right = 0, len(text)
    base = text
    while left < right:
        mid = (left + right) // 2
        trial = base[:mid] + "…"
        if font.size(trial)[0] <= max_width:
            left = mid + 1
        else:
            right = mid
    return base[:max(0, right - 1)] + "…"

class Button:
    def __init__(self, rect, label):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.hover = False
    def draw(self, surface):
        pygame.draw.rect(surface, BTN_BG_HOVER if self.hover else BTN_BG, self.rect, border_radius=s(10))
        pygame.draw.rect(surface, BTN_BORDER, self.rect, s(2), border_radius=s(10))
        inner_w = self.rect.w - s(20)
        lbl = elide(self.label, FONT, inner_w)
        draw_text(surface, lbl, FONT, FG, self.rect.centerx, self.rect.centery, "center")
    def handle(self, event):
        if event.type == MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if event.type == MOUSEBUTTONDOWN and event.button == 1 and self.rect.collidepoint(event.pos):
            return True
        return False

class TextInput:
    def __init__(self, rect, text=""):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.active = False
        self.caret_timer = 0
    def draw(self, surface):
        pygame.draw.rect(surface, BTN_BG, self.rect, border_radius=s(8))
        pygame.draw.rect(surface, BTN_BORDER, self.rect, s(2), border_radius=s(8))
        txt = FONT.render(self.text, True, FG)
        surface.blit(txt, (self.rect.x + s(10), self.rect.y + (self.rect.h - txt.get_height()) // 2))
        if self.active:
            self.caret_timer = (self.caret_timer + 1) % 60
            if self.caret_timer < 30:
                caret_x = self.rect.x + s(10) + txt.get_width() + s(2)
                pygame.draw.line(surface, FG, (caret_x, self.rect.y + s(8)),
                                 (caret_x, self.rect.y + self.rect.h - s(8)), s(2))
    def handle(self, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        if self.active and event.type == KEYDOWN:
            if event.key == K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (K_RETURN, K_KP_ENTER):
                self.active = False
            else:
                if len(self.text) < 20 and (event.unicode.isdigit() or event.unicode in "-/_ "):
                    self.text += event.unicode

class Dropdown:
    def __init__(self, rect, options, placeholder="Select...", visible_count=6):
        self.rect = pygame.Rect(rect)
        self.options = options[:]
        self.open = False
        self.value = None
        self.placeholder = placeholder
        self.visible_count = max(1, int(visible_count))
        self.scroll_idx = 0
        self._drop_rect = None
        self._item_h = self.rect.h
    def _max_scroll(self):
        return max(0, len(self.options) - self.visible_count)
    def _apply_scroll_bounds(self):
        self.scroll_idx = max(0, min(self.scroll_idx, self._max_scroll()))
    def draw(self, surface, force_front=False):
        pygame.draw.rect(surface, BTN_BG, self.rect, border_radius=s(8))
        pygame.draw.rect(surface, BTN_BORDER, self.rect, s(2), border_radius=s(8))
        label = self.value if self.value else self.placeholder
        draw_text(surface, label, FONT, FG if self.value else (120, 120, 120),
                  self.rect.x + s(10), self.rect.centery, "midleft")
        cx = self.rect.right - s(24)
        cy = self.rect.centery
        pygame.draw.polygon(surface, (120, 120, 120),
                            [(cx - s(6), cy - s(3)), (cx + s(6), cy - s(3)), (cx, cy + s(5))])
        if force_front and self.open:
            self._item_h = self.rect.h
            drop_h = self.visible_count * self._item_h
            self._drop_rect = pygame.Rect(self.rect.x, self.rect.bottom + s(4), self.rect.w, drop_h)
            pygame.draw.rect(surface, (252, 252, 252), self._drop_rect, border_radius=s(8))
            pygame.draw.rect(surface, BTN_BORDER, self._drop_rect, s(2), border_radius=s(8))
            start = self.scroll_idx
            end = min(start + self.visible_count, len(self.options))
            top = self._drop_rect.y
            for i in range(start, end):
                r = pygame.Rect(self._drop_rect.x, top, self._drop_rect.w, self._item_h)
                draw_text(surface, self.options[i], FONT, FG, r.x + s(10), r.centery, "midleft")
                pygame.draw.line(surface, LINE, (r.x, r.bottom), (r.right, r.bottom), 1)
                top += self._item_h
            if len(self.options) > self.visible_count:
                bar_w = s(6)
                track = pygame.Rect(self._drop_rect.right - bar_w - s(4), self._drop_rect.y + s(6),
                                    bar_w, self._drop_rect.h - s(12))
                pygame.draw.rect(surface, (235, 235, 235), track, border_radius=s(4))
                frac = self.visible_count / len(self.options)
                bar_h = max(s(18), int(track.h * frac))
                max_travel = track.h - bar_h
                pos_frac = 0 if self._max_scroll() == 0 else self.scroll_idx / self._max_scroll()
                bar_y = track.y + int(max_travel * pos_frac)
                pygame.draw.rect(surface, (200, 200, 200), (track.x, bar_y, bar_w, bar_h), border_radius=s(4))
    def _mouse_over_drop(self, pos):
        return self._drop_rect is not None and self._drop_rect.collidepoint(pos)
    def handle(self, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.open = not self.open
                return None
            if self.open and self._mouse_over_drop(event.pos):
                rel_y = event.pos[1] - self._drop_rect.y
                idx_in_view = int(rel_y // self._item_h)
                chosen_idx = self.scroll_idx + idx_in_view
                if 0 <= chosen_idx < len(self.options):
                    self.value = self.options[chosen_idx]
                    self.open = False
                    return self.value
                else:
                    self.open = False
            elif self.open:
                self.open = False
        if self.open and event.type == MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if self._mouse_over_drop((mx, my)) or self.rect.collidepoint((mx, my)):
                self.scroll_idx -= event.y
                self._apply_scroll_bounds()
        return None

class RadioPair:
    def __init__(self, left_pos, right_pos, radius=s(12)):
        self.left_is_leader = None
        self.left_pos = left_pos
        self.right_pos = right_pos
        self.radius = radius
    def draw(self, surface):
        pygame.draw.circle(surface, BTN_BORDER, self.left_pos, self.radius, s(2))
        if self.left_is_leader is True:
            pygame.draw.circle(surface, ACCENT, self.left_pos, self.radius - s(5))
        pygame.draw.circle(surface, BTN_BORDER, self.right_pos, self.radius, s(2))
        if self.left_is_leader is False:
            pygame.draw.circle(surface, ACCENT, self.right_pos, self.radius - s(5))
        draw_text(surface, "Left is Leader",  FONT_SMALL, FG, self.left_pos[0] + s(18),  self.left_pos[1], "midleft")
        draw_text(surface, "Right is Leader", FONT_SMALL, FG, self.right_pos[0] + s(18), self.right_pos[1], "midleft")
    def handle(self, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            if (pygame.Vector2(event.pos) - pygame.Vector2(self.left_pos)).length() <= self.radius + s(2):
                self.left_is_leader = True
                return "LEFT_LEADER"
            if (pygame.Vector2(event.pos) - pygame.Vector2(self.right_pos)).length() <= self.radius + s(2):
                self.left_is_leader = False
                return "RIGHT_LEADER"
        return None

# =============== Layout (Launch) ===============
panel_w = min(s(900), W - 2 * PAD)
panel_x = (W - panel_w) // 2
y = PAD * 2
title_rect = pygame.Rect(panel_x, y, panel_w, s(70))
y += title_rect.h + GROUP_SPACING
col_w = (panel_w - PAD) // 2
left_col_x = panel_x
right_col_x = panel_x + col_w + PAD
row_h = s(54)

date_input = TextInput((left_col_x, y, col_w, row_h), datetime.now().strftime("%Y-%m-%d"))
sessions_dd = Dropdown((right_col_x, y, col_w, row_h), [str(n) for n in range(1, 13)], "Sessions (1–12)", visible_count=6)
y += row_h + GROUP_SPACING

monkeyL_dd = Dropdown((left_col_x, y, col_w, row_h), MONKEYS, "Monkey L", visible_count=6)
monkeyR_dd = Dropdown((right_col_x, y, col_w, row_h), MONKEYS, "Monkey R", visible_count=6)
y += row_h + GROUP_SPACING

radio_y = y + row_h // 2
radio = RadioPair((left_col_x + s(16), radio_y), (right_col_x + s(16), radio_y))
y += row_h + GROUP_SPACING

stim_dd = Dropdown((left_col_x, y, col_w, row_h), STIMULI, "Stimuli (Dark S+ / Light S+)", visible_count=2)
y += row_h + GROUP_SPACING * 1.5

reset_btn  = Button((left_col_x, y, s(210), s(54)), "Reset")
launch_btn = Button((right_col_x + col_w - s(180), y, s(180), s(54)), "Launch")
resume_btn = Button((right_col_x + col_w - s(180) - s(280) - s(16), y, s(280), s(54)), "Restart Session")

# =============== Resume Menu UI ===============
mode = "launch"   # or "resume_menu"
selected_uid = None

detail_y0 = PAD * 2 + s(90)  # not used for layout any more but kept for compatibility
edit_monkeyL = Dropdown((0, 0, 0, 0), MONKEYS, "Monkey L", visible_count=6)
edit_monkeyR = Dropdown((0, 0, 0, 0), MONKEYS, "Monkey R", visible_count=6)
edit_stim    = Dropdown((0, 0, 0, 0), STIMULI, "Stimuli", visible_count=2)
edit_radio   = RadioPair((0, 0), (0, 0))

class Stepper:
    def __init__(self, x, y, w, h, vmin, vmax, value, label):
        self.rect = pygame.Rect(x, y, w, h)
        self.vmin = vmin
        self.vmax = vmax
        self.value = value
        self.label = label
        self.btn_minus = Button((x, y, s(44), h), "-")
        self.btn_plus  = Button((x + w - s(44), y, s(44), h), "+")
    def set_rect(self, x, y, w, h):
        self.rect.update(x, y, w, h)
        self.btn_minus.rect.update(x, y, s(44), h)
        self.btn_plus.rect.update(x + w - s(44), y, s(44), h)
    def draw(self, surface):
        pygame.draw.rect(surface, BTN_BG, self.rect, border_radius=s(8))
        pygame.draw.rect(surface, BTN_BORDER, self.rect, s(2), border_radius=s(8))
        draw_text(surface, self.label, FONT_SMALL, FG, self.rect.x, self.rect.y - s(22))
        draw_text(surface, str(self.value), FONT, FG, self.rect.centerx, self.rect.centery, "center")
        self.btn_minus.draw(surface)
        self.btn_plus.draw(surface)
    def handle(self, event):
        if self.btn_minus.handle(event):
            self.value = max(self.vmin, self.value - 1)
        if self.btn_plus.handle(event):
            self.value = min(self.vmax, self.value + 1)

edit_session = Stepper(0, 0, 0, 0, 1, 12, 1, "Session #")
edit_trial   = Stepper(0, 0, 0, 0, 1, 28, 1, "Next Trial #")

restart_btn  = Button((0, 0, 0, 0), "Restart")
back_btn     = Button((0, 0, 0, 0), "Back")

def layout_resume_panels():
    """Compute resume list/detail panel rects and place all edit widgets to avoid overlap."""
    top = title_rect.bottom + s(16)
    height = H - top - int(PAD * 1.5)

    # Left list ~45% of panel width (min width safeguard)
    left_w = max(s(480), int(panel_w * 0.45))
    list_rect = pygame.Rect(panel_x, top, left_w, height)

    # Right detail panel fills remaining width up to panel_x right edge
    detail_rect = pygame.Rect(list_rect.right + s(10), top, W - (list_rect.right + s(10)) - panel_x + s(150), height)


    # --- Adjusted vertical layout ---
    x = detail_rect.x + s(20)
    y = detail_rect.y + s(70)     # ⬆️ more space below "Edit & Restart"
    full_w = detail_rect.w - s(40)
    dd_h = row_h
    vgap_small = int(PAD * 1.0)   # for tighter gaps
    vgap_large = int(PAD * 1.5)   # for looser gaps

    # Dropdowns (with more spacing between them)
    edit_monkeyL.rect.update(x, y, full_w, dd_h)
    y += dd_h + vgap_large        # ⬆️ more space after Monkey L

    edit_monkeyR.rect.update(x, y, full_w, dd_h)
    y += dd_h + vgap_large        # ⬆️ more space after Monkey R

    edit_stim.rect.update(x, y, full_w, dd_h)
    y += dd_h + vgap_large        # ⬆️ more space before Leader/Follower

    # Leader/Follower radio row (with extra vertical offset)
    radio_y = y + dd_h // 2 + s(8)   # ⬆️ adds a little vertical breathing room
    edit_radio.left_pos  = (x + s(16),              radio_y)
    edit_radio.right_pos = (x + s(16) + s(220),     radio_y)
    y += dd_h + vgap_large

    # Session + Trial steppers (two columns)
    step_w = (full_w - s(20)) // 2
    edit_session.set_rect(x, y, step_w, dd_h)
    edit_trial.set_rect(x + step_w + s(20), y, step_w, dd_h)
    y += dd_h + int(vgap_large * 1.2)

    # Buttons
    restart_btn.rect.update(x, y, s(240), s(54))
    back_btn.rect.update(x + s(260), y, s(180), s(54))

    return list_rect, detail_rect

def populate_edit_fields_from_state(st):
    edit_monkeyL.value = st["config"]["leader"]
    edit_monkeyR.value = st["config"]["follower"]
    edit_stim.value    = st["config"]["stimuli"]
    edit_radio.left_is_leader = True  # default assumption for editor
    edit_session.value = int(st["progress"]["session_index"])
    next_trial = st["progress"]["completed_trios"] + 1
    edit_trial.value = max(1, min(28, next_trial))

def set_state_from_edit_fields(st):
    left_name = edit_monkeyL.value
    right_name = edit_monkeyR.value
    if edit_radio.left_is_leader is True:
        leader, follower = left_name, right_name
    else:
        leader, follower = right_name, left_name
    st["config"]["leader"]   = leader
    st["config"]["follower"] = follower
    st["config"]["stimuli"]  = edit_stim.value
    set_next_trial(st, session_index=edit_session.value, next_trial=edit_trial.value)
    new_uid = make_uid(st["config"]["leader"], st["config"]["follower"], st["config"]["stimuli"], st["config"]["sessions_total"])
    if new_uid != st["uid"]:
        old = state_path(st["uid"])
        st["uid"] = new_uid
        try:
            os.remove(old)
        except FileNotFoundError:
            pass

# -----------------------------
# Validation & helpers
# -----------------------------
def current_roles_launch():
    if radio.left_is_leader is None:
        return None, None
    return ("Leader", "Follower") if radio.left_is_leader else ("Follower", "Leader")

def validate_launch():
    ok, messages = True, []
    Lrole, Rrole = current_roles_launch()
    if not date_input.text.strip():
        ok, messages = False, messages + ["Date required."]
    if sessions_dd.value is None:
        ok, messages = False, messages + ["Sessions not selected."]
    if monkeyL_dd.value is None:
        ok, messages = False, messages + ["Monkey L not selected."]
    if monkeyR_dd.value is None:
        ok, messages = False, messages + ["Monkey R not selected."]
    if monkeyL_dd.value and monkeyR_dd.value and monkeyL_dd.value == monkeyR_dd.value:
        ok, messages = False, messages + ["Left and Right monkeys must differ."]
    if Lrole is None:
        ok, messages = False, messages + ["Leader side not chosen."]
    if stim_dd.value is None:
        ok, messages = False, messages + ["Stimuli not selected."]
    return ok, messages

def reset_all_launch():
    date_input.text = datetime.now().strftime("%Y-%m-%d")
    sessions_dd.value = None
    monkeyL_dd.value = None
    monkeyR_dd.value = None
    stim_dd.value = None
    radio.left_is_leader = None
    for dd in (sessions_dd, monkeyL_dd, monkeyR_dd, stim_dd):
        dd.scroll_idx = 0
        dd.open = False

# -----------------------------
# Main loop
# -----------------------------
load_all_states()
ensure_fake_incomplete_examples()

error_lines = []
running = True
selected_uid = None

while running:
    for event in pygame.event.get():
        if event.type == QUIT:
            running = False
        if event.type == KEYDOWN and (event.key == K_ESCAPE or event.key == K_q):
            running = False

        if mode == "launch":
            date_input.handle(event)
            sessions_dd.handle(event)
            if monkeyL_dd.handle(event) is not None and monkeyR_dd.value == monkeyL_dd.value:
                monkeyR_dd.value = None
            if monkeyR_dd.handle(event) is not None and monkeyL_dd.value == monkeyR_dd.value:
                monkeyL_dd.value = None
            radio.handle(event)
            stim_dd.handle(event)

            if reset_btn.handle(event):
                reset_all_launch()
                error_lines = []

            if resume_btn.handle(event):
                mode = "resume_menu"
                error_lines = []
                selected_uid = next(iter(INCOMPLETE.keys()), None)
                if selected_uid:
                    populate_edit_fields_from_state(INCOMPLETE[selected_uid])

            if launch_btn.handle(event):
                ok, msgs = validate_launch()
                if ok:
                    Lrole, Rrole = current_roles_launch()
                    left_name = monkeyL_dd.value
                    right_name = monkeyR_dd.value
                    leader = left_name if Lrole == "Leader" else right_name
                    follower = right_name if Lrole == "Leader" else left_name
                    uid = make_uid(leader, follower, stim_dd.value, int(sessions_dd.value))
                    config = {
                        "leader": leader,
                        "follower": follower,
                        "stimuli": stim_dd.value,
                        "sessions_total": int(sessions_dd.value)
                    }
                    state, is_resume = new_or_resume_state(uid, config)
                    print("\n--- KM + JBT Launch Config ---")
                    print("mode: ", "RESUME(existing)" if is_resume else "NEW")
                    for k in ("uid", "status"):
                        print(f"{k}: {state[k]}")
                    print("config:", state["config"])
                    print("progress:", state["progress"])
                    running = False
                else:
                    error_lines = msgs[:]

        elif mode == "resume_menu":
            # Single-click select on the left list
            if event.type == MOUSEBUTTONDOWN and event.button == 1:
                list_rect, _ = layout_resume_panels()
                item_h = s(64)
                top_y = list_rect.y + s(48)
                uid_rows = []
                for uid, st in list(INCOMPLETE.items()):
                    if top_y + item_h > list_rect.bottom - s(10):
                        break
                    row = pygame.Rect(list_rect.x + s(8), top_y, list_rect.w - s(16), item_h)
                    uid_rows.append((row, uid))
                    top_y += item_h + s(8)
                for r, uid in uid_rows:
                    if r.collidepoint(event.pos):
                        if selected_uid != uid:
                            selected_uid = uid
                            populate_edit_fields_from_state(INCOMPLETE[uid])
                        break

            # Pass events to edit controls
            edit_monkeyL.handle(event)
            edit_monkeyR.handle(event)
            edit_stim.handle(event)
            edit_radio.handle(event)
            edit_session.handle(event)
            edit_trial.handle(event)

            if back_btn.handle(event):
                mode = "launch"
                selected_uid = None
                error_lines = []
                load_all_states()

            if restart_btn.handle(event):
                if not selected_uid:
                    error_lines = ["Select a session from the list."]
                else:
                    st = INCOMPLETE[selected_uid]
                    set_state_from_edit_fields(st)
                    save_state(st)
                    load_all_states()
                    selected_uid = st["uid"] if st["uid"] in INCOMPLETE else None
                    print("\n--- KM + JBT RESTART ---")
                    print("uid:", st["uid"])
                    print("config:", st["config"])
                    print("progress:", st["progress"])
                    running = False

    # ========== DRAW ==========
    screen.fill(BG)
    draw_text(screen, "KM + JBT — Launch", TITLE_FONT, FG, title_rect.centerx, title_rect.centery, "center")

    if mode == "launch":
        draw_text(screen, "Date", FONT_SMALL, FG, left_col_x, date_input.rect.y - s(22))
        draw_text(screen, "Sessions", FONT_SMALL, FG, right_col_x, sessions_dd.rect.y - s(22))
        draw_text(screen, "Monkey L", FONT_SMALL, FG, left_col_x, monkeyL_dd.rect.y - s(22))
        draw_text(screen, "Monkey R", FONT_SMALL, FG, right_col_x, monkeyR_dd.rect.y - s(22))
        draw_text(screen, "Leader / Follower", FONT_SMALL, FG, left_col_x, (monkeyL_dd.rect.bottom + s(10)))
        draw_text(screen, "Stimuli Set", FONT_SMALL, FG, left_col_x, stim_dd.rect.y - s(22))

        date_input.draw(screen)
        sessions_dd.draw(screen)
        monkeyL_dd.draw(screen)
        monkeyR_dd.draw(screen)
        radio.draw(screen)
        stim_dd.draw(screen)

        reset_btn.draw(screen)
        resume_btn.draw(screen)
        launch_btn.draw(screen)

        Lrole, Rrole = current_roles_launch()
        if Lrole:
            draw_text(screen, f"Left: {Lrole}",  FONT_SMALL, OKGREEN, left_col_x,  radio.left_pos[1]  + s(24))
            draw_text(screen, f"Right: {Rrole}", FONT_SMALL, OKGREEN, right_col_x, radio.right_pos[1] + s(24))

        for dd in [sessions_dd, monkeyL_dd, monkeyR_dd, stim_dd]:
            if dd.open:
                dd.draw(screen, force_front=True)

        if error_lines:
            y_err = y + s(70)
            for line in error_lines:
                draw_text(screen, f"• {line}", FONT_SMALL, ERROR, panel_x, y_err)
                y_err += s(24)

    elif mode == "resume_menu":
        list_rect, detail_rect = layout_resume_panels()

        # Left panel
        pygame.draw.rect(screen, BTN_BG, list_rect, border_radius=s(12))
        pygame.draw.rect(screen, BTN_BORDER, list_rect, s(2), border_radius=s(12))
        draw_text(screen, "Incomplete Sessions", FONT, FG, list_rect.x + s(12), list_rect.y + s(10))

        # Items
        item_h = s(64)
        top_y = list_rect.y + s(48)
        uid_rows = []
        for uid, st in list(INCOMPLETE.items()):
            if top_y + item_h > list_rect.bottom - s(10):
                break
            row = pygame.Rect(list_rect.x + s(8), top_y, list_rect.w - s(16), item_h)
            pygame.draw.rect(screen, BTN_BG_HOVER if uid == selected_uid else (252, 252, 252), row, border_radius=s(8))
            pygame.draw.rect(screen, BTN_BORDER, row, s(1), border_radius=s(8))
            leader = st["config"]["leader"]; follower = st["config"]["follower"]
            sess = st["progress"]["session_index"]; trial = st["progress"]["completed_trios"] + 1
            line1 = f"{leader} (Leader) + {follower} (Follower)"
            line2 = f"Session {sess} — Next Trial {trial} — Stim: {st['config']['stimuli']}"
            draw_text(screen, line1, FONT_SMALL, FG, row.x + s(10), row.y + s(10))
            draw_text(screen, line2, FONT_SMALL, (60, 60, 60), row.x + s(10), row.bottom - s(22))
            uid_rows.append((row, uid))
            top_y += item_h + s(8)

        # Right detail panel
        pygame.draw.rect(screen, BTN_BG, detail_rect, border_radius=s(12))
        pygame.draw.rect(screen, BTN_BORDER, detail_rect, s(2), border_radius=s(12))
        draw_text(screen, "Edit & Restart", FONT, FG, detail_rect.x + s(12), detail_rect.y + s(10))

        draw_text(screen, "Monkey L",          FONT_SMALL, FG, edit_monkeyL.rect.x,         edit_monkeyL.rect.y - s(22))
        draw_text(screen, "Monkey R",          FONT_SMALL, FG, edit_monkeyR.rect.x,         edit_monkeyR.rect.y - s(22))
        draw_text(screen, "Stimuli",           FONT_SMALL, FG, edit_stim.rect.x,            edit_stim.rect.y    - s(22))
        draw_text(screen, "Leader / Follower", FONT_SMALL, FG, edit_radio.left_pos[0],      edit_radio.left_pos[1] - s(38))
        draw_text(screen, "Session #",         FONT_SMALL, FG, edit_session.rect.x,         edit_session.rect.y - s(22))
        draw_text(screen, "Next Trial #",      FONT_SMALL, FG, edit_trial.rect.x,           edit_trial.rect.y   - s(22))

        edit_monkeyL.draw(screen); edit_monkeyR.draw(screen); edit_stim.draw(screen); edit_radio.draw(screen)
        edit_session.draw(screen); edit_trial.draw(screen)
        restart_btn.draw(screen);  back_btn.draw(screen)

        for dd in [edit_monkeyL, edit_monkeyR, edit_stim]:
            if dd.open:
                dd.draw(screen, force_front=True)

        if error_lines:
            y_err = detail_rect.bottom - s(90)
            for line in error_lines:
                draw_text(screen, f"• {line}", FONT_SMALL, ERROR, detail_rect.x + s(12), y_err)
                y_err += s(24)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
