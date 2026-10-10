# This is necessary to find the main code
import os
import math
import random
import sys
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'Bomberman'
))
# Import necessary stuff
from entity import CharacterEntity
from events import Event
from colorama import Fore, Back
import pandas as pd

#import enum for RobotStates
from enum import Enum, auto

class RobotStates(Enum): #init states for the robot
    CHECK_PATH = auto()
    CLEAR_PATH = auto()
    BLOCKED_PATH = auto()
    BOMB_EVADE = auto()
    MONSTER_EVADE = auto()

class TestCharacter(CharacterEntity):

    # Use epsilon=0.0 for evaluation after training.
    epsilon = 0.15

    def choose_q_action(self, available_actions, q_function): # CHoosing action
        if not available_actions:
            return None
        if random.random() < self.epsilon: # If random number is less than epsilon, choose a random action (exploration)
            return random.choice(available_actions)

        scored_actions = [
            (action, q_function(action)) for action in available_actions  # Returns the possible actions and their corresponding Q-values
        ]
        best_Q = max(value for action, value in scored_actions) # Find the maximum Q-value among the scored actions
        best_actions = [
            action for action, value in scored_actions
            if math.isclose(value, best_Q, rel_tol=1e-12, abs_tol=1e-12)
            # Finds multiple actions with similar values, 1e-12 = 1E-10%. 
            # rel_tolerance finds ones that are 1E-10% similar
            # abs_tolerance finds ones that are 1E-12 similar
        ]
        return random.choice(best_actions) #picks a random action from the best actions

    def get_max_Q(self, available_actions, q_function):
        #gets the maximum Q-value from the available actions
        return max((q_function(action) for action in available_actions), default=0.0)

    def can_place_bomb(self, wrld):

        # Checks if a bomb can be placed at the character's current position
        # False if a bomb exists
        me = wrld.me(self)
        if wrld.bomb_at(me.x, me.y):
            return False
        # False if a bomb exists that was placed by this character
        # Checks if the name of the owner of any bomb in the world is the same as the name of this character
        # if no bomb matches the character's name, return True

        return not any(bomb.owner.name == self.name for bomb in wrld.bombs.values())

    def get_wall_distance(self, wrld, position):
        # Nearest wall along any of the four bomb-blast directions.
        board_size = max(wrld.width(), wrld.height())
        nearest = board_size
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for distance in range(1, board_size):
                x = position[0] + dx * distance
                y = position[1] + dy * distance
                if not (0 <= x < wrld.width() and 0 <= y < wrld.height()):
                    break
                if wrld.wall_at(x, y):
                    nearest = min(nearest, distance)
                    break
        return nearest

    def bomb_would_hit_wall(self, wrld, position):
        # Estimate usefulness from the current board. Entities can move
        # before detonation, so the actual wall-hit event supplies the reward.
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for distance in range(1, wrld.expl_range + 1):
                x = position[0] + dx * distance
                y = position[1] + dy * distance
                if not (0 <= x < wrld.width() and 0 <= y < wrld.height()):
                    break
                if wrld.exit_at(x, y) or wrld.bomb_at(x, y):
                    break
                if wrld.wall_at(x, y):
                    return True
                if wrld.monsters_at(x, y) or wrld.characters_at(x, y):
                    break
        return False


    def save_weights(self):
        # Collects the current updated weights and saves them to the csv for later
        rows = []

        for behavior, weights in self.Weights.items():
            for feature_name, weight in weights.items():
                rows.append({
                    "Behavior": behavior.name,
                    "Feature": feature_name,
                    "Weight": weight
                })

        saved_weights = pd.DataFrame(
            rows,
            columns=["Behavior", "Feature", "Weight"]
        )

        saved_weights.to_csv("weights.csv", index=False) 
        #Adds the weights to csv
        # =False prevents the index column being generated

    def update_previous_weights(self, reward, next_max_Q):
        alpha = 0.2 # Values for updates 
        gamma = 0.9

        error = ( # Error equation from lecture slides
            reward 
            + gamma * next_max_Q
            - self.previous_Q_value
        )

        previous_weights = self.Weights[self.previous_behavior] #pulls previous weights from csv

        for feature_name, feature_value in self.previous_features.items(): 
            previous_weights[feature_name] = (
                previous_weights.get(feature_name, 0.0)
                + alpha * error * feature_value
            )
        self.save_weights()  # Save the updated weights to CSV after updating


    def get_monster_distance(self, wrld, position):
        # Raw cell distance; the Q features remain normalized separately.
        return min(
            (max(abs(position[0] - monster.x), abs(position[1] - monster.y))
             for monsters in wrld.monsters.values() for monster in monsters),
            default=max(wrld.width(), wrld.height())
        )

    def in_bomb_danger(self, wrld, position):
        x, y = position
        if wrld.explosion_at(x, y):
            return True

        # Estimate a bomb's cross-shaped blast, respecting its range and
        # fixed blockers. Moving monsters/characters may change before it fires.
        for bomb in wrld.bombs.values():
            if position == (bomb.x, bomb.y):
                return True
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for distance in range(1, wrld.expl_range + 1):
                    check_x = bomb.x + dx * distance
                    check_y = bomb.y + dy * distance
                    if not (0 <= check_x < wrld.width() and
                            0 <= check_y < wrld.height()):
                        break
                    if (wrld.exit_at(check_x, check_y) or
                            wrld.bomb_at(check_x, check_y)):
                        break
                    if (check_x, check_y) == position:
                        return True
                    if wrld.wall_at(check_x, check_y):
                        break
        return False

    def remember_reward_inputs(self, wrld):
        me = wrld.me(self)
        self.previous_position = (me.x, me.y)
        self.previous_monster_distance = self.get_monster_distance(
            wrld, self.previous_position
        )
        self.previous_bomb_danger = self.in_bomb_danger(
            wrld, self.previous_position
        )

    def get_reward(self, wrld, died=False, reachedExit=False):
        if died:
            return -100.0
        if reachedExit:
            return 100.0

        me = wrld.me(self)
        current_position = (me.x, me.y)
        previous_exit_distance = max(
            abs(self.previous_position[0] - wrld.exitcell[0]),
            abs(self.previous_position[1] - wrld.exitcell[1])
        )
        current_exit_distance = max(
            abs(current_position[0] - wrld.exitcell[0]),
            abs(current_position[1] - wrld.exitcell[1])
        )
        exit_progress = previous_exit_distance - current_exit_distance
        current_monster_distance = self.get_monster_distance(
            wrld, current_position
        )
        monster_progress = (
            current_monster_distance - self.previous_monster_distance
        )
        current_bomb_danger = self.in_bomb_danger(wrld, current_position)
        reward = -0.1

        # This event identifies OUR bomb, even if behavior changed since
        # placement. The wall clears when its explosion expires in this engine.
        hit_wall = any(
            event.tpe == Event.BOMB_HIT_WALL and
            event.character.name == self.name
            for event in wrld.events
        )
        if hit_wall:
            reward += 15.0

        if self.previous_behavior == RobotStates.MONSTER_EVADE:
            reward += monster_progress + 0.5 * exit_progress
            if current_monster_distance == 0:
                reward -= 100.0
            elif current_monster_distance == 1:
                reward -= 20.0
            elif current_monster_distance == 2:
                reward -= 10.0

        elif self.previous_behavior == RobotStates.BOMB_EVADE:
            # Award one escape bonus when the position changes from danger
            # to safety; merely staying safe does not earn it again.
            if self.previous_bomb_danger and not current_bomb_danger:
                reward += 5.0
            elif current_bomb_danger:
                reward -= 3.0

        elif self.previous_behavior == RobotStates.BLOCKED_PATH:
            reward += 0.5 * exit_progress

        elif self.previous_behavior == RobotStates.CLEAR_PATH:
            reward += exit_progress

        return reward

    def clear_previous_action(self):
        for attribute in (
            'previous_features', 'previous_Q_value', 'previous_behavior',
            'previous_position', 'previous_monster_distance',
            'previous_bomb_danger'
        ):
            if hasattr(self, attribute):
                delattr(self, attribute)

    def done(self, wrld):
        # Death/exit removes the character before another do() call.
        died = any(
            (event.tpe == Event.BOMB_HIT_CHARACTER and
             event.other.name == self.name) or
            (event.tpe == Event.CHARACTER_KILLED_BY_MONSTER and
             event.character.name == self.name)
            for event in wrld.events
        )
        reached_exit = any(
            event.tpe == Event.CHARACTER_FOUND_EXIT and
            event.character.name == self.name
            for event in wrld.events
        )
        if hasattr(self, 'previous_features') and (died or reached_exit):
            reward = self.get_reward(wrld, died=died, reachedExit=reached_exit)
            self.update_previous_weights(reward, next_max_Q=0.0)
        self.clear_previous_action()

    def do(self, wrld):
        # Commands persist in this engine; start each turn stationary.
        self.move(0, 0)

        ###########
        #States####
        ###########
       
           
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

        
        if not hasattr(self, "Weights"):
            self.Weights = {
                RobotStates.BLOCKED_PATH: {
                    "distance_to_exit": 1.0,
                    "distance_to_wall": 1.0,
                    "bomb": 1.0,
                    "bomb_hits_wall": 0.0
                },

                RobotStates.BOMB_EVADE: {
                    "distance_to_exit": 1.0,
                    "distance_to_bomb": 1.0,
                    "bomb": 1.0,
                    "bomb_danger": 0.0,
                    "bomb_hits_wall": 0.0
                },

                RobotStates.MONSTER_EVADE: {
                    "distance_to_exit": 1.0,
                    "distance_to_monster": 1.0,
                    "bomb": 1.0
                }
            }

            if os.path.exists("weights.csv"):
                saved_weights = pd.read_csv("weights.csv")

                for _, row in saved_weights.iterrows():
                    behavior = RobotStates[row["Behavior"]]
                    feature = row["Feature"]

                    self.Weights[behavior][feature] = float(
                        row["Weight"]
                    )
        
            

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
        
        #########################
        #Apr.Q-Learning Equations
        #########################
          #returns a list of available actions for the character to take when the path is blocked: move, wait, or bomb
        def get_blocked_path_actions():
            current_position = (wrld.me(self).x, wrld.me(self).y)
            available_actions = []

            for neighbor in find_neighbors(
                current_position[0], current_position[1]
            ):
                available_actions.append(
                    ("MOVE", neighbor[0], neighbor[1])
                )

            available_actions.append(
                ("WAIT", current_position[0], current_position[1])
            )

            if self.can_place_bomb(wrld):
                available_actions.append(
                    ("BOMB", current_position[0], current_position[1])
                )

            return available_actions



        def get_blocked_path_features(action):
            action_type, action_x, action_y = action
            board_size = max(wrld.width(), wrld.height())
            distance_to_exit = max(
                abs(action_x - wrld.exitcell[0]),
                abs(action_y - wrld.exitcell[1])
            )
            distance_to_wall = self.get_wall_distance(wrld, (action_x, action_y))
            return {
                "distance_to_exit": distance_to_exit / board_size,
                "distance_to_wall": distance_to_wall / board_size,
                "bomb": 1.0 if action_type == "BOMB" else 0.0,
                "bomb_hits_wall": float(
                    action_type == "BOMB" and
                    self.bomb_would_hit_wall(wrld, (action_x, action_y))
                )
            }

        def get_blocked_path_Q_value(action):
        
                features = get_blocked_path_features(action)
                blocked_path_weights = self.Weights[RobotStates.BLOCKED_PATH]
                Q_value =0.0
                for feature_name, feature_value in features.items():
                    weight = blocked_path_weights.get(feature_name, 0.0)
                    Q_value += weight * feature_value
                return Q_value

        def choose_blocked_path_action():
            return self.choose_q_action(
                get_blocked_path_actions(), get_blocked_path_Q_value
            )

        def get_bomb_actions():
            current_position = (wrld.me(self).x, wrld.me(self).y)
            available_actions = []

            for neighbor in find_neighbors(
                current_position[0], current_position[1]
            ):
                available_actions.append(
                    ("MOVE", neighbor[0], neighbor[1])
                )

            available_actions.append(
                ("WAIT", current_position[0], current_position[1])
            )

            if self.can_place_bomb(wrld):
                available_actions.append(
                    ("BOMB", current_position[0], current_position[1])
                )

            return available_actions

        def choose_bomb_action(bombs):
            return self.choose_q_action(
                get_bomb_actions(), lambda action: get_bomb_Q_value(action, bombs)
            )

        def get_bomb_features(action, bombs):
            action_type, action_x, action_y = action

            board_size = max(wrld.width(), wrld.height())

            distance_to_exit = max(
                abs(action_x - wrld.exitcell[0]),
                abs(action_y - wrld.exitcell[1])
            )

            distance_to_bomb = board_size

            for current_bomb in bombs.values():
                distance = max(
                    abs(action_x - current_bomb.x),
                    abs(action_y - current_bomb.y)
                )

                distance_to_bomb = min(
                    distance_to_bomb, distance
                )

            return {
                "distance_to_exit": distance_to_exit / board_size,
                "distance_to_bomb": distance_to_bomb / board_size,
                "bomb": 1.0 if action_type == "BOMB" else 0.0,
                "bomb_danger": float(
                    action_type == "BOMB" or
                    self.in_bomb_danger(wrld, (action_x, action_y))
                ),
                "bomb_hits_wall": float(
                    action_type == "BOMB" and
                    self.bomb_would_hit_wall(wrld, (action_x, action_y))
                )
            }
        

        def get_bomb_Q_value(action, bomb):
            features = get_bomb_features(action, bomb)
            bomb_weights = self.Weights[RobotStates.BOMB_EVADE]

            Q_value = 0.0

            for feature_name, feature_value in features.items():
                weight = bomb_weights.get(feature_name, 0.0)
                Q_value += weight * feature_value

            return Q_value
    
          
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
        
        def monster_evade_Q_value( action):
 
            features = monster_evade_features(action)
            monster_weights = self.Weights[RobotStates.MONSTER_EVADE]

            Q_value = 0.0

            for feature_name, feature_value in features.items():
                weight = monster_weights.get(feature_name, 0.0)
                Q_value += weight * feature_value

            return Q_value

        def choose_monster_evade_action():
            return self.choose_q_action(
                monster_evade_actions(), monster_evade_Q_value
            )

        
        ##################
        #Q Values in CSV##
        ##################

        def QValue_archive(behavior, action, Q_value):
            row = pd.DataFrame([{
                "State": behavior.name,
                "Action": action,
                "Q_Value": Q_value
            }])

            file_exists = os.path.exists("q_values.csv")

            row.to_csv(
                "q_values.csv",
                mode="a",
                header=not file_exists,
                index=False
            )


        def get_next_state_Q_value_monsterEvade():
            available_actions = monster_evade_actions()
            best_Q_value = float("-inf")

            for next_action in available_actions:
                Q_value = monster_evade_Q_value(next_action)

                if Q_value > best_Q_value:
                    best_Q_value = Q_value

            if best_Q_value == float("-inf"):
                return 0.0

            return best_Q_value

        ###################################
        #ApproximateQLearningAct&Update####
        ###################################

        def act_on_q_value_blocked_path():
                action = choose_blocked_path_action()
                if action is None:
                    return
                self.previous_features = get_blocked_path_features(action).copy()
                self.previous_Q_value = get_blocked_path_Q_value(action)
                self.previous_behavior = RobotStates.BLOCKED_PATH
                self.remember_reward_inputs(wrld)

                QValue_archive(
                    self.previous_behavior,
                    action,
                    self.previous_Q_value
                                     )

                if action[0] == "MOVE":
                    self.move(action[1] - wrld.me(self).x, action[2] - wrld.me(self).y)
                elif action[0] == "WAIT":
                    self.move(0, 0)
                elif action[0] == "BOMB":
                    self.place_bomb()
        def act_on_q_value_evade_monster():
                        action = choose_monster_evade_action()
                        if action is None:
                            return
                        self.previous_features = monster_evade_features(action).copy()
                        self.previous_Q_value = monster_evade_Q_value(action)
                        self.previous_behavior = RobotStates.MONSTER_EVADE
                        self.remember_reward_inputs(wrld)
                        QValue_archive(
                            self.previous_behavior,
                            action,
                            self.previous_Q_value
                                        )
                        
                        if action[0] == "MOVE":
                            self.move(action[1] - wrld.me(self).x, action[2] - wrld.me(self).y)
                        elif action[0] == "WAIT":
                            self.move(0, 0)
                        elif action[0] == "BOMB":
                            self.place_bomb()
        def act_on_q_value_evade_bomb():
            action = choose_bomb_action(wrld.bombs)

            if action is None:
                return

            self.previous_features = get_bomb_features(
                action, wrld.bombs
            ).copy()

            self.previous_Q_value = get_bomb_Q_value(
                action, wrld.bombs
            )

            self.previous_behavior = RobotStates.BOMB_EVADE
            self.remember_reward_inputs(wrld)
            QValue_archive(
                self.previous_behavior,
                action,
                self.previous_Q_value
            )
            if action[0] == "MOVE":
                self.move(
                    action[1] - wrld.me(self).x,
                    action[2] - wrld.me(self).y
                )
            elif action[0] == "WAIT":
                self.move(0, 0)
            elif action[0] == "BOMB":
                self.place_bomb()    

                       

            
        ###########
        #Update####
        ###########

        #This function decides logic based on current state
        def Update():
            if hasattr(self, "previous_features"):
                if wrld.time <= 0:
                    next_max_Q = 0.0
                elif ROBOT_STATE == RobotStates.BLOCKED_PATH:
                    next_max_Q = self.get_max_Q(
                        get_blocked_path_actions(), get_blocked_path_Q_value
                    )
                elif ROBOT_STATE == RobotStates.BOMB_EVADE:
                    next_max_Q = self.get_max_Q(
                        get_bomb_actions(),
                        lambda action: get_bomb_Q_value(action, wrld.bombs)
                    )
                elif ROBOT_STATE == RobotStates.MONSTER_EVADE:
                    next_max_Q = self.get_max_Q(
                        monster_evade_actions(), monster_evade_Q_value
                    )
                else:
                    # CLEAR_PATH uses BFS rather than a learned Q model.
                    next_max_Q = 0.0

                reward = self.get_reward(wrld)
                self.update_previous_weights(reward, next_max_Q)
                self.clear_previous_action()

            if wrld.time <= 0:
                return
            if ROBOT_STATE == RobotStates.CLEAR_PATH:
                path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
                if path is not None and len(path) > 1:
                    follow_path(path)
            elif ROBOT_STATE == RobotStates.BLOCKED_PATH:
                act_on_q_value_blocked_path()
            elif ROBOT_STATE == RobotStates.BOMB_EVADE:
                act_on_q_value_evade_bomb()
            elif ROBOT_STATE == RobotStates.MONSTER_EVADE:
                act_on_q_value_evade_monster()

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
        if check_bomb_placed() or check_bomb_exploded():
             handle_check_bomb_placed()

        elif check_monster_in_path():
            handle_check_monster_in_path()

        elif check_path_clear():
            handle_check_path_clear()

        else:
            handle_check_path_blocked()
      # Test Commit 
