# scenes/launch.py
import os
import sys
import json
from datetime import datetime

import pygame
from pygame.locals import *

# Use the shared persistence (single source of truth)
from shared.persistence import (
    INCOMPLETE,
    make_uid,
    load_all_states,
    save_state,
    new_or_resume_state,
    set_next_trial,
    ensure_fake_incomplete_examples,
)

# =====================================================
# UI helpers (same behavior as before, packaged here)
# =====================================================
def _elide(text, font, max_width):
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




class _Button:
    def __init__(self, rect, label, s, FONT, FG, BTN_BG, BTN_BG_HOVER, BTN_BORDER):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.hover = False
        self._s = s
        self._FONT = FONT
        self._FG = FG
        self._BTN_BG = BTN_BG
        self._BTN_BG_HOVER = BTN_BG_HOVER
        self._BTN_BORDER = BTN_BORDER

    def draw(self, surface):
        pygame.draw.rect(
            surface,
            self._BTN_BG_HOVER if self.hover else self._BTN_BG,
            self.rect,
            border_radius=self._s(10),
        )
        pygame.draw.rect(
            surface, self._BTN_BORDER, self.rect, self._s(2), border_radius=self._s(10)
        )
        inner_w = self.rect.w - self._s(20)
        lbl = _elide(self.label, self._FONT, inner_w)
        t = self._FONT.render(lbl, True, self._FG)
        surface.blit(t, t.get_rect(center=self.rect.center))

    def handle(self, event):
        if event.type == MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        if (
            event.type == MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        ):
            return True
        return False


class _TextInput:
    def __init__(self, rect, text, s, FONT, FG, BTN_BG, BTN_BORDER):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.active = False
        self.caret_timer = 0
        self._s = s
        self._FONT = FONT
        self._FG = FG
        self._BTN_BG = BTN_BG
        self._BTN_BORDER = BTN_BORDER

    def draw(self, surface):
        pygame.draw.rect(surface, self._BTN_BG, self.rect, border_radius=self._s(8))
        pygame.draw.rect(
            surface, self._BTN_BORDER, self.rect, self._s(2), border_radius=self._s(8)
        )
        txt = self._FONT.render(self.text, True, self._FG)
        surface.blit(
            txt,
            (self.rect.x + self._s(10), self.rect.y + (self.rect.h - txt.get_height()) // 2),
        )
        if self.active:
            self.caret_timer = (self.caret_timer + 1) % 60
            if self.caret_timer < 30:
                caret_x = self.rect.x + self._s(10) + txt.get_width() + self._s(2)
                pygame.draw.line(
                    surface,
                    self._FG,
                    (caret_x, self.rect.y + self._s(8)),
                    (caret_x, self.rect.y + self.rect.h - self._s(8)),
                    self._s(2),
                )

    def handle(self, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            self.active = self.rect.collidepoint(event.pos)
        if self.active and event.type == KEYDOWN:
            if event.key == K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key in (K_RETURN, K_KP_ENTER):
                self.active = False
            else:
                if len(self.text) < 20 and (
                    event.unicode.isdigit() or event.unicode in "-/_ "
                ):
                    self.text += event.unicode


class _Dropdown:
    def __init__(self, rect, options, placeholder, visible_count, s, FONT, FG, LINE, BTN_BG, BTN_BORDER):
        self.rect = pygame.Rect(rect)
        self.options = list(options)
        self.placeholder = placeholder
        self.visible_count = max(1, int(visible_count))
        self.open = False
        self.value = None
        self.scroll_idx = 0
        self._drop_rect = None
        self._item_h = self.rect.h
        self._s = s
        self._FONT = FONT
        self._FG = FG
        self._LINE = LINE
        self._BTN_BG = BTN_BG
        self._BTN_BORDER = BTN_BORDER

    def _max_scroll(self):
        return max(0, len(self.options) - self.visible_count)

    def _apply_scroll_bounds(self):
        self.scroll_idx = max(0, min(self.scroll_idx, self._max_scroll()))

    def draw(self, surface, force_front=False):
        pygame.draw.rect(surface, self._BTN_BG, self.rect, border_radius=self._s(8))
        pygame.draw.rect(surface, self._BTN_BORDER, self.rect, self._s(2), border_radius=self._s(8))
        label = self.value if self.value else self.placeholder
        t = self._FONT.render(label, True, self._FG if self.value else (120, 120, 120))
        surface.blit(t, (self.rect.x + self._s(10), self.rect.centery - t.get_height() // 2))
        cx = self.rect.right - self._s(24)
        cy = self.rect.centery
        pygame.draw.polygon(
            surface,
            (120, 120, 120),
            [(cx - self._s(6), cy - self._s(3)), (cx + self._s(6), cy - self._s(3)), (cx, cy + self._s(5))],
        )
        if force_front and self.open:
            self._item_h = self.rect.h
            drop_h = self.visible_count * self._item_h
            self._drop_rect = pygame.Rect(self.rect.x, self.rect.bottom + self._s(4), self.rect.w, drop_h)
            pygame.draw.rect(surface, (252, 252, 252), self._drop_rect, border_radius=self._s(8))
            pygame.draw.rect(surface, self._BTN_BORDER, self._drop_rect, self._s(2), border_radius=self._s(8))

            start = self.scroll_idx
            end = min(start + self.visible_count, len(self.options))
            top = self._drop_rect.y
            for i in range(start, end):
                r = pygame.Rect(self._drop_rect.x, top, self._drop_rect.w, self._item_h)
                tt = self._FONT.render(self.options[i], True, self._FG)
                surface.blit(tt, (r.x + self._s(10), r.centery - tt.get_height() // 2))
                pygame.draw.line(surface, self._LINE, (r.x, r.bottom), (r.right, r.bottom), 1)
                top += self._item_h

            if len(self.options) > self.visible_count:
                bar_w = self._s(6)
                track = pygame.Rect(
                    self._drop_rect.right - bar_w - self._s(4),
                    self._drop_rect.y + self._s(6),
                    bar_w,
                    self._drop_rect.h - self._s(12),
                )
                pygame.draw.rect(surface, (235, 235, 235), track, border_radius=self._s(4))
                frac = self.visible_count / len(self.options)
                bar_h = max(self._s(18), int(track.height * frac))
                max_travel = track.height - bar_h
                pos_frac = 0 if self._max_scroll() == 0 else self.scroll_idx / self._max_scroll()
                bar_y = track.y + int(max_travel * pos_frac)
                bar = pygame.Rect(track.x, bar_y, bar_w, bar_h)
                pygame.draw.rect(surface, (200, 200, 200), bar, border_radius=self._s(4))

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


class _RadioPair:
    def __init__(self, left_pos, right_pos, s, FONT_SMALL, FG, BTN_BORDER, ACCENT):
        self.left_is_leader = None
        self.left_pos = left_pos
        self.right_pos = right_pos
        self.radius = s(12)
        self._s = s
        self._FONT_SMALL = FONT_SMALL
        self._FG = FG
        self._BTN_BORDER = BTN_BORDER
        self._ACCENT = ACCENT

    def draw(self, surface):
        pygame.draw.circle(surface, self._BTN_BORDER, self.left_pos, self.radius, self._s(2))
        if self.left_is_leader is True:
            pygame.draw.circle(surface, self._ACCENT, self.left_pos, self.radius - self._s(5))
        pygame.draw.circle(surface, self._BTN_BORDER, self.right_pos, self.radius, self._s(2))
        if self.left_is_leader is False:
            pygame.draw.circle(surface, self._ACCENT, self.right_pos, self.radius - self._s(5))

        def _draw_text(txt, x, y):
            t = self._FONT_SMALL.render(txt, True, self._FG)
            surface.blit(t, t.get_rect(midleft=(x, y)))

        _draw_text("Left is Leader", self.left_pos[0] + self._s(18), self.left_pos[1])
        _draw_text("Right is Leader", self.right_pos[0] + self._s(18), self.right_pos[1])

    def handle(self, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            if (pygame.Vector2(event.pos) - pygame.Vector2(self.left_pos)).length() <= self.radius + self._s(2):
                self.left_is_leader = True
                return "LEFT_LEADER"
            if (pygame.Vector2(event.pos) - pygame.Vector2(self.right_pos)).length() <= self.radius + self._s(2):
                self.left_is_leader = False
                return "RIGHT_LEADER"
        return None


class _Stepper:
    def __init__(self, x, y, w, h, vmin, vmax, value, label, s, FONT, FONT_SMALL, FG, BTN_BG, BTN_BORDER):
        self.rect = pygame.Rect(x, y, w, h)
        self.vmin = vmin
        self.vmax = vmax
        self.value = value
        self.label = label
        self._s = s
        self._FONT = FONT
        self._FONT_SMALL = FONT_SMALL
        self._FG = FG
        self._BTN_BG = BTN_BG
        self._BTN_BORDER = BTN_BORDER
        self.btn_minus = _Button((x, y, self._s(44), h), "-", s, FONT, FG, BTN_BG, (248, 248, 248), BTN_BORDER)
        self.btn_plus = _Button((x + w - self._s(44), y, self._s(44), h), "+", s, FONT, FG, BTN_BG, (248, 248, 248), BTN_BORDER)

    def set_rect(self, x, y, w, h):
        self.rect.update(x, y, w, h)
        self.btn_minus.rect.update(x, y, self._s(44), h)
        self.btn_plus.rect.update(x + w - self._s(44), y, self._s(44), h)

    def draw(self, surface):
        pygame.draw.rect(surface, self._BTN_BG, self.rect, border_radius=self._s(8))
        pygame.draw.rect(surface, self._BTN_BORDER, self.rect, self._s(2), border_radius=self._s(8))
        t = self._FONT_SMALL.render(self.label, True, self._FG)
        surface.blit(t, (self.rect.x, self.rect.y - self._s(22)))
        v = self._FONT.render(str(self.value), True, self._FG)
        surface.blit(v, v.get_rect(center=self.rect.center))
        self.btn_minus.draw(surface)
        self.btn_plus.draw(surface)

    def handle(self, event):
        if self.btn_minus.handle(event):
            self.value = max(self.vmin, self.value - 1)
        if self.btn_plus.handle(event):
            self.value = min(self.vmax, self.value + 1)

# =====================================================
# Persistence (STATE_DIR defined here)
# =====================================================
STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "state", "KM_JBT")
ARCHIVE_DIR = os.path.join(STATE_DIR, "archive")
os.makedirs(STATE_DIR, exist_ok=True)
os.makedirs(ARCHIVE_DIR, exist_ok=True)

# Add helper *here*, after STATE_DIR*
def _state_path(uid: str) -> str:
    return os.path.join(STATE_DIR, f"{uid}.json")

# =====================================================
# The Scene
# =====================================================

class LaunchScene:
    MONKEYS = ["Ira", "Paddy", "Irene", "Ingrid", "Griffin", "Lily", "Wren", "Nkima", "Lychee"]
    SESSIONS = [str(n) for n in range(1, 13)]
    STIMULI = ["Dark S+", "Light S+"]

    def __init__(self, screen, clock=None):
        self.screen = screen
        self.clock = clock or pygame.time.Clock()
        self.W, self.H = self.screen.get_size()

        def s(x):
            return int((x / 800) * self.H)

        self.s = s

        # Colors & fonts
        self.BG = (240, 242, 245)
        self.FG = (20, 20, 20)
        self.ACCENT = (30, 120, 255)
        self.LINE = (200, 200, 200)
        self.BTN_BG = (255, 255, 255)
        self.BTN_BORDER = (180, 180, 180)
        self.BTN_BG_HOVER = (248, 248, 248)
        self.ERROR = (200, 30, 30)
        self.OKGREEN = (0, 120, 0)

        self.PAD = s(20)
        self.GROUP_SPACING = s(40)
        self.FONT = pygame.font.SysFont("Calibri", s(28))
        self.FONT_SMALL = pygame.font.SysFont("Calibri", s(24))
        self.TITLE_FONT = pygame.font.SysFont("Calibri", s(44), bold=True)

        # Layout (launch)
        self.panel_w = min(s(900), self.W - 2 * self.PAD)
        self.panel_x = (self.W - self.panel_w) // 2
        y = self.PAD * 2
        self.title_rect = pygame.Rect(self.panel_x, y, self.panel_w, s(70))
        y += self.title_rect.h + self.GROUP_SPACING

        col_w = (self.panel_w - self.PAD) // 2
        left_col_x = self.panel_x
        right_col_x = self.panel_x + col_w + self.PAD
        row_h = s(54)
        self._left_col_x, self._right_col_x, self._row_h = left_col_x, right_col_x, row_h

        # Controls (launch)
        self.date_input = _TextInput(
            (left_col_x, y, col_w, row_h),
            datetime.now().strftime("%Y-%m-%d"),
            s, self.FONT, self.FG, self.BTN_BG, self.BTN_BORDER,
        )
        self.sessions_dd = _Dropdown(
            (right_col_x, y, col_w, row_h),
            self.SESSIONS, "Sessions (1–12)", 6,
            s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER,
        )
        y += row_h + self.GROUP_SPACING

        self.monkeyL_dd = _Dropdown(
            (left_col_x, y, col_w, row_h),
            self.MONKEYS, "Monkey L", 6,
            s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER,
        )
        self.monkeyR_dd = _Dropdown(
            (right_col_x, y, col_w, row_h),
            self.MONKEYS, "Monkey R", 6,
            s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER,
        )
        y += row_h + self.GROUP_SPACING

        radio_y = y + row_h // 2
        self.radio = _RadioPair(
            (left_col_x + s(16), radio_y), (right_col_x + s(16), radio_y),
            s, self.FONT_SMALL, self.FG, self.BTN_BORDER, self.ACCENT,
        )
        y += row_h + self.GROUP_SPACING

        self.stim_dd = _Dropdown(
            (left_col_x, y, col_w, row_h),
            self.STIMULI, "Stimuli (Dark S+ / Light S+)", 2,
            s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER,
        )
        y += row_h + int(self.GROUP_SPACING * 1.5)

        self.reset_btn  = _Button((left_col_x, y, s(210), s(54)), "Reset", s, self.FONT, self.FG, self.BTN_BG, self.BTN_BG_HOVER, self.BTN_BORDER)
        self.launch_btn = _Button((right_col_x + col_w - s(180), y, s(180), s(54)), "Launch", s, self.FONT, self.FG, self.BTN_BG, self.BTN_BG_HOVER, self.BTN_BORDER)
        self.resume_btn = _Button((right_col_x + col_w - s(180) - s(280) - s(16), y, s(280), s(54)), "Restart Session", s, self.FONT, self.FG, self.BTN_BG, self.BTN_BG_HOVER, self.BTN_BORDER)

        # Resume UI
        self.mode = "launch"
        self.selected_uid = None

        # Editor widgets (positions set in layout function)
        self.edit_monkeyL = _Dropdown((0, 0, 0, 0), self.MONKEYS, "Monkey L", 6, s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER)
        self.edit_monkeyR = _Dropdown((0, 0, 0, 0), self.MONKEYS, "Monkey R", 6, s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER)
        self.edit_stim    = _Dropdown((0, 0, 0, 0), self.STIMULI, "Stimuli",     2, s, self.FONT, self.FG, self.LINE, self.BTN_BG, self.BTN_BORDER)
        self.edit_radio   = _RadioPair((0, 0), (0, 0), s, self.FONT_SMALL, self.FG, self.BTN_BORDER, self.ACCENT)

        self.edit_session = _Stepper(0, 0, 0, 0, 1, 12, 1, "Session #", s, self.FONT, self.FONT_SMALL, self.FG, self.BTN_BG, self.BTN_BORDER)
        self.edit_trial   = _Stepper(0, 0, 0, 0, 1, 28, 1, "Next Trial #", s, self.FONT, self.FONT_SMALL, self.FG, self.BTN_BG, self.BTN_BORDER)

        self.restart_btn  = _Button((0, 0, 0, 0), "Restart", s, self.FONT, self.FG, self.BTN_BG, self.BTN_BG_HOVER, self.BTN_BORDER)
        self.back_btn     = _Button((0, 0, 0, 0), "Back",    s, self.FONT, self.FG, self.BTN_BG, self.BTN_BG_HOVER, self.BTN_BORDER)

        # Errors
        self.error_lines = []

        # Load persisted states (and dev seeds for first runs)
        load_all_states()
        ensure_fake_incomplete_examples()

        # Optional: widen right panel without touching left
        self.RIGHT_PANEL_EXTRA_W = s(150)

    # --------------- helpers ---------------
    def _draw_text(self, surface, text, font, color, x, y, anchor="topleft"):
        t = font.render(text, True, color)
        r = t.get_rect(**{anchor: (x, y)})
        surface.blit(t, r)
        return r

    def _current_roles_launch(self):
        if self.radio.left_is_leader is None:
            return None, None
        return ("Leader", "Follower") if self.radio.left_is_leader else ("Follower", "Leader")

    def _validate_launch(self):
        ok, messages = True, []
        Lrole, _ = self._current_roles_launch()
        if not self.date_input.text.strip():
            ok, messages = False, messages + ["Date required."]
        if self.sessions_dd.value is None:
            ok, messages = False, messages + ["Sessions not selected."]
        if self.monkeyL_dd.value is None:
            ok, messages = False, messages + ["Monkey L not selected."]
        if self.monkeyR_dd.value is None:
            ok, messages = False, messages + ["Monkey R not selected."]
        if self.monkeyL_dd.value and self.monkeyR_dd.value and self.monkeyL_dd.value == self.monkeyR_dd.value:
            ok, messages = False, messages + ["Left and Right monkeys must differ."]
        if Lrole is None:
            ok, messages = False, messages + ["Leader side not chosen."]
        if self.stim_dd.value is None:
            ok, messages = False, messages + ["Stimuli not selected."]
        return ok, messages

    def _reset_launch(self):
        self.date_input.text = datetime.now().strftime("%Y-%m-%d")
        self.sessions_dd.value = None
        self.monkeyL_dd.value = None
        self.monkeyR_dd.value = None
        self.stim_dd.value = None
        self.radio.left_is_leader = None
        for dd in (self.sessions_dd, self.monkeyL_dd, self.monkeyR_dd, self.stim_dd):
            dd.scroll_idx = 0
            dd.open = False

    def _layout_resume_panels(self):
        top = self.title_rect.bottom + self.s(16)
        height = self.H - top - int(self.PAD * 1.5)

        left_w = max(self.s(480), int(self.panel_w * 0.45))
        list_rect = pygame.Rect(self.panel_x, top, left_w, height)

        detail_rect = pygame.Rect(
            list_rect.right + self.s(10), top,
            self.W - (list_rect.right + self.s(10)) - self.panel_x + self.RIGHT_PANEL_EXTRA_W,
            height,
        )

        # place widgets
        x = detail_rect.x + self.s(20)
        y = detail_rect.y + self.s(70)
        full_w = detail_rect.w - self.s(40)
        dd_h = self._row_h
        vgap_large = int(self.PAD * 1.5)

        self.edit_monkeyL.rect.update(x, y, full_w, dd_h); y += dd_h + vgap_large
        self.edit_monkeyR.rect.update(x, y, full_w, dd_h); y += dd_h + vgap_large
        self.edit_stim.rect.update(x, y, full_w, dd_h);    y += dd_h + vgap_large

        radio_y = y + dd_h // 2 + self.s(8)
        self.edit_radio.left_pos  = (x + self.s(16), radio_y)
        self.edit_radio.right_pos = (x + self.s(16) + self.s(220), radio_y)
        y += dd_h + vgap_large

        step_w = (full_w - self.s(20)) // 2
        self.edit_session.set_rect(x, y, step_w, dd_h)
        self.edit_trial.set_rect(x + step_w + self.s(20), y, step_w, dd_h)
        y += dd_h + int(vgap_large * 1.2)

        self.restart_btn.rect.update(x, y, self.s(240), self.s(54))
        self.back_btn.rect.update(x + self.s(260), y, self.s(180), self.s(54))

        return list_rect, detail_rect

    def _populate_editor_from_state(self, st):
        self.edit_monkeyL.value = st["config"].get("left_name", st["config"]["leader"])
        self.edit_monkeyR.value = st["config"].get("right_name", st["config"]["follower"])
        self.edit_stim.value    = st["config"]["stimuli"]

        # Set the radio based on who is currently the leader
        left_name  = st["config"].get("left_name", st["config"]["leader"])
        leader     = st["config"]["leader"]
        self.edit_radio.left_is_leader = (leader == left_name)

        self.edit_session.value = int(st["progress"]["session_index"])
        next_trial = st["progress"]["completed_trios"] + 1
        self.edit_trial.value = max(1, min(28, next_trial))


    def _apply_editor_to_state(self, st):
        left_name = self.edit_monkeyL.value
        right_name = self.edit_monkeyR.value

        # Optional guard
        if not left_name or not right_name or left_name == right_name:
            self.error_lines = ["Left and Right monkeys must be different."]
            return

        if self.edit_radio.left_is_leader is True:
            leader, follower = left_name, right_name
        else:
            leader, follower = right_name, left_name

        st["config"]["leader"]    = leader
        st["config"]["follower"]  = follower
        st["config"]["left_name"] = left_name
        st["config"]["right_name"] = right_name

        # Keep old stimuli if dropdown unset (optional)
        if self.edit_stim.value is not None:
            st["config"]["stimuli"] = self.edit_stim.value

        set_next_trial(st, session_index=self.edit_session.value, next_trial=self.edit_trial.value)

        new_uid = make_uid(
            st["config"]["leader"],
            st["config"]["follower"],
            st["config"]["stimuli"],
            st["config"]["sessions_total"],
        )
        if new_uid != st["uid"]:
            old = _state_path(st["uid"])  # use local helper for consistency
            st["uid"] = new_uid
            try:
                os.remove(old)
            except FileNotFoundError:
                pass
    
    def _first_open_dropdown(self):
        """Return a reference to the first open dropdown in current mode, else None."""
        if self.mode == "launch":
            for dd in (self.sessions_dd, self.monkeyL_dd, self.monkeyR_dd, self.stim_dd):
                if dd.open:
                    return dd
        elif self.mode == "resume_menu":
            for dd in (self.edit_monkeyL, self.edit_monkeyR, self.edit_stim):
                if dd.open:
                    return dd
        return None



    # --------------- public API ---------------
    def run(self):
        """Block here until user launches/resumes or quits.

        Returns:
            state dict on success, or None if the user quits.
        """
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    return None
                if event.type == KEYDOWN and (event.key == K_ESCAPE or event.key == K_q):
                    return None
                
                # --- If any dropdown is open, route this event ONLY to that dropdown and skip others
                open_dd = self._first_open_dropdown()
                if open_dd is not None:
                    selected = open_dd.handle(event)

                    # If a selection was actually made, enforce "Left ≠ Right" for monkey pickers
                    if selected is not None:
                        if self.mode == "launch":
                            if open_dd is self.monkeyL_dd and self.monkeyR_dd.value == self.monkeyL_dd.value:
                                self.monkeyR_dd.value = None
                            elif open_dd is self.monkeyR_dd and self.monkeyL_dd.value == self.monkeyR_dd.value:
                                self.monkeyL_dd.value = None
                        elif self.mode == "resume_menu":
                            if open_dd is self.edit_monkeyL and self.edit_monkeyR.value == self.edit_monkeyL.value:
                                self.edit_monkeyR.value = None
                            elif open_dd is self.edit_monkeyR and self.edit_monkeyL.value == self.edit_monkeyR.value:
                                self.edit_monkeyL.value = None

                    # Consume this frame's event so controls underneath don't react to the same click/scroll
                    continue



                if self.mode == "launch":
                    self.date_input.handle(event)
                    self.sessions_dd.handle(event)
                    if self.monkeyL_dd.handle(event) is not None and self.monkeyR_dd.value == self.monkeyL_dd.value:
                        self.monkeyR_dd.value = None
                    if self.monkeyR_dd.handle(event) is not None and self.monkeyL_dd.value == self.monkeyR_dd.value:
                        self.monkeyL_dd.value = None
                    self.radio.handle(event)
                    self.stim_dd.handle(event)

                    if self.reset_btn.handle(event):
                        self._reset_launch()
                        self.error_lines = []

                    if self.resume_btn.handle(event):
                        self.mode = "resume_menu"
                        self.error_lines = []
                        load_all_states()
                        self.selected_uid = next(iter(INCOMPLETE.keys()), None)
                        if self.selected_uid:
                            self._populate_editor_from_state(INCOMPLETE[self.selected_uid])

                    if self.launch_btn.handle(event):
                        ok, msgs = self._validate_launch()
                        if ok:
                            Lrole, _ = self._current_roles_launch()
                            left_name = self.monkeyL_dd.value
                            right_name = self.monkeyR_dd.value
                            leader = left_name if Lrole == "Leader" else right_name
                            follower = right_name if Lrole == "Leader" else left_name
                            uid = make_uid(leader, follower, self.stim_dd.value, int(self.sessions_dd.value))
                            config = {
                                "leader": leader,
                                "follower": follower,
                                "stimuli": self.stim_dd.value,
                                "sessions_total": int(self.sessions_dd.value),
                                "left_name": left_name,         # <- add
                                "right_name": right_name,       # <- add
                            }

                            state, is_resume = new_or_resume_state(uid, config)
                            return state
                        else:
                            self.error_lines = msgs[:]

                elif self.mode == "resume_menu":
                    # list selection
                    if event.type == MOUSEBUTTONDOWN and event.button == 1:
                        list_rect, _ = self._layout_resume_panels()
                        item_h = self.s(64)
                        top_y = list_rect.y + self.s(48)
                        uid_rows = []
                        for uid, st in list(INCOMPLETE.items()):
                            if top_y + item_h > list_rect.bottom - self.s(10):
                                break
                            row = pygame.Rect(list_rect.x + self.s(8), top_y, list_rect.w - self.s(16), item_h)
                            uid_rows.append((row, uid))
                            top_y += item_h + self.s(8)
                        for r, uid in uid_rows:
                            if r.collidepoint(event.pos):
                                if self.selected_uid != uid:
                                    self.selected_uid = uid
                                    self._populate_editor_from_state(INCOMPLETE[uid])
                                break

                    # pass into controls
                    self.edit_monkeyL.handle(event)
                    self.edit_monkeyR.handle(event)
                    self.edit_stim.handle(event)
                    self.edit_radio.handle(event)
                    self.edit_session.handle(event)
                    self.edit_trial.handle(event)

                    if self.back_btn.handle(event):
                        self.mode = "launch"
                        self.selected_uid = None
                        self.error_lines = []
                        load_all_states()

                    if self.restart_btn.handle(event):
                        if not self.selected_uid:
                            self.error_lines = ["Select a session from the list."]
                        else:
                            st = INCOMPLETE[self.selected_uid]
                            self._apply_editor_to_state(st)
                            save_state(st)
                            load_all_states()
                            self.selected_uid = st["uid"] if st["uid"] in INCOMPLETE else None
                            return st

            # ---------- DRAW ----------
            self.screen.fill(self.BG)
            self._draw_text(self.screen, "KM + JBT — Launch", self.TITLE_FONT, self.FG, self.title_rect.centerx, self.title_rect.centery, "center")

            if self.mode == "launch":
                left_col_x = self._left_col_x
                right_col_x = self._right_col_x

                self._draw_text(self.screen, "Date", self.FONT_SMALL, self.FG, left_col_x, self.date_input.rect.y - self.s(22))
                self._draw_text(self.screen, "Sessions", self.FONT_SMALL, self.FG, right_col_x, self.sessions_dd.rect.y - self.s(22))
                self._draw_text(self.screen, "Monkey L", self.FONT_SMALL, self.FG, left_col_x, self.monkeyL_dd.rect.y - self.s(22))
                self._draw_text(self.screen, "Monkey R", self.FONT_SMALL, self.FG, right_col_x, self.monkeyR_dd.rect.y - self.s(22))
                self._draw_text(self.screen, "Leader / Follower", self.FONT_SMALL, self.FG, left_col_x, (self.monkeyL_dd.rect.bottom + self.s(10)))
                self._draw_text(self.screen, "Stimuli Set", self.FONT_SMALL, self.FG, left_col_x, self.stim_dd.rect.y - self.s(22))

                self.date_input.draw(self.screen)
                self.sessions_dd.draw(self.screen)
                self.monkeyL_dd.draw(self.screen)
                self.monkeyR_dd.draw(self.screen)
                self.radio.draw(self.screen)
                self.stim_dd.draw(self.screen)

                self.reset_btn.draw(self.screen)
                self.resume_btn.draw(self.screen)
                self.launch_btn.draw(self.screen)

                Lrole, Rrole = self._current_roles_launch()
                if Lrole:
                    self._draw_text(self.screen, f"Left: {Lrole}", self.FONT_SMALL, self.OKGREEN, left_col_x,  self.radio.left_pos[1]  + self.s(24))
                    self._draw_text(self.screen, f"Right: {Rrole}", self.FONT_SMALL, self.OKGREEN, right_col_x, self.radio.right_pos[1] + self.s(24))

                # overlays last
                for dd in [self.sessions_dd, self.monkeyL_dd, self.monkeyR_dd, self.stim_dd]:
                    if dd.open:
                        dd.draw(self.screen, force_front=True)

                if self.error_lines:
                    # Optional: subtle translucent backdrop for readability
                    band_h = self.s(28) * len(self.error_lines) + self.s(16)
                    band = pygame.Surface((self.W, band_h), pygame.SRCALPHA)
                    band.fill((0, 0, 0, 60))
                    self.screen.blit(band, (0, self.H - band_h))

                    # Draw lines from bottom up, centered
                    y = self.H - self.s(12)  # bottom margin
                    for line in reversed(self.error_lines):
                        t = f"• {line}"
                        # midbottom anchored, centered horizontally
                        self._draw_text(self.screen, t, self.FONT_SMALL, self.ERROR, self.W // 2, y, anchor="midbottom")
                        y -= self.s(28)

            elif self.mode == "resume_menu":
                list_rect, detail_rect = self._layout_resume_panels()

                # left panel
                pygame.draw.rect(self.screen, self.BTN_BG, list_rect, border_radius=self.s(12))
                pygame.draw.rect(self.screen, self.BTN_BORDER, list_rect, self.s(2), border_radius=self.s(12))
                self._draw_text(self.screen, "Incomplete Sessions", self.FONT, self.FG, list_rect.x + self.s(12), list_rect.y + self.s(10))

                # items
                item_h = self.s(64)
                top_y = list_rect.y + self.s(48)
                for uid, st in list(INCOMPLETE.items()):
                    if top_y + item_h > list_rect.bottom - self.s(10):
                        break
                    row = pygame.Rect(list_rect.x + self.s(8), top_y, list_rect.w - self.s(16), item_h)
                    pygame.draw.rect(self.screen, self.BTN_BG_HOVER if uid == self.selected_uid else (252, 252, 252), row, border_radius=self.s(8))
                    pygame.draw.rect(self.screen, self.BTN_BORDER, row, self.s(1), border_radius=self.s(8))
                    leader = st["config"]["leader"]; follower = st["config"]["follower"]
                    sess = st["progress"]["session_index"]; trial = st["progress"]["completed_trios"] + 1
                    line1 = f"{leader} (Leader) + {follower} (Follower)"
                    line2 = f"Session {sess} — Next Trial {trial} — Stim: {st['config']['stimuli']}"
                    self._draw_text(self.screen, line1, self.FONT_SMALL, self.FG, row.x + self.s(10), row.y + self.s(10))
                    self._draw_text(self.screen, line2, self.FONT_SMALL, (60, 60, 60), row.x + self.s(10), row.bottom - self.s(22))
                    top_y += item_h + self.s(8)

                # right panel
                pygame.draw.rect(self.screen, self.BTN_BG, detail_rect, border_radius=self.s(12))
                pygame.draw.rect(self.screen, self.BTN_BORDER, detail_rect, self.s(2), border_radius=self.s(12))
                self._draw_text(self.screen, "Edit & Restart", self.FONT, self.FG, detail_rect.x + self.s(12), detail_rect.y + self.s(10))

                # labels
                self._draw_text(self.screen, "Monkey L",          self.FONT_SMALL, self.FG, self.edit_monkeyL.rect.x,       self.edit_monkeyL.rect.y - self.s(22))
                self._draw_text(self.screen, "Monkey R",          self.FONT_SMALL, self.FG, self.edit_monkeyR.rect.x,       self.edit_monkeyR.rect.y - self.s(22))
                self._draw_text(self.screen, "Stimuli",           self.FONT_SMALL, self.FG, self.edit_stim.rect.x,          self.edit_stim.rect.y    - self.s(22))
                self._draw_text(self.screen, "Leader / Follower", self.FONT_SMALL, self.FG, self.edit_radio.left_pos[0],    self.edit_radio.left_pos[1] - self.s(38))
                self._draw_text(self.screen, "Session #",         self.FONT_SMALL, self.FG, self.edit_session.rect.x,       self.edit_session.rect.y  - self.s(22))
                self._draw_text(self.screen, "Next Trial #",      self.FONT_SMALL, self.FG, self.edit_trial.rect.x,         self.edit_trial.rect.y    - self.s(22))

                # controls
                self.edit_monkeyL.draw(self.screen); self.edit_monkeyR.draw(self.screen); self.edit_stim.draw(self.screen); self.edit_radio.draw(self.screen)
                self.edit_session.draw(self.screen); self.edit_trial.draw(self.screen)
                self.restart_btn.draw(self.screen);  self.back_btn.draw(self.screen)

                for dd in [self.edit_monkeyL, self.edit_monkeyR, self.edit_stim]:
                    if dd.open:
                        dd.draw(self.screen, force_front=True)

                if self.error_lines:
                    band_h = self.s(28) * len(self.error_lines) + self.s(16)
                    band = pygame.Surface((detail_rect.w, band_h), pygame.SRCALPHA)
                    band.fill((0, 0, 0, 60))
                    self.screen.blit(band, (detail_rect.x, detail_rect.bottom - band_h))

                    y = detail_rect.bottom - self.s(12)
                    for line in reversed(self.error_lines):
                        t = f"• {line}"
                        # center within the right panel
                        self._draw_text(self.screen, t, self.FONT_SMALL, self.ERROR, detail_rect.centerx, y, anchor="midbottom")
                        y -= self.s(28)

            pygame.display.flip()
            self.clock.tick(60)


# keep the class; add this simple wrapper so function-style callers work too
def run(screen, clock):
    scene = LaunchScene(screen, clock)
    outcome, state = scene.run()
    # function API historically returned just the state or None
    return None if outcome == "quit" else state
