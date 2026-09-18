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
        # Your code here

        ###########
        #States####
        ###########
        class RobotStates(Enum):
            SAFE_NAVIGATION = auto()
            STUPID_MONSTER_IN_PROXIMITY = auto()
            SMART_MONSTER_IN_PROXIMITY = auto()
            BOMB_SAFETY_PROTOCOL = auto()
           
        #Initialize robot into the Safe Navigation state
        ROBOT_STATE = RobotStates.SAFE_NAVIGATION

        ###########
        #StateEntry
        ###########

        def Enter_Safe_Navigation():
            ROBOT_STATE = RobotStates.SAFE_NAVIGATION
            pass
        def Enter_Stupid_Monster_In_Proximity():
            ROBOT_STATE = RobotStates.STUPID_MONSTER_IN_PROXIMITY
            pass
        def Enter_Smart_Monster_In_Proximity():
            ROBOT_STATE = RobotStates.SMART_MONSTER_IN_PROXIMITY
            pass
        def Enter_Bomb_Safety_Protocol():
            ROBOT_STATE = RobotStates.BOMB_SAFETY_PROTOCOL
            pass
        ###########
        #SearchAlgs
        ###########
        def BFS():
            
            pass

        ###########
        #Update####
        ###########
        def Update():
            if ROBOT_STATE == RobotStates.SAFE_NAVIGATION:
                #Call BFS
                pass
            if ROBOT_STATE == RobotStates.STUPID_MONSTER_IN_PROXIMITY:
                #Call Expectimax
                pass
            if ROBOT_STATE == RobotStates.SMART_MONSTER_IN_PROXIMITY:
                #Call minimax
                pass
            if ROBOT_STATE == RobotStates.BOMB_SAFETY_PROTOCOL:
                #Call BombSafetyProtocol 
                pass


        ###########
        #Checkers##
        ###########

        ###########
        #Handlers##
        ###########



        ###########
        #MainLoop##
        ###########
        pass
