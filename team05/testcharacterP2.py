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
            START = auto()
            CHECK_PATH = auto()
            CLEAR_PATH = auto()
            BLOCKED_PATH = auto()
            BOMB_EVADE = auto()
            EVADE_MONSTER = auto()
           
        #Initialize robot into the Start state
        ROBOT_STATE = RobotStates.START

        ###########
        #StateEntry
        ###########
        
        #Function to enter SAFE_Navigation State
        def Enter_Safe_Navigation():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.SAFE_NAVIGATION
            pass
          #Function to enter Monster_IN_PROXIMITY State
        def Enter_Monster_In_Proximity():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.MONSTER_IN_PROXIMITY
            pass
      
        ###########
        #SearchAlgs
        ###########

        #Finds All legal moves a character can make based on current position
        def find_neighbors(nodeX, nodeY):
            Current_Position = (nodeX,nodeY)
            All_Neighbors = []
            Invalid_Neighbors = []
            Valid_Neighbors = []
            #Add all characters surrounding nodes to list
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] - 1))
            #remove all nodes that are invalid
            for neighbor in All_Neighbors:
                if neighbor[0] < 0 or neighbor[1] < 0 or neighbor[0] >= wrld.width() or neighbor[1] >= wrld.height() or wrld.wall_at(neighbor[0], neighbor[1]):
                    Invalid_Neighbors.append(neighbor)
            Valid_Neighbors = [neighbor for neighbor in All_Neighbors if neighbor not in Invalid_Neighbors]
            return Valid_Neighbors
        
        #Breadth First Search Algorithm
        def BFS(S,T):
            #Initialize a queue with starting position and path to get there
            queue = [(S, [S])]
            #Keep track of visited nodes to avoid cycles
            visited = set()
            #loop over the queue until it's empty
            discovered = set([S])
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
                    for neighbor in find_neighbors(current_nodeX, current_nodeY):
                        if neighbor not in visited and neighbor not in discovered:
                            queue.append((neighbor, path + [neighbor]))
                            discovered.add(neighbor)
            return None
        
        #Follow the path given by BFS
        def follow_path(path):
            current_node = path[0]
            next_node = path[1]
                #Move to the next node in the path
            self.move(next_node[0] - current_node[0], next_node[1] - current_node[1])

            
        ###########
        #Update####
        ###########

        #This function decides logic based on current state
        def Update():
            if ROBOT_STATE == RobotStates.SAFE_NAVIGATION:
                pass
            if ROBOT_STATE == RobotStates.MONSTER_IN_PROXIMITY:
                pass

        ###########
        #Checkers##
        ###########

            
            
        ###########
        #Handlers##
        ###########

        ###########
        #RunCode###
        ###########
   
      # Test Commit