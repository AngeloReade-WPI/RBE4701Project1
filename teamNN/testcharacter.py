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
        def find_neighbors(character):
            #Get Current Position of Robot
            Current_Position = (wrld.me(character).x, wrld.me(character).y)
            All_Neighbors = []
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] - 1))
            for neighbor in All_Neighbors:
                if neighbor[0] < 0 or neighbor[1] < 0 or neighbor[0] >= wrld.width() or neighbor[1] >= wrld.height():
                    All_Neighbors.remove(neighbor)
                if wrld.wall_at(neighbor[0], neighbor[1]):
                    All_Neighbors.remove(neighbor)
            return All_Neighbors
        def BFS(G,S,T):
            #Initialize a queue with starting position and path to get there
            queue = [(S, [S])]
            #Keep track of visited nodes to avoid cycles
            visited = set()
            #loop over the queue until it's empty
            while queue:
                #get the first item in the queue
                ((current_nodeX, current_nodeY), path) = queue.pop(0)
                #if the current node is the target, return the path
                if (current_nodeX, current_nodeY) == T:
                    return path
                #if the current node has not been visited yet
                if (current_nodeX, current_nodeY) not in visited:
                    #mark the current node as visited
                    visited.add((current_nodeX, current_nodeY))
                    #add all unvisited neighbors to the queue
                    for neighbor in G.neighbors((current_nodeX, current_nodeY)):
                        if neighbor not in visited:
                            queue.append((neighbor, path + [neighbor]))
            
            return None

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
        test = find_neighbors(self)
        print(test)
        pass
        

        