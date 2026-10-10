import math
import os
import random
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "Bomberman"
))

from enum import Enum, auto

import pandas as pd

from entity import CharacterEntity
from events import Event


class RobotStates(Enum):
    BLOCKED_PATH = auto()
    BOMB_EVADE = auto()
    MONSTER_EVADE = auto()


class InteractiveCharacter(CharacterEntity):

    alpha = 0.5
    gamma = 0.9

    def initialise_weights(self):
        if hasattr(self, "Weights"):
            return

        self.Weights = {
            RobotStates.BLOCKED_PATH: {
                "distance_to_exit": 1.0,
                "distance_to_wall": 1.0,
                "bomb": 1.0,
                "bomb_hits_wall": 0.0,
            },
            RobotStates.BOMB_EVADE: {
                "distance_to_exit": 1.0,
                "distance_to_bomb": 1.0,
                "bomb": 1.0,
                "bomb_danger": 0.0,
                "bomb_hits_wall": 0.0,
            },
            RobotStates.MONSTER_EVADE: {
                "distance_to_exit": 1.0,
                "distance_to_monster": 1.0,
                "bomb": 1.0,
            },
        }

        if not os.path.exists("weights.csv"):
            return

        saved_weights = pd.read_csv("weights.csv")

        for _, row in saved_weights.iterrows():
            try:
                behavior = RobotStates[row["Behavior"]]
            except KeyError:
                continue

            feature = row["Feature"]
            self.Weights[behavior][feature] = float(row["Weight"])

    def save_weights(self):
        rows = []

        for behavior, weights in self.Weights.items():
            for feature_name, weight in weights.items():
                rows.append({
                    "Behavior": behavior.name,
                    "Feature": feature_name,
                    "Weight": weight,
                })

        pd.DataFrame(
            rows,
            columns=["Behavior", "Feature", "Weight"],
        ).to_csv("weights.csv", index=False)

    def archive_q_value(self, behavior, action, q_value):
        row = pd.DataFrame([{
            "State": behavior.name,
            "Action": action,
            "Q_Value": q_value,
        }])

        file_exists = os.path.exists("q_values.csv")

        row.to_csv(
            "q_values.csv",
            mode="a",
            header=not file_exists,
            index=False,
        )

    def get_monsters(self, wrld):
        return [
            monster
            for monsters in wrld.monsters.values()
            for monster in monsters
        ]

    def get_monster_distance(self, wrld, position):
        return min(
            (
                max(
                    abs(position[0] - monster.x),
                    abs(position[1] - monster.y),
                )
                for monster in self.get_monsters(wrld)
            ),
            default=max(wrld.width(), wrld.height()),
        )

    def get_wall_distance(self, wrld, position):
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

    def in_bomb_danger(self, wrld, position):
        x, y = position

        if wrld.explosion_at(x, y):
            return True

        for bomb in wrld.bombs.values():
            if position == (bomb.x, bomb.y):
                return True

            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                for distance in range(1, wrld.expl_range + 1):
                    check_x = bomb.x + dx * distance
                    check_y = bomb.y + dy * distance

                    if not (
                        0 <= check_x < wrld.width()
                        and 0 <= check_y < wrld.height()
                    ):
                        break

                    if (
                        wrld.exit_at(check_x, check_y)
                        or wrld.bomb_at(check_x, check_y)
                    ):
                        break

                    if (check_x, check_y) == position:
                        return True

                    if wrld.wall_at(check_x, check_y):
                        break

        return False

    def choose_behavior(self, wrld):
        me = wrld.me(self)
        position = (me.x, me.y)

        if wrld.bombs or wrld.explosions or self.in_bomb_danger(wrld, position):
            return RobotStates.BOMB_EVADE

        if self.get_monsters(wrld):
            return RobotStates.MONSTER_EVADE

        return RobotStates.BLOCKED_PATH

    def get_features(self, wrld, behavior, action):
        action_type, action_x, action_y = action
        board_size = max(wrld.width(), wrld.height())

        distance_to_exit = max(
            abs(action_x - wrld.exitcell[0]),
            abs(action_y - wrld.exitcell[1]),
        )

        features = {
            "distance_to_exit": distance_to_exit / board_size,
            "bomb": float(action_type == "BOMB"),
        }

        if behavior == RobotStates.BLOCKED_PATH:
            features.update({
                "distance_to_wall": (
                    self.get_wall_distance(wrld, (action_x, action_y))
                    / board_size
                ),
                "bomb_hits_wall": float(
                    action_type == "BOMB"
                    and self.bomb_would_hit_wall(
                        wrld, (action_x, action_y)
                    )
                ),
            })

        elif behavior == RobotStates.BOMB_EVADE:
            distance_to_bomb = min(
                (
                    max(
                        abs(action_x - bomb.x),
                        abs(action_y - bomb.y),
                    )
                    for bomb in wrld.bombs.values()
                ),
                default=board_size,
            )

            features.update({
                "distance_to_bomb": distance_to_bomb / board_size,
                "bomb_danger": float(
                    action_type == "BOMB"
                    or self.in_bomb_danger(
                        wrld, (action_x, action_y)
                    )
                ),
                "bomb_hits_wall": float(
                    action_type == "BOMB"
                    and self.bomb_would_hit_wall(
                        wrld, (action_x, action_y)
                    )
                ),
            })

        elif behavior == RobotStates.MONSTER_EVADE:
            features["distance_to_monster"] = (
                self.get_monster_distance(
                    wrld, (action_x, action_y)
                )
                / board_size
            )

        return features

    def get_q_value(self, behavior, features):
        weights = self.Weights[behavior]

        return sum(
            weights.get(feature_name, 0.0) * feature_value
            for feature_name, feature_value in features.items()
        )

    def get_available_actions(self, wrld):
        me = wrld.me(self)

        candidates = [
            ("MOVE", me.x, me.y - 1, "w"),
            ("MOVE", me.x - 1, me.y, "a"),
            ("MOVE", me.x, me.y + 1, "s"),
            ("MOVE", me.x + 1, me.y, "d"),
            ("WAIT", me.x, me.y, ""),
            ("BOMB", me.x, me.y, "b"),
        ]

        actions = {}

        for action_type, x, y, key in candidates:
            if action_type == "MOVE":
                inside_board = (
                    0 <= x < wrld.width()
                    and 0 <= y < wrld.height()
                )

                if not inside_board or wrld.wall_at(x, y):
                    continue

            if action_type == "BOMB" and wrld.bomb_at(me.x, me.y):
                continue

            actions[key] = (action_type, x, y)

        return actions

    def get_max_next_q(self, wrld, behavior):
        q_values = []

        for action in self.get_available_actions(wrld).values():
            features = self.get_features(wrld, behavior, action)
            q_values.append(self.get_q_value(behavior, features))

        return max(q_values, default=0.0)

    def remember_action(self, wrld, behavior, action, features, q_value):
        me = wrld.me(self)

        self.previous_behavior = behavior
        self.previous_action = action
        self.previous_features = features.copy()
        self.previous_Q_value = q_value
        self.previous_position = (me.x, me.y)
        self.previous_monster_distance = self.get_monster_distance(
            wrld, self.previous_position
        )
        self.previous_bomb_danger = self.in_bomb_danger(
            wrld, self.previous_position
        )

    def get_reward(self, wrld, died=False, reached_exit=False):
        if died:
            return -100.0

        if reached_exit:
            return 100.0

        me = wrld.me(self)
        current_position = (me.x, me.y)

        previous_exit_distance = max(
            abs(self.previous_position[0] - wrld.exitcell[0]),
            abs(self.previous_position[1] - wrld.exitcell[1]),
        )
        current_exit_distance = max(
            abs(current_position[0] - wrld.exitcell[0]),
            abs(current_position[1] - wrld.exitcell[1]),
        )

        exit_progress = previous_exit_distance - current_exit_distance

        current_monster_distance = self.get_monster_distance(
            wrld, current_position
        )
        monster_progress = (
            current_monster_distance
            - self.previous_monster_distance
        )

        current_bomb_danger = self.in_bomb_danger(
            wrld, current_position
        )

        reward = -0.1

        hit_wall = any(
            event.tpe == Event.BOMB_HIT_WALL
            and event.character.name == self.name
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
            if self.previous_bomb_danger and not current_bomb_danger:
                reward += 5.0
            elif current_bomb_danger:
                reward -= 3.0

        elif self.previous_behavior == RobotStates.BLOCKED_PATH:
            reward += 0.5 * exit_progress

        return reward

    def update_previous_weights(self, reward, next_max_q):
        error = (
            reward
            + self.gamma * next_max_q
            - self.previous_Q_value
        )

        weights = self.Weights[self.previous_behavior]

        for feature_name, feature_value in self.previous_features.items():
            weights[feature_name] = (
                weights.get(feature_name, 0.0)
                + self.alpha * error * feature_value
            )

        self.save_weights()

    def clear_previous_action(self):
        attributes = (
            "previous_behavior",
            "previous_action",
            "previous_features",
            "previous_Q_value",
            "previous_position",
            "previous_monster_distance",
            "previous_bomb_danger",
        )

        for attribute in attributes:
            if hasattr(self, attribute):
                delattr(self, attribute)

    def update_from_previous_action(self, wrld):
        if not hasattr(self, "previous_features"):
            return

        behavior = self.choose_behavior(wrld)
        reward = self.get_reward(wrld)

        if wrld.time <= 0:
            next_max_q = 0.0
        else:
            next_max_q = self.get_max_next_q(wrld, behavior)

        self.update_previous_weights(reward, next_max_q)
        self.clear_previous_action()

    def do(self, wrld):
        self.initialise_weights()
        self.move(0, 0)

        # Learn from the action entered on the previous turn.
        self.update_from_previous_action(wrld)

        if wrld.time <= 0:
            return

        available_actions = self.get_available_actions(wrld)

        command = input(
            "Move (w=up, a=left, s=down, d=right, "
            "b=bomb, Enter=wait): "
        ).strip().lower()

        # Use only one command per turn.
        key = command[0] if command else ""

        if key not in available_actions:
            print("Invalid or blocked action. Waiting instead.")
            key = ""

        action = available_actions[key]
        behavior = self.choose_behavior(wrld)
        features = self.get_features(wrld, behavior, action)
        q_value = self.get_q_value(behavior, features)

        self.remember_action(
            wrld,
            behavior,
            action,
            features,
            q_value,
        )

        self.archive_q_value(behavior, action, q_value)

        print(
            f"State={behavior.name}, "
            f"Action={action}, "
            f"Q-value={q_value:.6f}"
        )
        print(f"Features={features}")
        print(f"Weights={self.Weights[behavior]}")

        if action[0] == "MOVE":
            me = wrld.me(self)
            self.move(action[1] - me.x, action[2] - me.y)

        elif action[0] == "BOMB":
            self.place_bomb()

    def done(self, wrld):
        self.initialise_weights()

        died = any(
            (
                event.tpe == Event.BOMB_HIT_CHARACTER
                and event.other.name == self.name
            )
            or (
                event.tpe == Event.CHARACTER_KILLED_BY_MONSTER
                and event.character.name == self.name
            )
            for event in wrld.events
        )

        reached_exit = any(
            event.tpe == Event.CHARACTER_FOUND_EXIT
            and event.character.name == self.name
            for event in wrld.events
        )

        if hasattr(self, "previous_features"):
            reward = self.get_reward(
                wrld,
                died=died,
                reached_exit=reached_exit,
            )
            self.update_previous_weights(reward, next_max_q=0.0)

        self.clear_previous_action()
