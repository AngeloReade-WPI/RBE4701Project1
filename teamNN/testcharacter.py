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
            SAFE_NAVIGATION = auto()
            MONSTER_IN_PROXIMITY = auto()
           
        #Initialize robot into the Safe Navigation state
        ROBOT_STATE = RobotStates.START

        ###########
        #StateEntry
        ###########

        def Enter_Safe_Navigation():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.SAFE_NAVIGATION
            pass
        def Enter_Monster_In_Proximity():
            nonlocal ROBOT_STATE
            ROBOT_STATE = RobotStates.MONSTER_IN_PROXIMITY
            pass
      
        ###########
        #SearchAlgs
        ###########
        def find_neighbors(nodeX, nodeY):
            #Get Current Position of Robot
            Current_Position = (nodeX,nodeY)
            All_Neighbors = []
            Invalid_Neighbors = []
            Valid_Neighbors = []
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] + 1, Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0], Current_Position[1] - 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1]))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] + 1))
            All_Neighbors.append((Current_Position[0] - 1, Current_Position[1] - 1))
            for neighbor in All_Neighbors:
                if neighbor[0] < 0 or neighbor[1] < 0 or neighbor[0] >= wrld.width() or neighbor[1] >= wrld.height() or wrld.wall_at(neighbor[0], neighbor[1]):
                    Invalid_Neighbors.append(neighbor)
            Valid_Neighbors = [neighbor for neighbor in All_Neighbors if neighbor not in Invalid_Neighbors]
            return Valid_Neighbors
        
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
        
        def follow_path(path):
            #Follow the path given by BFS
            current_node = path[0]
            next_node = path[1]
                #Move to the next node in the path
            self.move(next_node[0] - current_node[0], next_node[1] - current_node[1])

        def minimax_evaluation_function():
            #Generate a list of all legal player actions, then for each generated action, generate all possible monster actions
            Legal_Player_Actions = find_neighbors(wrld.me(self).x, wrld.me(self).y)
            Legal_Player_Actions.append((wrld.me(self).x, wrld.me(self).y)) #Add the option to stay in place
            monster_list = []
            for monsters in wrld.monsters.values():
                for m in monsters:
                    monster_list.append(m)

            if len(monster_list) == 1:
                print("2monsters detected")
                Legal_Monster_Actions = find_neighbors(monster_list[0].x, monster_list[0].y)
                Legal_Monster_Actions.append((monster_list[0].x, monster_list[0].y)) #Add the option to stay in place
           
                #For every legal player action, evaluate the worst case scenario for the player based on all possible monster actions. Return the best player action based on the worst case scenario.
                
                #Create a dictionary of node_score_pairs where the key is the player action and the value is the score of that action based on the worst case scenario for the player based on the monster actions. The score should be calculated using an equation that takes into account the distance to the target and the distance to the nearest monster. The equation should return a score for each player action, and the action with the highest score should be chosen as the best action for the player.
                node_score_pairs = {}
                #Iterate through every legal player action
                for action in Legal_Player_Actions:
                #get chebyshev distance to target
                    distance_to_target = max(abs(action[0] - wrld.exitcell[0]), abs(action[1] - wrld.exitcell[1]))
                    #for action I in legal player actions, iterate through every legal monster action
                    min_distance_to_monster = 1000
                    for monster_action in Legal_Monster_Actions:
                        #Get updated x,y to monster
                        #get chebyshev distance to monster
                        distance_to_monster = max(abs(action[0] - monster_action[0]), abs(action[1] - monster_action[1]))
                        if distance_to_monster < min_distance_to_monster:
                            min_distance_to_monster = distance_to_monster
                            #get each iteration of the loop to return worst case scenario for the player based on the monster actions
                    #create an equation that evaluates the best player action based on the worst case scenario for the player based on the monster actions. The equation should take into account the distance to the target and the distance to the nearest monster. The equation should return a score for each player action, and the action with the highest score should be chosen as the best action for the player.            
                    w1=1
                    w2=.5
                    node_score_pairs[action] = (w1 * min_distance_to_monster) - (w2 * distance_to_target) 
                    if min_distance_to_monster == 0:
                        node_score_pairs[action] = -1000
                    if min_distance_to_monster == 1:
                        node_score_pairs[action] = -10
                #choose the best player action based on the worst case scenario for the player based on the monster actions.
                print(node_score_pairs)    
                return max(node_score_pairs, key=node_score_pairs.get) 
            
            elif len(monster_list) == 2:    
                print("2monsters detected")
                Legal_Monster1_Actions = find_neighbors(monster_list[0].x, monster_list[0].y)
                Legal_Monster1_Actions.append((monster_list[0].x, monster_list[0].y)) #Add the option to stay in place
                Legal_Monster2_Actions = find_neighbors(monster_list[1].x, monster_list[1].y)
                Legal_Monster2_Actions.append((monster_list[1].x, monster_list[1].y)) #Add the option to stay in place

                #Create a dictionary of node_score_pairs where the key is the player action and the value is the score of that action based on the worst case scenario for the player based on the monster actions. The score should be calculated using an equation that takes into account the distance to the target and the distance to the nearest monster. The equation should return a score for each player action, and the action with the highest score should be chosen as the best action for the player.
                node_score_pairs = {}
                #iterate through every legal player action

                for action in Legal_Player_Actions:
                #get chebshev distance to target
                    distance_to_target = max(abs(action[0] - wrld.exitcell[0]), abs(action[1] - wrld.exitcell[1]))
                #Iterate through all monster actions for each monster. Return Both monsters min distance
                    min_distance_to_monster1 = 1000
                    for monster_action in Legal_Monster1_Actions:
                        #Get updated x,y to monster
                        #get chebyshev distance to monster
                        distance_to_monster = max(abs(action[0] - monster_action[0]), abs(action[1] - monster_action[1]))
                        if distance_to_monster < min_distance_to_monster1:
                            min_distance_to_monster1 = distance_to_monster

                    min_distance_to_monster2 = 1000
                    for monster_action in Legal_Monster2_Actions:
                        #Get updated x,y to monster
                        #get chebyshev distance to monster
                        distance_to_monster = max(abs(action[0] - monster_action[0]), abs(action[1] - monster_action[1]))
                        if distance_to_monster < min_distance_to_monster2:
                            min_distance_to_monster2 = distance_to_monster        
                #Compare and see which monster is bigger threat
                    biggest_monster_threat = min(min_distance_to_monster1,min_distance_to_monster2)
                    lesser_monster_threat = max(min_distance_to_monster1,min_distance_to_monster2)
                #Create an equation that evaluates best player action based on both worst monster case scenarios

                    # Safe move counter for the next move
                    next_turn_escape_nodes = find_neighbors(action[0], action[1])

                    # Staying at the proposed action is also an option
                    next_turn_escape_nodes.append(action)

                    safe_escape_count = 0

                    for escape in next_turn_escape_nodes:
                        minimum_escape_distance = 1000

                        # Check escape against every possible position of monster 1
                        for monster_action in Legal_Monster1_Actions:
                            distance_to_monster = max( abs(escape[0] - monster_action[0]), abs(escape[1] - monster_action[1]))

                            if distance_to_monster < minimum_escape_distance:
                                minimum_escape_distance = distance_to_monster

                        # Check escape against every possible position of monster 2
                        for monster_action in Legal_Monster2_Actions:
                            distance_to_monster = max(abs(escape[0] - monster_action[0]),abs(escape[1] - monster_action[1]))

                            if distance_to_monster < minimum_escape_distance:
                                minimum_escape_distance = distance_to_monster

                        # Count this escape only if neither monster can get adjacent
                        if minimum_escape_distance > 1:
                            safe_escape_count += 1

                    # Score the proposed player action
                    w1 = 2
                    w2 = 0.5
                    w3 = 0.25
                    w4 = 1

                    node_score_pairs[action] = ((w1 * biggest_monster_threat) + (w2 * lesser_monster_threat) - (w3 * distance_to_target) + (w4 * safe_escape_count) )
                    # Apply safety penalties
                    if biggest_monster_threat == 0:
                        node_score_pairs[action] = -1000
                    else:
                        if biggest_monster_threat == 1:
                            node_score_pairs[action] -= 200

                        if safe_escape_count == 0:
                            node_score_pairs[action] -= 500
                print(node_score_pairs)    
                return max(node_score_pairs, key=node_score_pairs.get) 
                            
        def advance_to_node(next_node):
            #Move to the next node in the path
            current_node = (wrld.me(self).x, wrld.me(self).y)
            self.move(next_node[0] - current_node[0], next_node[1] - current_node[1])
            pass
            


        ###########
        #Update####
        ###########
        def Update():
            if ROBOT_STATE == RobotStates.SAFE_NAVIGATION:
                #Call BFS
                Path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
                follow_path(Path)
                pass
            if ROBOT_STATE == RobotStates.MONSTER_IN_PROXIMITY:
                print("Monster in Proximity")
                Path = minimax_evaluation_function()
                advance_to_node(Path)
                pass

        ###########
        #Checkers##
        ###########
        #If there are no monsters in world, it is safe. If the next proposed move puts you within 2 spaces of a monster, it is not safe
        def Check_Safe_Navigation():
            purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
            count=0
            if len(wrld.monsters) == 0:
                return True
    
            for monsters in wrld.monsters.values():
                for m in monsters:
                    if abs(purposed_path[1][0] - m.x) <= 2 and abs(purposed_path[1][1] - m.y) <= 2:
                        count+=1
            if count > 0:
                return False
            return True
        #If there are no monsters in world,no monsters are in proximity. If the next proposed move puts you within 2 spaces of a monster, a monster is in proximity
        def Check_Monster_In_Proximity():
            purposed_path = BFS((wrld.me(self).x, wrld.me(self).y), wrld.exitcell)
            count=0
            if len(wrld.monsters) == 0:
                return False
            for monsters in wrld.monsters.values():
                for m in monsters:
                    if abs(purposed_path[1][0] - m.x) <= 2 and abs(purposed_path[1][1] - m.y) <= 2:
                        count+=1
            if count > 0:
                return True
            return False
            
            
        ###########
        #Handlers##
        ###########
        def Handle_Safe_Navigation():
            Enter_Safe_Navigation()
            Update()
            pass
        def Handle_Monster_In_Proximity():
            Enter_Monster_In_Proximity()
            Update()
            pass

        ###########
        #MainLoop##
        ###########
   
        if Check_Safe_Navigation():
            Handle_Safe_Navigation()
        elif Check_Monster_In_Proximity():
            Handle_Monster_In_Proximity()
