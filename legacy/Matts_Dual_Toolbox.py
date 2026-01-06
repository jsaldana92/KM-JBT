#___  ___      _   _   _         ___       _       _     _____           _______           
#|  \/  |     | | | | ( )       |_  |     (_)     | |   |_   _|         | | ___ \          
#| .  . | __ _| |_| |_|/ ___      | | ___  _ _ __ | |_    | | ___   ___ | | |_/ / _____  __
#| |\/| |/ _` | __| __| / __|     | |/ _ \| | '_ \| __|   | |/ _ \ / _ \| | ___ \/ _ \ \/ /
#| |  | | (_| | |_| |_  \__ \ /\__/ / (_) | | | | | |_    | | (_) | (_) | | |_/ / (_) >  < 
#\_|  |_/\__,_|\__|\__| |___/ \____/ \___/|_|_| |_|\__|   \_/\___/ \___/|_\____/ \___/_/\_\
                                                                                          
import sys
import random
import math
import time
import os
import glob
import pygame
import platform 
sys.path.append("c:")
sys.path.append("..")                                                                                          

from pygame.locals import *


pygame.init()

# READ TECHNICAL FILES ----------------------------------------------------

# Pellet Dispensing
pelletPath = ['c:/pellet1.exe', 'c:/pellet2.exe']

# Grab the monkey names from monkey_names.txt
with open("monkey_names.txt") as f:
    monkey = f.read()
    monkey = monkey.split(' ')

# set current date
today = time.strftime('%Y-%m-%d')

# SET UNIVERSAL VARIABLES  ---------------------------------------------------------------------------------------------
white = (255, 255, 255)
black = (0, 0, 0)
green = (0, 200, 0)
red = (255,48,48)
transparent = (0, 0, 0, 0)

# SET SCREEN VARIABLES ------------------------------------------------------------------------------------------------
scrSize = (1024, 768)
bg = pygame.Surface(scrSize)
wall = pygame.Surface(scrSize)

scrRect0 = pygame.Rect((0, 0), (500, 768))
scrRect1 = pygame.Rect((524, 0), (500, 768))

#wall.fill(Color('white'))
#wall.fill(Color('black'), (500, 0, 24, 768))
wall.fill(white)
wall.fill(black, (500, 0, 24, 768))

fps = 60

sound_correct = pygame.mixer.Sound("correct.wav")
sound_incorrect = pygame.mixer.Sound("incorrect.wav")

# DISPLAY FUNCTIONS----------------------------------------------------------------------------------------------------
def setScreen(full_screen = True, size = scrSize):
    """Define screen with scrSize, no frame, and full screen. Option to set 
       full_screen = False for window display (for development)."""
    if full_screen:
        #return pygame.display.set_mode(size, (NOFRAME and FULLSCREEN))
        return pygame.display.set_mode(size, pygame.FULLSCREEN)
    else:
        return pygame.display.set_mode(size)

def refresh(surface):
    """Blit background to screen and update display."""
    surface.blit(bg, (0, 0))
    pygame.display.update()


# BOX CLASS -----------------------------------------------------------------------------------------------------------
class Box(pygame.sprite.Sprite):
    """Class for box with default dimensions (20, 20), in screen center, red 
       colour, and speed 8."""

    def __init__(self, size = (20, 20), position = (512, 384), color = (red), speed = 10, circle = False):
        super(Box, self).__init__()
        self.size = size
        self.color = color
        self.speed = speed
        self.circle = circle
        
        self.image = pygame.Surface(size)
        self.image.fill(color)
        self.image.set_colorkey(white)
        self.rect = self.image.get_rect()
        self.rect.center = self.position = position

        if self.circle == True:
            self.image.fill(white)
            pygame.draw.ellipse(self.image, self.color, (0, 0, self.size[0], self.size[1]))

        self.mask = pygame.mask.from_surface(self.image)

    def update(self, size = None, color = None, position = None, speed = None):
        """Update box size, colour, position, and speed. Keep current values 
           unless a different one is passed to the method."""
        self.size = size or self.size
        self.color = color or self.color
        self.position = position or self.position
        self.speed = speed or self.speed

        self.image = pygame.Surface(self.size)
        self.image.fill(self.color)
        self.image.set_colorkey(white)
        self.rect = self.image.get_rect()
        self.rect.center = self.position

        if self.circle:
            self.image.fill(white)
            pygame.draw.ellipse(self.image, self.color, (0, 0, self.size[0], self.size[1]))
            
        self.mask = pygame.mask.from_surface(self.image)

    def draw(self, surface):
        """Draw box onto display/screen assigned with setScreen()."""
        surface.blit(self.image, self.rect)

    def move(self, side, x, y):
        """Move box x pixels to the right and y pixels down. Keep box on-screen."""
        self.rect.move_ip(x * self.speed, y * self.speed)
        if side:
            self.rect.clamp_ip(scrRect1)
        else:
            self.rect.clamp_ip(scrRect0)
            
        self.update(position = self.rect.center)

    def mv2pos(self, position = None):
        """Move box to position (x, y)."""
        self.update(position = position)

    def collides_with(self, sprite):
        offset_x = sprite.rect.left - self.rect.left
        offset_y = sprite.rect.top - self.rect.top
        return self.mask.overlap(sprite.mask, (offset_x, offset_y)) is not None

    def collides_with_list(self, list):
        """Test for pixel-perfect collision with a sprite in the list, returns index. 
           Returns -1 when no collision is occuring."""
        for i, sprite in enumerate(list):
            if self.collides_with(sprite):
                return i                              # Returns the index of the icon if collision is occurring
        return -1                                     # Returns -1 when no collision is occurring

# Moving the Cursor ---------------------------------------------------------------------------------------------------

joyCount = pygame.joystick.get_count()
if joyCount == 2:
    joy0 = pygame.joystick.Joystick(1)
    joy1 = pygame.joystick.Joystick(0)
    joy0.init()
    joy1.init()

pygame.mouse.set_visible(False) # Hide the Mouse

def moveCursor(cursor, side = 0, only = None, diagonal = True):
    """Move cursor via joystick (if available) or arrow keys (if not). 
       Directions can be constrained by a passing string to `only`. If passing 
       several directions, separate with `, ` (comma *and* space). Suppress 
       diagnoal moves with diag = False. Returns boolean True (False) when 
       cursor is (not) moving."""
    # no movement unless kb or joystick input
    x_dir = y_dir = 0

    # gets key presses
    key = pygame.key.get_pressed()

    # move cursor with arrow keys
    if joyCount == 0:
        if side:
            if key[K_LEFT]:
                x_dir = -1
            if key[K_RIGHT]:
                x_dir =  1
            if key[K_UP]:
                y_dir = -1
            if key[K_DOWN]:
                y_dir =  1
        else:
            if key[K_a]:
                x_dir = -1
            if key[K_d]:
                x_dir =  1
            if key[K_w]:
                y_dir = -1
            if key[K_s]:
                y_dir =  1

    # move cursor with joystick
    if joyCount > 0:
        if side:
            x_dir = round(joy1.get_axis(0))
            y_dir = round(joy1.get_axis(1))
        else:
            x_dir = round(joy0.get_axis(0))
            y_dir = round(joy0.get_axis(1))

    # constrain to cardinal directions
    if not diagonal:
        if x_dir != 0:
            y_dir = 0
        if y_dir != 0:
            x_dir = 0

    if only:
    # if the argument `only` is specified:
    # - get direction constraints as list
    # - reset all directions that are not specified
        only = only.split(', ')
        if x_dir < 0 and 'left' not in only:
            x_dir = 0
        if x_dir > 0 and 'right' not in only:
            x_dir = 0
        if y_dir < 0 and 'up' not in only:
            y_dir = 0
        if y_dir > 0 and 'down' not in only:
            y_dir = 0

    cursor.move(side, x_dir, y_dir)

    if x_dir == y_dir == 0:
        return False
    else:
        return True

# helper functions
def sound(sound_boolean):               # Pass True to play correct.wav
    if sound_boolean:                   # Pass False to play incorrect.wav
        sound_correct.play()            # TODO: Make it so correct is the only sound ever played
    else:                               # TODO: or remove the sounds entirely
        sound_incorrect.play()

def pellet(side = 0, num = 1):
    """Dispense [num] pellets. Prints 'Pellet' if `pellet.exe` is not found (for 
       development). Waits 500ms between pellets."""
    for i in range(num):
        if os.path.isfile(pelletPath[side]):
            os.system(pelletPath[side])
            print(pelletPath)
        else:
            print ("Pellet for" + str(monkey[side]))
        pygame.time.delay(500)

def quitEscQ(file = None):
    """Quit pygame on QUIT, [Esc], and [Q]. Use inside main game loop. Optional 
       argument adds blank line to file before exiting."""
    for event in pygame.event.get():
        if event.type == QUIT or (event.type == KEYDOWN and (event.key in (K_ESCAPE, K_q))):
            if file:    writeLn(file)
            pygame.quit()
            sys.exit()


# file manipulations
def writeLn(filename, data = '', csv = True):
    """Write a list to a file as comma- or tab-delimited. Not passing a list 
       results in a blank line."""
    file = open(filename, 'a')

    if csv:    file.write(','.join(map(str, data)) + '\n')
    else:      file.write('\t'.join(map(str, data)) + '\n')

    file.close()

def makeFileName(task = 'Task', format = 'csv'):
    """Return string of the form MonkeyName_Task_Date.format."""
    return monkey[0] + monkey[1] + '_' + task + '_' + today + '.' + format

def getParams(varNames, filename='parameters.txt'):
    """Read in all even lines from parameters.txt. Takes a list of variable names
       as argument and stores them with their values. Returns a dictionary.
       Encase text values in the parameter file in "", lists in [], etc.!"""
    params = {}
    with open(filename) as txt:
        for i, line in enumerate(txt):
            if i % 2 == 1:
                j = i // 2
                params[varNames[j]] = line.strip('\r\n')
    for key, val in params.items():
        exec('params[key] = %s' % val)
    return params

def saveParams():
    pass

# RANDOMIZATION FUNCTIONS ---------------------------------------------------------------------------------------------

def pseudorandomize(array):
    random.shuffle(array)
    new_array = array
    i = 3
    while i <= len(new_array) - 1:
        if new_array[i] == new_array[i - 1] and new_array[i - 2]:
            random.shuffle(new_array)
            i = 3
        i += 1
    return new_array

def shuffle_array(array):
    random.shuffle(array)
    new_array = array
    return new_array

