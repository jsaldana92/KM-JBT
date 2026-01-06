#.-. .-')     ('-.     _  .-')           _ (`-.                                  
#\  ( OO )   ( OO ).-.( \( -O )         ( (OO  )                                 
# ;-----.\   / . --. / ,------.        _.`     \,--. ,--.    ,--.      ,--.      
# | .-.  |   | \-.  \  |   /`. '      (__...--''|  | |  |    |  |.-')  |  |.-')  
# | '-' /_).-'-'  |  | |  /  | |       |  /  | ||  | | .-')  |  | OO ) |  | OO ) 
# | .-. `.  \| |_.'  | |  |_.' |       |  |_.' ||  |_|( OO ) |  |`-' | |  |`-' | 
# | |  \  |  |  .-.  | |  .  '.'       |  .___.'|  | | `-' /(|  '---.'(|  '---.' 
# | '--'  /  |  | |  | |  |\  \        |  |    ('  '-'(_.-'  |      |  |      |  
# `------'   `--' `--' `--' '--'       `--'      `-----'     `------'  `------'  
#Joint Bar Pull: for use with subject + conspecific

"""original code by MHB"""
# Do NOT use without permission from author!!! Copyright pending.
                                                                
'''WRITTEN IN PYTHON 3.6'''

'''HOW TO USE THIS FILE'''

'''MASTER TODO LIST'''

'''FINISHED TODO ITEMS'''
#scrSize = (1024, 768)

import sys
import random               # Import the 'random' library which gives cool functions for randomizing numbers
import math                 # Import the 'math' library for more advanced math operations
import time                 # Import the 'time' library for functions of keeping track of time (ITIs, IBIs etc.)
import datetime
import os                   # Import the operating system (OS)
import glob                 # Import the glob function
import pygame               # Import Pygame to have access to all those cool functions

pygame.init()               # This initializes all pygame modules

# Grab the monkey name from monkey_names.txt
# Split the two monkey names by ' '
with open("monkey_names.txt") as f:
    monkey = f.read()
    monkey = monkey.split(' ')
# Grab the monkey group name from monkey_group.txt
with open("monkey_group.txt") as f:
    monkey_group = f.read()

# Set Current Date
today = time.strftime('%Y-%m-%d')

fps = 60

sys.path.append('c:/')
sys.path.append('..')
#from lrc1024 import *
from Matts_Dual_Toolbox import *

"""Put your sounds here"""
sound_chime = pygame.mixer.Sound("chime.wav")                   # This sets your trial initiation sound
sound_correct = pygame.mixer.Sound("correct.wav")               # This sets your correct pellet dispensing sound
sound_incorrect = pygame.mixer.Sound("Incorrect.wav")           # This sets your incorrect sound
sound_sparkle = pygame.mixer.Sound("sparkle.wav")

pelletPath = ['c:/pellet1.exe', 'c:/pellet2.exe']


def pellet(side = [0,1], num = 1):
    """Dispense [num] pellets - 2nd argument will change number of pellets when called. Prints 'Pellet' if `pellet.exe` is not found (for
       development). Waits 500ms between pellets."""
    """side = 0 for Left; side = 1 for Right"""
    for i in range(num):
        if os.path.isfile(pelletPath[side]):
            os.system(pelletPath[side])
        else:
            print ("Pellet for " + str(monkey[side]))
            
        pygame.time.delay(500)

#trial_number = 0
#def increment():
#        global trial_number
#        trial_number = trial_number + 1

def makeFileName(task = 'Task', format = 'csv'):
    """Return string of the form SubjectStooge_Task_Date.format."""
    return monkey[0] + '_' + monkey[1] + '_' + task + '_' + today + '.' + format


start_button = Box((200, 100), (512, 384), Color('gray'))
font = pygame.font.SysFont('Calibri', 20)
starttext = font.render('GO', 1, Color('black'))
startpos = starttext.get_rect(centerx = 512, centery = 384)


"""ICON CLASS -------------------------------------------------------------------------------------------------------"""


class Image(Box):
    '''Image sprite. Inherits from toolbox Box class. Loads image from `index` 
       (column, row) in spritesheet. Image is scaled to 200x200px and centered 
       at (400, 300).'''
    def __init__(self, PNG, position, scale):                                  # Pass the image and position (x,y)
        super(Image, self).__init__()
        image = pygame.image.load(PNG).convert_alpha()                          # image = image you passed in arguments
        self.size = image.get_size()                                            # Get the size of the image
        self.image = pygame.transform.smoothscale(image, scale)                 # Scale the image = scale inputted
        self.rect = self.image.get_rect()                                       # Get rectangle around the image
        self.rect.center = self.position = position                             # Set rectangle and center at position
        self.mask = pygame.mask.from_surface(self.image)                        # Creates a mask object

    def mv2pos(self, pos):
        """Move image to position (x, y)."""
        self.rect = self.image.get_rect()
        self.rect.center = self.pos = pos

"""TRIAL CLASS -----------------------------------------------------------------------------------------------------"""

class Trial(object):
    def __init__(self):
        '''Initialise trial with properties set to 0 or empty. `present` is True 
           when sample is presented, False when choice occurs.'''
        self.trial_number = 0
        self.trial_within_block = -1
        self.block = 1
        self.block_length = trials_per_block
        self.blocks_per_session = blocks_per_session
        self.LorR = (0, 0)
        self.startphase = True
        self.phase1 = False
        self.phase2 = False

        self.zone_touched = False
        
        self.stimID = 0
        self.stimuli = []
        self.trial_type = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
                           1, 1, 1, 1, 1, 1, 1, 1, 1, 1]        
        
        

    def new(self):
        global subselection
        global SELECT1
        self.trial_number += 1                                                # Increment trial number by 1
        self.trial_within_block += 1                                          # Increment trial within block by 1
        print("Trial: " + str(self.trial_number))
        print("Trial_within_block: " + str(self.trial_within_block))
        print(self.trial_type)

        if self.trial_within_block == self.block_length:                      # If this is the last trial in the block
            self.trial_within_block = 0                                       # Reset this to 0           
            self.newBlock()                                                   # Run .newBlock()
            print("Block Complete!")

        self.startphase = True
        self.phase1 = False
        self.phase2 = False
        self.start_time = 0

        self.zone_touched = False

        self.create_stimuli()
        cursor1.mv2pos((225, 450))
        cursor2.mv2pos((801, 450))

        self.start_time = pygame.time.get_ticks()

    def newBlock(self):
        """Moves program to the next block and randomizes the trial types"""
        self.stimID = 0
        self.block += 1

        if self.block > self.blocks_per_session:
            print("Session Complete!")
            pygame.quit()
            sys.exit()

    def create_stimuli(self):
        """Create the stimuli based on the trial type"""
        global icon_condition

        Images = [Image("start.png", (512, 400), (400, 200)),
                    Image("pull_zone.png", (-500, -500), (1000, 500)),
                    Image("pull_zone_cursor1.png", (-500, -500), (1000, 500)),
                    Image("pull_zone_cursor2.png", (-500, -500), (1000, 500))]

        self.stimuli = [Images[0], Images[1], Images[2], Images[3]]

    def draw_start(self):
        """Draw the start button at center of the screen"""
        self.stimuli[0].mv2pos((512, 500))
        self.stimuli[0].draw(bg)

    def draw_pull_zone(self):
        """Draw the stimuli at their positions after start button is selected"""
        self.stimuli[1].mv2pos((512, -125))
        self.stimuli[1].draw(bg)
        self.stimuli[2].mv2pos((-500, -500))
        self.stimuli[2].size = 0
        self.stimuli[3].mv2pos((-500, -500))
        self.stimuli[3].size = 0

    def update_pull_zone(self, cursor):
        if cursor == 1:
            self.stimuli[2].mv2pos((512, -120))
            self.stimuli[2].size = (1000, 500)
            self.stimuli[2].draw(bg)
            self.stimuli[3].mv2pos((-10000, -10000))
            self.stimuli[3].size = 0
        elif cursor == 2:
            self.stimuli[3].mv2pos((512, -120))
            self.stimuli[3].size = (1000, 500)
            self.stimuli[3].draw(bg)
            self.stimuli[2].mv2pos((-10000, -10000))
            self.stimuli[2].size = 0

    def trial_duration(self):
        global duration
        global timer
        global SELECT1
        global SELECT2
        seconds = 0

        if seconds < duration:
            seconds = ((pygame.time.get_ticks() / 1000) - self.start_time - 1.000)
            #print(seconds)

        if seconds > duration and self.zone_touched == True:
            seconds = seconds
        elif seconds > duration and self.zone_touched == False:
            sound(False)
            print("No response made! WRONG!")
            self.write(data_file, 0)
            bg.fill(white)
            refresh(screen)
            pygame.time.delay(ITI*1000)
            self.startphase = True
            self.phase1 = False
            self.phase2 = False
            seconds = 0
            self.new()

        return seconds

    def time_delay(self):
        """This function counts up time (0.000s) since the start button was touched"""
        delay_counter = ((pygame.time.get_ticks() - self.start_time)/1000)
        print(delay_counter)
        return delay_counter

    def response_time(self):
        seconds = 0
        if seconds < duration:
            seconds = ((pygame.time.get_ticks() / 1000) - self.start_time - 1.000)

        return seconds

    def resetSample(self):
        '''Reset sample to left or right position.'''
        self.stimuli[0].mv2pos(pos[0])


# Start Phase ----------------------------------------------------------------------------------------
    def start(self):
        global delay
        """Draw start_button, show response screen upon collision."""
        #self.start_time = (pygame.time.get_ticks() / 1000)
        moveCursor(cursor1, side = 0, only = 'down')
        moveCursor(cursor2, side = 1, only = 'down')
        #cursor1.draw(bg)
        #cursor2.draw(bg)
        if self.time_delay() >= delay:
            sound_chime.play()
            self.startphase = False
            self.phase2 = True

        
# Phase 1 ---------------------------------------------------------------------------------------------
    def run_delay_phase(self):
        self.stimuli[0].mv2pos((-50, -50))
        self.stimuli[0].size = 0
        cursor1.draw(bg)
        cursor2.draw(bg)
        self.delay_duration()

    def delay_duration(self):
        global timer
        global SELECT1
        global SELECT2
        seconds = 0
        if seconds < 1:
            seconds = ((pygame.time.get_ticks() / 1000) - self.start_time)
            #print(seconds)

        if seconds > 1:
            self.phase1 = False
            print("Phase 1: False")
            self.phase2 = True
            print("Phase 2: True")
            seconds = 0

        return seconds
        

# Phase 2 -------------------------------------------------------------------------------------------
    def run_trial(self):
        global SELECT1
        global SELECT2
        global button_positions
        global duration

        moveCursor(cursor1, side = 0, only = 'up')
        moveCursor(cursor2, side = 1, only = 'up')
        cursor1.draw(bg)
        cursor2.draw(bg)
        # Remove start button
        self.stimuli[0].mv2pos((-500, -500))
        self.stimuli[0].size = 0
        
        self.draw_pull_zone()
        #self.trial_duration()
        self.response_time()

        self.zone_touched = False
        self.first_monkey = 0
            

        # If left cursor collides with the pull_zone, activate it to stimuli[2]
        if cursor1.collides_with(self.stimuli[1]) and moveCursor(cursor1, side = 0, only = 'up') == True:
            self.stimuli[1].mv2pos((10000, 10000))                                    # Remove pull zone from the screen
            self.stimuli[1].size = 0
            self.stimuli[3].mv2pos((10000, 10000))
            self.stimuli[3].size = 0
            self.update_pull_zone(cursor = 1)                                       # Draw cursor1's activated pull zone
            cursor1.mv2pos((225, 60))
            cursor1.draw(bg)                                                        # Draw cursor1 on top of the activated pull zone so it doesn't disappear
            cursor2.draw(bg)
            self.zone_touched = True
            #if cursor2.collides_with(self.stimuli[2]):
            #    print("Wow nice work Monkey 1 (LEFT)")
            #    sound(True)
            #    self.write(data_file, 1, 1)
            #    pellet(side = 0, num = 1)
            #    pellet(side = 1, num = 1)
            #    bg.fill(white)
            #    refresh(screen)
            #    pygame.time.delay(ITI * 1000)
            #    self.new()
        # If right cursor collides with the pull_zone, activate it to stimuli[3]
        elif cursor2.collides_with(self.stimuli[1]) and moveCursor(cursor2, side = 1, only = 'up') == True:
            self.stimuli[1].mv2pos((10000, 10000))                                      # Remove pull zone from the screen
            self.stimuli[1].size = 0
            self.stimuli[2].mv2pos((10000, 10000))
            self.stimuli[2].size = 0
            self.update_pull_zone(cursor = 2)                                       # Draw cursor2's activated pull zone
            cursor2.mv2pos((800, 60))
            cursor2.draw(bg)                                                        # Draw cursor2 on top of the activated pull zone so it doesn't disappear
            cursor1.draw(bg)
            self.zone_touched = True
            #if cursor1.collides_with(self.stimuli[3]):
            #    print("Good job Monkey 2 (RIGHT)")
            #    sound(True)
            #    self.write(data_file, 1, 2)
            #    pellet(side = 0, num = 1)
            #    pellet(side = 1, num = 1)
            #    bg.fill(white)
            #    refresh(screen)
            #    pygame.time.delay(ITI * 1000)
            #    self.new()

        # If neither cursor are colliding with the pull zone, remove the other pull zones from the screen
        elif SELECT1 == -1 and SELECT2 == -1:
            self.stimuli[2].mv2pos((-500, -100))
            self.stimuli[2].size = 0
            self.stimuli[3].mv2pos((-500, -100))
            self.stimuli[3].size = 0
            self.zone_touched = False
            self.first_monkey = 0

        if cursor1.collides_with(self.stimuli[3]):
            sound(True)
            print("(RIGHT) responded first")
            self.write(data_file, 1, 1)
            pellet(side = 0, num = 1)
            pellet(side = 1, num = 1)
            bg.fill(white)
            refresh(screen)
            pygame.time.delay(ITI * 1000)
            self.new()

        if cursor2.collides_with(self.stimuli[2]):
            sound(True)
            print("(LEFT) responded first")
            self.write(data_file, 1, 2)
            pellet(side = 0, num = 1)
            pellet(side = 1, num = 1)
            bg.fill(white)
            refresh(screen)
            pygame.time.delay(ITI * 1000)
            self.new()

        
        # If the cursor is in the pull zone and its not moving, reset it to the start
            # This ensures monkey 1 is holding down the lever
        if cursor1.position[1] <= 445 and moveCursor(cursor1, side = 0, only = 'up') == False:
            #cursor1.mv2pos((225, 450))
            #CURSOR.MOVE(SIDE, XDIR, YDIR)
            cursor1.move(0, 0, 1)
            # This ensures monkey 2 is holding down the lever
        if cursor2.position[1] <= 445 and moveCursor(cursor2, side = 1, only = 'up') == False:
            #cursor2.mv2pos((800, 450))
            #CURSOR.MOVE(SIDE, XDIR, YDIR)
            cursor2.move(1, 0, 1)

        if self.time_delay() - delay >= duration:
            sound(False)
            self.write(data_file, 0, 0)
            bg.fill(white)
            refresh(screen)
            pygame.time.delay(ITI * 1000)
            self.new()


    def left_or_right(self):
        global button_positions
        if self.LorR == 1:
            return "left"
        elif self.LorR == 2:
            return "right"

    def write(self, file, correct, first_monkey):
        now = time.strftime('%H:%M:%S')
        session_type = "joint"
        time_taken = self.time_delay() - delay
        if first_monkey == 0:
            r = "none"
        elif first_monkey == 1:
            r = "right"
        elif first_monkey == 2:
            r = "left"
        data = [monkey_group, monkey[0], monkey[1], today, now, session_type, self.block, self.trial_number, self.trial_type[self.trial_within_block], time_taken, r, correct]

        
        writeLn(file, data)
        


# SETUP
# get parameters
varNames = ['full_screen', 'trials_per_block', 'blocks_per_session', 'ITI', 'duration', 'run_time', 'delay']
params = getParams(varNames)
globals().update(params)

full_screen = params['full_screen']
trials_per_block = params['trials_per_block']
blocks_per_session = params['blocks_per_session']
ITI = params['ITI']
duration = params['duration']
run_time = params['run_time']
delay = params['delay']

# set screen; define cursor; make left/right, top/bottom positions
screen = setScreen(full_screen)
pygame.display.set_caption('Bar Pull')
display_icon = pygame.image.load("Monkey_Icon.png")
pygame.display.set_icon(display_icon)
cursor1 = Box(circle = True, speed = 5)
cursor2 = Box(circle = True, speed = 5)
pos = [(150, 100), (874, 100), (150, 668), (874, 668)]

# create list of delays for a block (for pseudo-randomisation)
#delayList = delay * reps

# load file list
files = glob.glob('stimuli/*.png')

# start clock; stop program after [run_time] min x 60 seconds x 1000 ms
clock = pygame.time.Clock()
button_positions = [(120, 550), (920, 550)]

# save parameters and make data file with header

data_file = makeFileName('Barpull')
writeLn(data_file, ['group', 'monkey_left', 'monkey_right', 'date', 'time', 'session_type', 'block', 'trial_number', 'trial_type', 'response_time', 'first_responder' ,'correct_or_incorrect'])



# MAIN GAME LOOP: start first trial
trial = Trial()
trial.new()



while True:
    quitEscQ(data_file)  # quit on [Q] or [Esc]
    timer = (pygame.time.get_ticks() / 1000)
    SELECT1 = cursor1.collides_with_list(trial.stimuli)
    #print("SELECT 1: " + str(SELECT1))
    SELECT2 = cursor2.collides_with_list(trial.stimuli)
    #print("SELECT 2: " + str(SELECT2))

    #for testing have it quit after 200 trials
    #current_time = pygame.time.get_ticks()

    if trial.trial_number > 200:
        pygame.quit()
        sys.exit()

    bg.fill(white)  # clear screen
    clock.tick(fps)
    if trial.startphase == True:
        trial.start()
    elif trial.startphase == False:
        if trial.phase1 == True:
            trial.run_delay_phase()
        elif trial.phase2 == True:
            trial.run_trial()
        else:
            pygame.quit()
            
            
    #if trial.startphase:
    #    trial.start()
    #elif trial.phase1:
    #    trial.sample() # else, if sample is to be presented, run sample subroutine
    #else:
    #    trial.matching()  # else, run matching subroutine

    refresh(screen)
    #clock.tick(fps)  # caps frame rate
