# This is necessary to find the main code
import sys
sys.path.insert(0, '../bomberman')
# Import necessary stuff
from entity import CharacterEntity
from colorama import Fore, Back

#import enum for RobotStates
from enum import Enum, auto

class TestCharacter(CharacterEntity):

    def do(self, wrld):
        pass

    #Test commit