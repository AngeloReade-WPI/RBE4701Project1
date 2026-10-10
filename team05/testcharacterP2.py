# This is necessary to find the main code
import os
import math
import heapq
from collections import deque
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

class RobotStates(Enum):
    CHECK_PATH = auto()
    CLEAR_PATH = auto()
    BLOCKED_PATH = auto()
    BOMB_EVADE = auto()
    MONSTER_EVADE = auto()

class TestCharacter(CharacterEntity):


    training = True

    @staticmethod
    def grid_neighbors(wrld, position):
        x, y = position
        for dx, dy in ((1, 0), (1, 1), (1, -1), (0, 1),
                       (0, -1), (-1, 0), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < wrld.width() and 0 <= ny < wrld.height():
                yield nx, ny

    def route_cost_map(self, wrld, walls):
        # Dijkstra: minimize walls crossed first, then number of moves.
        # This supplies features; it does not choose the agent's actions.
        costs = {wrld.exitcell: (0, 0)}
        queue = [(0, 0, wrld.exitcell)]
        while queue:
            wall_count, steps, position = heapq.heappop(queue)
            if costs[position] != (wall_count, steps):
                continue
            for neighbor in self.grid_neighbors(wrld, position):
                # Reverse search: forward movement from neighbor enters position.
                new_cost = (wall_count + int(position in walls), steps + 1)
                if new_cost < costs.get(neighbor, (float('inf'), float('inf'))):
                    costs[neighbor] = new_cost
                    heapq.heappush(queue, (*new_cost, neighbor))
        return costs

    def walk_distances(self, wrld, starts, walls):
        distances = {position: 0 for position in starts if position not in walls}
        queue = deque(distances)
        while queue:
            position = queue.popleft()
            for neighbor in self.grid_neighbors(wrld, position):
                if neighbor not in walls and neighbor not in distances:
                    distances[neighbor] = distances[position] + 1
                    queue.append(neighbor)
        return distances

    def predicted_wall_hits(self, wrld, position, walls):
        hits = set()
        # Static geometry estimate. Moving entities may change before detonation.
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            for distance in range(1, wrld.expl_range + 1):
                cell = (position[0] + dx * distance, position[1] + dy * distance)
                if not (0 <= cell[0] < wrld.width() and 0 <= cell[1] < wrld.height()):
                    break
                if cell == wrld.exitcell or wrld.bomb_at(*cell):
                    break
                if cell in walls:
                    hits.add(cell)
                    break
        return hits

    def get_navigation_info(self, wrld, start):
        walls = {
            (x, y) for x in range(wrld.width()) for y in range(wrld.height())
            if wrld.wall_at(x, y)
        }
        cache_key = (
            wrld.width(), wrld.height(), wrld.exitcell, frozenset(walls),
            frozenset((bomb.x, bomb.y) for bomb in wrld.bombs.values()),
            frozenset((explosion.x, explosion.y) for explosion in wrld.explosions.values())
        )
        cached = getattr(self, '_navigation_cache', None)
        if (getattr(self, '_navigation_cache_key', None) == cache_key and
                cached is not None and start in cached['reachable']):
            return cached
        costs = self.route_cost_map(wrld, walls)
        reachable = self.walk_distances(wrld, [start], walls)
        useful_positions = set()
        best_remaining_walls = costs[start][0]
        simulated_costs = {}
        for position in reachable:
            if wrld.bomb_at(*position) or wrld.explosion_at(*position):
                continue
            hits = frozenset(self.predicted_wall_hits(wrld, position, walls))
            if not hits:
                continue
            if hits not in simulated_costs:
                simulated_costs[hits] = self.route_cost_map(wrld, walls - hits)[start][0]
            remaining_walls = simulated_costs[hits]
            if remaining_walls < best_remaining_walls:
                best_remaining_walls = remaining_walls
                useful_positions = {position}
            elif remaining_walls == best_remaining_walls and remaining_walls < costs[start][0]:
                useful_positions.add(position)

        # If the exit is reachable, route features point toward the exit.
        # Otherwise they point to reachable sites that remove the next barrier.
        targets = {wrld.exitcell} if costs[start][0] == 0 else useful_positions
        distances = self.walk_distances(wrld, targets, walls)
        info = {
            'walls': walls,
            'route_costs': costs,
            'targets': targets,
            'useful_bomb_positions': useful_positions,
            'target_distances': distances,
            'reachable': set(reachable),
            'distance_scale': max(1, wrld.width() * wrld.height())
        }
        self._navigation_cache_key = cache_key
        self._navigation_cache = info
        return info

    def route_action_features(self, wrld, action):
        action_type, x, y = action
        info = self.navigation_info
        me = wrld.me(self)
        distances = info['target_distances']
        default_distance = info['distance_scale']
        previous_distance = distances.get((me.x, me.y), default_distance)
        action_distance = distances.get((x, y), default_distance)
        return {
            'bias': 1.0,
            'distance_to_target': action_distance / default_distance,
            'target_progress': float(previous_distance - action_distance),
            # Distinguish waiting/sideways wandering at a useful site from
            # taking the bombing action that can actually open the route.
            'idle_at_target': float(
                action_type != 'BOMB' and previous_distance == 0 and action_distance == 0
            ),
            'place_bomb': float(action_type == 'BOMB'),
            'bomb_opens_route': float(
                action_type == 'BOMB' and (x, y) in info['useful_bomb_positions']
            )
        }

    def collect_removed_own_walls(self, wrld):
        # This engine clears walls when explosions expire, not at wall-hit time.
        # Track our wall-hit cells until that actual removal occurs.
        pending = getattr(self, 'pending_own_wall_hits', set())
        for explosion in wrld.explosions.values():
            cell = (explosion.x, explosion.y)
            if explosion.owner.name == self.name and wrld.wall_at(*cell):
                pending.add(cell)
        removed = {cell for cell in pending if not wrld.wall_at(*cell)}
        self.pending_own_wall_hits = pending - removed
        return removed

    # Use training=False for evaluation with frozen weights and no exploration.
    epsilon = 0.1

    def choose_q_action(self, available_actions, q_function):
        if not available_actions:
            return None
        if self.training and random.random() < self.epsilon:
            return random.choice(available_actions)

        scored_actions = [
            (action, q_function(action)) for action in available_actions
        ]
        best_Q = max(value for action, value in scored_actions)
        best_actions = [
            action for action, value in scored_actions
            if math.isclose(value, best_Q, rel_tol=1e-12, abs_tol=1e-12)
        ]
        return random.choice(best_actions)

    def get_max_Q(self, available_actions, q_function):
        # The training target must be a maximum, even during exploration.
        return max((q_function(action) for action in available_actions), default=0.0)

    def can_place_bomb(self, wrld):
        me = wrld.me(self)
        if wrld.bomb_at(me.x, me.y):
            return False
        return not any(bomb.owner.name == self.name for bomb in wrld.bombs.values())

    def filter_immediate_blast_actions(self, wrld, actions):
        # Keep exploration from stepping into an active explosion or a blast
        # about to fire. Bombs update before characters move in this engine,
        # so a cell must be cleared one decision before a timer reaches zero.
        safe_actions = []
        for action in actions:
            position = (action[1], action[2])
            if wrld.explosion_at(*position):
                continue
            danger = False
            for bomb in wrld.bombs.values():
                if bomb.timer > 1:
                    continue
                if position == (bomb.x, bomb.y):
                    danger = True
                    break
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    for distance in range(1, wrld.expl_range + 1):
                        cell = (bomb.x + dx * distance, bomb.y + dy * distance)
                        if not (0 <= cell[0] < wrld.width() and 0 <= cell[1] < wrld.height()):
                            break
                        if cell == wrld.exitcell or wrld.bomb_at(*cell):
                            break
                        if cell == position:
                            danger = True
                            break
                        if wrld.wall_at(*cell):
                            break
                    if danger:
                        break
                if danger:
                    break
            if not danger:
                safe_actions.append(action)
        # If no escape exists, preserve available actions so the terminal
        # outcome still updates the pending learned action normally.
        return self.filter_monster_actions(wrld, safe_actions or actions)

    def filter_monster_actions(self, wrld, actions):
        # Monsters move before the character, and hitting its old position
        # is fatal even if it moves away. Leave two monster steps of clearance:
        # this turn's move and the move before our following action executes.
        threatened = set()
        for monsters in wrld.monsters.values():
            for monster in monsters:
                position = (monster.x, monster.y)
                reachable = {position}
                for _ in range(2):
                    reachable.update(cell for origin in tuple(reachable)
                                     for cell in self.grid_neighbors(wrld, origin)
                                     if not wrld.wall_at(*cell))
                threatened.update(reachable)
        safe = [action for action in actions
                if (action[1], action[2]) not in threatened]
        if safe or not actions:
            return safe
        # No collision-free option: retain the greatest separation available.
        distances = [self.get_monster_distance(wrld, (a[1], a[2]))
                     for a in actions]
        best = max(distances)
        return [a for a, distance in zip(actions, distances) if distance == best]

    def monster_action_features(self, wrld, action):
        me = wrld.me(self)
        position = (action[1], action[2])
        exit_x, exit_y = wrld.exitcell
        before = max(abs(me.x - exit_x), abs(me.y - exit_y))
        after = max(abs(position[0] - exit_x), abs(position[1] - exit_y))
        distance = self.get_monster_distance(wrld, position)
        previous_distance = self.get_monster_distance(wrld, (me.x, me.y))
        return {
            'bias': 1.0,
            'exit_progress': float(before - after),
            'monster_progress': float(distance - previous_distance),
            'monster_risk': 1.0 / (1.0 + distance)
        }




    def save_weights(self):
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

    def update_previous_weights(self, reward, next_max_Q):
        if not self.training:
            return
        alpha = 0.1
        gamma = 0.9

        error = (
            reward
            + gamma * next_max_Q
            - self.previous_Q_value
        )

        previous_weights = self.Weights[self.previous_behavior]

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
        self.previous_monster_distance = self.get_monster_distance(wrld, self.previous_position)
        self.previous_bomb_danger = self.in_bomb_danger(wrld, self.previous_position)
        self.previous_navigation = self.navigation_info

    def get_reward(self, wrld, died=False, reachedExit=False):
        if died:
            return -100.0
        if reachedExit:
            return 100.0

        me = wrld.me(self)
        current_position = (me.x, me.y)
        current_monster_distance = self.get_monster_distance(wrld, current_position)
        current_bomb_danger = self.in_bomb_danger(wrld, current_position)
        previous_info = self.previous_navigation
        current_info = self.navigation_info
        reward = -0.1

        removed = self.collect_removed_own_walls(wrld)
        if removed:
            # Compare from the SAME position so movement is not counted as demolition.
            # Undo just our removals to isolate their contribution from other bombs.
            without_our_removals = self.route_cost_map(wrld, current_info['walls'] | removed)
            before = without_our_removals[self.previous_position]
            after = current_info['route_costs'][self.previous_position]
            barriers_removed = before[0] - after[0]
            if barriers_removed > 0:
                reward += 15.0 * barriers_removed

        if self.previous_behavior == RobotStates.MONSTER_EVADE:
            previous_exit_distance = max(
                abs(self.previous_position[0] - wrld.exitcell[0]),
                abs(self.previous_position[1] - wrld.exitcell[1])
            )
            current_exit_distance = max(
                abs(current_position[0] - wrld.exitcell[0]),
                abs(current_position[1] - wrld.exitcell[1])
            )
            monster_progress = current_monster_distance - self.previous_monster_distance
            reward += monster_progress + 0.5 * (previous_exit_distance - current_exit_distance)
            if current_monster_distance == 0:
                reward -= 100.0
            elif current_monster_distance == 1:
                reward -= 20.0
            elif current_monster_distance == 2:
                reward -= 10.0

        elif self.previous_behavior == RobotStates.BOMB_EVADE:
            # No escape bonus: cycling into danger and back out cannot earn reward.
            if current_bomb_danger:
                reward -= 3.0

        elif self.previous_behavior == RobotStates.BLOCKED_PATH:
            if previous_info['walls'] == current_info['walls']:
                # Same target set for both positions; moving back cancels progress.
                distances = previous_info['target_distances']
                if self.previous_position in distances and current_position in distances:
                    reward += distances[self.previous_position] - distances[current_position]
            if self.previous_features.get('place_bomb', 0.0):
                # A small action cost, not an unverified reward for predicted wall hits.
                reward -= 0.5

        return reward

    def clear_previous_action(self):
        for attribute in (
            'previous_features', 'previous_Q_value', 'previous_behavior',
            'previous_position', 'previous_monster_distance',
            'previous_bomb_danger', 'previous_navigation'
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
        self.pending_own_wall_hits = set()

    def do(self, wrld):
        # Commands persist in this engine; start each turn stationary.
        self.move(0, 0)
        me = wrld.me(self)
        if me is None:
            return
        self.navigation_info = self.get_navigation_info(wrld, (me.x, me.y))

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
                    "bias": 0.0,
                    "distance_to_target": -1.0,
                    "target_progress": 1.0,
                    "idle_at_target": 0.0,
                    "place_bomb": -0.5,
                    "bomb_opens_route": 1.0
                },

                RobotStates.BOMB_EVADE: {
                    "distance_to_exit": 1.0,
                    "distance_to_bomb": 1.0,
                    "bomb": 1.0,
                    "bomb_danger": 0.0,
                    "bomb_opens_route": 0.0
                },

                RobotStates.MONSTER_EVADE: {
                    "bias": 0.0,
                    "exit_progress": 1.0,
                    "monster_progress": 1.0,
                    "monster_risk": -5.0
                }
            }

            if os.path.exists("weights.csv"):
                saved_weights = pd.read_csv("weights.csv")

                for _, row in saved_weights.iterrows():
                    behavior = RobotStates.__members__.get(row["Behavior"])
                    feature = row["Feature"]
                    if behavior in self.Weights and feature in self.Weights[behavior]:
                        self.Weights[behavior][feature] = float(row["Weight"])
                    # Retired feature names are ignored; new features use defaults.
        
            

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

            return self.filter_immediate_blast_actions(wrld, available_actions)



        def get_blocked_path_features(action):
            return self.route_action_features(wrld, action)

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

            return self.filter_immediate_blast_actions(wrld, available_actions)

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
                "bomb_opens_route": float(
                    action_type == "BOMB" and
                    (action_x, action_y) in self.navigation_info['useful_bomb_positions']
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
            return self.filter_immediate_blast_actions(wrld, available_actions)

        def monster_evade_features(action):
            return self.monster_action_features(wrld, action)
        
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

        # Evade reachable monsters nearby; distant monsters do not stop navigation.
        def check_monster_in_path():
            monster_list = get_monster_list()
            for monster in monster_list:
                purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), (monster.x, monster.y))
                if purposed_path is not None and len(purposed_path) - 1 <= 4:
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
