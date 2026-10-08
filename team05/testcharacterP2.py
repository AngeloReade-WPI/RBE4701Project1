# This is necessary to find the main code
from pyexpat import features
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
            CHECK_PATH = auto()
            CLEAR_PATH = auto()
            BLOCKED_PATH = auto()
            BOMB_EVADE = auto()
            MONSTER_EVADE = auto()
           
        #Initialize robot into the Start state
        ROBOT_STATE = RobotStates.CHECK_PATH

        ###########
        #StateEntry
        ###########
        
        #Function to enter CHECK_PATH State
        def Enter_CHECK_PATH():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.CHECK_PATH
            pass
        #Function to enter CLEAR_PATH State
        def Enter_CLEAR_PATH():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.CLEAR_PATH
            pass
        #Function to enter BLOCKED_PATH State
        def Enter_BLOCKED_PATH():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.BLOCKED_PATH
            pass
        #Function to enter BOMB_EVADE State
        def Enter_BOMB_EVADE():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.BOMB_EVADE
            pass
        #Function to enter MONSTER_EVADE State
        def Enter_MONSTER_EVADE():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.MONSTER_EVADE
            pass

        
        
        ###########
        #Weights##
        ###########

        self.Weights = {
            RobotStates.BLOCKED_PATH: {
                distance_to_exit: 1.0,
                distance_to_wall: 1.0,
                bomb: 1.0
            },

            RobotStates.BOMB_EVADE: {
                #TODO: Add weights for BOMB_EVADE state
                distance_to_exit: 1.0,
                distance_to_bomb: 1.0,
                bomb: 1.0
            },

            RobotStates.MONSTER_EVADE: {
                #TODO: Add weights for MONSTER_EVADE state
                distance_to_exit: 1.0,
                distance_to_monster: 1.0,
                bomb: 1.0
            }
        }
            

        ###########
        #HelpFuncs#
        ###########

        #returns a list of monsters in the world
        def get_monster_list():
            monster_list = []
            for monsters in wrld.monsters.values():
                for m in monsters:
                    monster_list.append(m)
            return monster_list

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

        #Follow the path given by BFS
        def follow_path(path):
            current_node = path[0]
            next_node = path[1]
                #Move to the next node in the path
            self.move(next_node[0] - current_node[0], next_node[1] - current_node[1])

        
        ###########
        #SearchAlgs
        ###########

       
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
        
        ###############
        #Apr.Q-Learning
        ###############

        def get_bomb_actions():
            current_position = (wrld.me(self).x, wrld.me(self).y)
            available_actions = []

            for neighbor in find_neighbors(current_position[0], current_position[1]):
                available_actions.append(("MOVE", neighbor[0], neighbor[1]))
                available_actions.append(("WAIT", current_position[0], current_position[1]))
                if not wrld.bomb_at(current_position[0], current_position[1]):
                    available_actions.append(("BOMB", current_position[0], current_position[1]))

            return available_actions
            
        def get_bomb_features(action, bomb):
            action_type = action[0]
            action_x = action[1]
            action_y = action[2]

            

            board_size = max(wrld.width(), wrld.height())

            # Chebyshev distance because diagonal movement is allowed
            distance_to_exit = max(
                abs(action_x - wrld.exitcell[0]),
                abs(action_y - wrld.exitcell[1])
            )

            # Default if no wall is found
            distance_to_bomb = board_size

            # Coords for where bomb was placed 
            for i in bomb:
                bombx = bomb[i].x
                bomby = bomb[i].y
                # Calculate distance to the bomb
                distance_to_bomb = max(
                    abs(action_x - bombx),
                    abs(action_y - bomby))
                # for x in [-1, -2, -3, -4, -5, 1, 2, 3, 4, 5]:
                #     for y in [-1, -2, -3, -4, -5, 1, 2, 3, 4, 5]:
                #         distance_to_explosion = distance_to_explosion.append((distance_to_bomb.x+x, distance_to_bomb.y+y))
            

            if action_type == "BOMB":
                bomb = 1.0
                # self.bomb.append((action_x, action_y))
            else:
                bomb = 0.0


            features = {
                "distance_to_exit": distance_to_exit / board_size,
                "distance_to_bomb": distance_to_bomb / board_size,
                # "distance_to_explosion": distance_to_explosion / board_size,
                "bomb": bomb
            }

            return features
        
        def get_bomb_Q_value(weight, action, bomb):
            features = get_bomb_features(action, bomb)
            bomb_weights = self.Weights[RobotStates.BOMB_EVADE]
            Q_value = 0.0
            for feature_name, feature_value in features.items():
                weight = bomb_weights.get(feature_name, 0.0)
                Q_value += weight * feature_value

            return Q_value
        
        def choose_bomb_action(bomb):
            available_actions = get_bomb_actions()
            best_action = None
            best_Q_value = float('-inf')
            for action in available_actions:
                Q_value = get_bomb_Q_value(action, bomb)
                if Q_value > best_Q_value:
                    best_Q_value = Q_value
                    best_action = action
            return best_action
        
        #returns a list of available actions for the character to take when the path is blocked: move, wait, or bomb
        def get_blocked_path_actions():
            current_position = (wrld.me(self).x, wrld.me(self).y)
            available_actions = []

            for neighbor in find_neighbors(current_position[0], current_position[1]):
                available_actions.append("MOVE", neighbor[0], neighbor[1])
                available_actions.append("WAIT", current_position[0], current_position[1])
                available_actions.append("BOMB", current_position[0], current_position[1])
            return available_actions

        
        def get_blocked_path_features(action):
            action_type = action[0]
            action_x = action[1]
            action_y = action[2]

            board_size = max(wrld.width(), wrld.height())

            # Chebyshev distance because diagonal movement is allowed
            distance_to_exit = max(
                abs(action_x - wrld.exitcell[0]),
                abs(action_y - wrld.exitcell[1])
            )

            # Default if no wall is found
            distance_to_wall = board_size

            # Look downward from the proposed action
            for i in range(1, wrld.height()):
                check_y = action_y + i

                # Check bounds before calling wall_at()
                if check_y >= wrld.height():
                    break

                if wrld.wall_at(action_x, check_y):
                    distance_to_wall = i
                    break

            if action_type == "BOMB":
                bomb = 1.0
                self.bomb.append((action_x, action_y))
            else:
                bomb = 0.0

            features = {
                "distance_to_exit": distance_to_exit / board_size,
                "distance_to_wall": distance_to_wall / board_size,
                "bomb": bomb
            }

            return features

            
        def get_blocked_path_Q_value(action):
 
            features = get_blocked_path_features(action)
            blocked_path_weights = self.Weights[RobotStates.BLOCKED_PATH]
            Q_value =0.0
            for feature_name, feature_value in features.items():
                weight = blocked_path_weights.get(feature_name, 0.0)
                Q_value += weight * feature_value
            return Q_value

            
        def choose_blocked_path_action():
            available_actions = get_blocked_path_actions()
            best_action = None
            best_Q_value = float('-inf')
            for action in available_actions:
                Q_value = get_blocked_path_Q_value(action)
                if Q_value > best_Q_value:
                    best_Q_value = Q_value
                    best_action = action
            return best_action
          
        # returns a list of available actions for the character to evade a monster
        def monster_evade_actions():
            current_position = (wrld.me(self).x, wrld.me(self).y)
            available_actions = []
            # Appends all possible movement actions from neighboring cells to the available_actions list
            for neighbor in find_neighbors(current_position[0], current_position[1]):
                available_actions.append(("MOVE", neighbor[0], neighbor[1]))
                #moved outside for loop
            available_actions.append(("WAIT", current_position[0], current_position[1]))
            return available_actions

        def monster_evade_features(action):
            action_type = action[0]
            action_x = action[1]
            action_y = action[2]

            board_size = max(wrld.width(), wrld.height())
            distance_to_monster = board_size

            for monster in get_monster_list():
                distance = max(abs(action_x - monster.x),abs(action_y - monster.y))

                if distance < distance_to_monster:
                    distance_to_monster = distance
        
            distance_to_exit = max(abs(action_x - wrld.exitcell[0]),abs(action_y - wrld.exitcell[1]))
        
            features = {
            "distance_to_monster": distance_to_monster / board_size,
            "distance_to_exit": distance_to_exit / board_size
            }
            return features
        
        def monster_evade_Q_value(self, Weights, action):
 
            features = monster_evade_features(action)
            monster_evade_weights = self.Weights[RobotStates.MONSTER_EVADE]
            Q_value =0.0
            for feature_name, feature_value in features.items():
                weight = monster_evade_weights.get(feature_name, 0.0)
                Q_value += weight * feature_value
            return Q_value

        def choose_monster_evade_action():
            actions = monster_evade_actions()

            best_action = None
            best_Q_value = float("-inf")

            for action in actions:
                Q_value = monster_evade_Q_value(action, Weights)

                if Q_value > best_Q_value:
                    best_Q_value = Q_value
                    best_action = action
            return best_action  


        
        


        ###########
        #Update####
        ###########

        #This function decides logic based on current state
        def Update():
            if ROBOT_STATE == RobotStates.CHECK_PATH:
                pass
            if ROBOT_STATE == RobotStates.CLEAR_PATH:
                pass
            if ROBOT_STATE == RobotStates.BLOCKED_PATH:
                pass
            if ROBOT_STATE == RobotStates.BOMB_EVADE:
                pass
            if ROBOT_STATE == RobotStates.MONSTER_EVADE:
                pass

        ###########
        #Checkers##
        ###########

        #Return true if path is clear of walls. 
        def check_path_clear():
            purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
            if purposed_path is not None:
                return True

        #Return true if path is blocked by walls. 
        def check_path_blocked():
            purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
            if purposed_path is None:
                return True

        # If there is a direct path to the monster in front of the character, return true.
        def check_monster_in_path():
            monster_list = get_monster_list()
            for monster in monster_list:
                purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), (monster.x, monster.y))
                if purposed_path is not None:
                    return True
            return False

         # Return true if there is a bomb present in the world. 
        def check_bomb_placed():
            if len(wrld.bombs) > 0:
                return True

        # If there is an explosion in the world, return true. 
        def check_bomb_exploded():
            if len(wrld.explosions) > 0:
                return True
            pass
        
        ###########
        #Handlers##
        ###########
        def handle_check_path_clear():
            Enter_CLEAR_PATH()
            Update()
            pass
        def handle_check_path_blocked():
            Enter_BLOCKED_PATH()
            Update()
            pass
        def handle_check_monster_in_path():
            Enter_MONSTER_EVADE()
            Update()
            pass
        def handle_check_bomb_placed():
            Enter_BOMB_EVADE()
            Update()
            pass
        def handle_check_bomb_exploded():
            Enter_CHECK_PATH()
            Update()
            pass    

        ###########
        #RunCode###
        ###########
   
      # Test Commit