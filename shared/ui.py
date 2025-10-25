# shared/ui.py
import pygame
from pygame.locals import *

def s(H, x): return int((x / 800) * H)

class Button:
    def __init__(self, rect, label, fonts, colors, scale_fn):
        self.rect = pygame.Rect(rect); self.label = label; self.hover=False
        self.FONT = fonts["FONT"]; self.BTN_BG = colors["BTN_BG"]; self.BTN_BG_HOVER = colors["BTN_BG_HOVER"]
        self.BTN_BORDER = colors["BTN_BORDER"]; self.FG = colors["FG"]; self.s = scale_fn
    def draw(self, surface):
        pygame.draw.rect(surface, self.BTN_BG_HOVER if self.hover else self.BTN_BG, self.rect, border_radius=self.s(10))
        pygame.draw.rect(surface, self.BTN_BORDER, self.rect, self.s(2), border_radius=self.s(10))
        txt = self.FONT.render(self.label, True, self.FG)
        surface.blit(txt, txt.get_rect(center=self.rect.center))
    def handle(self, event):
        if event.type == MOUSEMOTION: self.hover = self.rect.collidepoint(event.pos)
        if event.type == MOUSEBUTTONDOWN and event.button==1 and self.rect.collidepoint(event.pos): return True
        return False

# (You can migrate your Dropdown, TextInput, RadioPair here later if you want them shared
# between scenes. For now, leaving them inside launch.py is fine.)
