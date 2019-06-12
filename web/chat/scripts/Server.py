#!/usr/bin/env python
__author__ = 'jesse'

import argparse
import json
import numpy as np
import os
import sys
import time


class Game:

    # Initialize the game.
    def __init__(self, uid1, uid2,
                 house, target_obj, start_pano, end_panos):
        print("Game: initializing with users %s, %s" % (uid1, uid2))
        print("Game: ... house %s, target %s, start pano %s, end panos " %
              (house, target_obj, start_pano) + str(end_panos))

        self.navigator = uid1
        self.oracle = uid2
        self.house = house
        self.target_obj = target_obj
        self.start_pano = start_pano
        self.end_panos = end_panos

        self.partner = {uid1: uid2, uid2: uid1}

        # Used when game is started.
        self.turn = None
        self.name = None

    # Start the game.
    def assign_roles(self):
        if np.random.randint(0, 2) == 0:
            tmp = self.navigator
            self.navigator = self.oracle
            self.oracle = tmp
        self.turn = "navigator"
        self.name = '%s_%s' % (self.navigator, self.oracle)
        # Make chat visible to both players.
        # Make primary navigation visible to navigator.
        # Enable navigator chat and navigation.
        # Make mirror navigation visible to oracle.
        return [[{"type": "update", "action": "set_house", "value": self.house},
                 {"type": "update", "action": "set_target_obj", "value": self.target_obj},
                 {"type": "update", "action": "set_start_pano", "value": self.start_pano},
                 {"type": "update", "action": "set_aux", "message": "Another player connected! You are The Navigator."},
                 {"type": "update", "action": "hide_instructions"},
                 {"type": "update", "action": "show_chat"},
                 {"type": "update", "action": "show_nav"},
                 {"type": "update", "action": "enable_chat"},
                 {"type": "update", "action": "enable_nav"},
                 ],
                [{"type": "update", "action": "set_house", "value": self.house},
                 {"type": "update", "action": "set_target_obj", "value": self.target_obj},
                 {"type": "update", "action": "set_start_pano", "value": self.start_pano},
                 {"type": "update", "action": "set_end_panos", "value": ','.join(self.end_panos)},
                 {"type": "update", "action": "set_aux", "message": "Another player connected! You are The Oracle."},
                 {"type": "update", "action": "hide_instructions"},
                 {"type": "update", "action": "show_chat"},
                 {"type": "update", "action": "show_mirror_nav"},
                 {"type": "update", "action": "show_gold_view"},
                 ]
                ]

    # Update the game from a client communication.
    # Returns (nav_m, oracle_m)
    def update(self, d, oracle, navigator):
        action = d["action"]
        if action == "chat":
            contents = d["message"]
            speaker_m = [{"type": "update", "action": "add_chat", "speaker": "self", "message": contents},  # the chat
                         {"type": "update", "action": "disable_chat"}]  # disable chatbox
            listener_m = [{"type": "update", "action": "add_chat", "speaker": "other", "message": contents},  # the chat
                          {"type": "update", "action": "enable_chat"}]  # enable chat

            # Navigator typed a help request chat to the oracle, so disable navigation until response.
            # In addition, enable the oracle to do gold viewing.
            if self.turn == "navigator":
                speaker_m.extend([{"type": "update", "action": "disable_nav"}])
                listener_m.extend([{"type": "update", "action": "enable_gold_view"}])
                self.turn = "oracle"
                return [speaker_m, listener_m, False]

            # Oracle typed a help response chat to the navigator, so disable gold view.
            # In addition, enable the navigator to do navigation.
            else:
                speaker_m.extend([{"type": "update", "action": "disable_gold_view"}])
                listener_m.extend([{"type": "update", "action": "enable_nav"}])
                self.turn = "navigator"
                return [listener_m, speaker_m, False]
        elif action == "nav":
            contents = d["message"]
            nav_m = []
            oracle_m = [{"type": "update", "action": "update_mirror_nav", "message": contents}]
            return [nav_m, oracle_m, False]
        elif action == "guess_stop":
            curr_pano = d["value"]
            if curr_pano in self.end_panos:  # correct location, so end task.
                nav_m = [{"type": "update", "action": "set_aux", "message": "Congrats, you found the room!"},
                         {"type": "update", "action": "disable_chat"},
                         {"type": "update", "action": "disable_nav"},
                         {"type": "update", "action": "enable_exit", "message": {"oracle": oracle, "navigator": navigator}}]
                oracle_m = [{"type": "update", "action": "set_aux",
                             "message": "Congrats, you helped your partner find the room!"},
                            {"type": "update", "action": "disable_chat"},
                            {"type": "update", "action": "disable_gold_view"},
                            {"type": "update", "action": "enable_exit", "message": {"oracle": oracle, "navigator": navigator}}]
                return [nav_m, oracle_m, True]
            else:  # incorrect location, so freeze nav and set aux.
                nav_m = [{"type": "update", "action": "disable_nav"},
                         {"type": "update", "action": "set_aux",
                          "message": "You're not yet in the right room. Try asking your partner for directions."}]
                oracle_m = []
            return [nav_m, oracle_m, False]

    # Interrupted.
    def interrupt(self, m):
        return [[{"type": "update", "action": "set_aux", "message": m},
                 {"type": "update", "action": "disable_chat"},
                 {"type": "update", "action": "disable_nav"},
                 {"type": "update", "action": "enable_exit"}],
                [{"type": "update", "action": "set_aux", "message": m},
                 {"type": "update", "action": "disable_chat"},
                 {"type": "update", "action": "disable_gold_view"},
                 {"type": "update", "action": "enable_exit"}]]


class Server:

    devnull = open(os.devnull, 'w')

    # Initialize the server.
    # spin_time - time in seconds between polling the filesystem for client communications.
    # max_seconds_per_turn - how many seconds to wait for a client response before aborting the dialog.
    # max_seconds_unpaired - how many seconds to let a client sit unpaired before aborting the dialog.
    # client_dir - directory to use for IPC with web server via JSON file reads/writes.
    # log_dir - directory to store interaction logs.
    def __init__(self, spin_time, max_seconds_per_turn, max_seconds_unpaired, client_dir, log_dir,
                 house_targets):
        self.spin_time = spin_time
        self.max_cycles_per_turn = max_seconds_per_turn / float(spin_time)
        self.max_cycles_unpaired = max_seconds_unpaired / float(spin_time)
        self.client_dir = client_dir
        self.log_dir = log_dir
        self.house_targets = house_targets

        # State and message information.
        self.users = []  # list of user ids, uid
        self.time_unpaired = {}  # map from uid -> int indicating how long a user has waited unpaired.
        self.games = []  # list of games indexed by game id gid
        self.games_timeout = []  # list of games' remaining times
        self.logs = []  # list of log file names parallel to games list
        self.u2g = {}  # assignment of users to games, uid -> gid
        self.exit_enabled = []

        # File upkeep is done at the end of each cycle; changes to be made stored in these structures.
        self.files_to_remove = []
        self.files_to_write = []

        # Current cycle.
        self.curr_cycle = 0

    # Begin to spin forever, checking the disk for relevant communications.
    def spin(self):

        # Spin.
        print("Server: spinning forever...")
        try:
            while True:

                # Walk the filesystem for new inputs from client-side webpage.
                for root, _, files in os.walk(self.client_dir):
                    for fn in files:
                        fnp = fn.split('.')
                        # Communication files from the client are named "[uid].client.json"
                        if len(fnp) == 3 and fnp[1] == 'client' and fnp[2] == 'json':
                            uid = fn.split('.')[0]
                            self.interpret_client_comm(os.path.join(root, fn), uid)
                            self.flush_files()

                # Pair users and start games.
                self.start_games()

                # Remove users who have been unpaired for too long.
                unassigned = [uid for uid in self.users if uid not in self.u2g]
                for uid in unassigned:
                    self.time_unpaired[uid] -= 1
                    if self.time_unpaired[uid] == 0:
                        self.exit_enabled.append(uid)
                        self.files_to_write.extend(
                            [("none", uid, "server", {"type": "update", "action": "enable_exit"})])

                # Interrupt games that have had no communication for too long.
                for gidx in range(len(self.games)):
                    if self.games[gidx] is not None:
                        self.games_timeout[gidx] -= 1
                        if self.games_timeout[gidx] == 0:
                            g = self.games[gidx]
                            nav_ms, oracle_ms = g.interrupt(
                                "Looks like you or your partner took too long to respond. Sorry about that! " +
                                "You can end the HIT and recieve payment.")
                            self.files_to_write.extend([(g.name, g.navigator, "server", m) for m in nav_ms])
                            self.files_to_write.extend([(g.name, g.oracle, "server", m) for m in oracle_ms])

                # Remove flagged files and write new ones.
                self.flush_files()

                time.sleep(self.spin_time)
                self.curr_cycle += 1

        # Clean up upon sigterm.
        except KeyboardInterrupt:
            print("Server: caught interrupt signal; ending games and messaging unpaired users")
            # Interrupt games.
            for g in self.games:
                if g is not None:
                    nav_ms, oracle_ms = g.interrupt("Unexpected Server Error. You can end the HIT and recieve payment.")
                    self.files_to_write.extend([(g.name, g.navigator, "server", m) for m in nav_ms])
                    self.files_to_write.extend([(g.name, g.oracle, "server", m) for m in oracle_ms])
            # Let unpaired users off the hook.
            unassigned = [uid for uid in self.users if uid not in self.u2g]
            for uid in unassigned:
                self.files_to_write.extend([("none", uid, "server", {"type": "update", "action": "set_aux",
                                                                     "message": "Unexpected Server Error." +
                                                                     "You can end the HIT and recieve payment."}),
                                            ("none", uid, "server", {"type": "update", "action": "enable_exit"})])
            while (len(self.files_to_write)) > 0:
                print("Server: Flushing files...")
                self.flush_files()
                time.sleep(self.spin_time)
                self.curr_cycle += 1

    # Interpret JSON communication from a user.
    # fn - the file path to interpret.
    def interpret_client_comm(self, fn, uid):
        with open(fn, 'r') as f:
            d = json.load(f)
        # New client connecting.
        if d["type"] == "new":
            self.create_new_user(uid)

            # Log new user appearance.
            log_fn = os.path.join(self.log_dir, uid + ".log")
            with open(log_fn, 'a') as f:
                f.write('%d\tclient\t%s\n' % (self.curr_cycle, d))
        # Game action.
        if d["type"] == "update":
            g = self.games[self.u2g[uid]]
            self.games_timeout[self.u2g[uid]] = self.max_cycles_per_turn
            nav_ms, oracle_ms, game_over = g.update(d, g.oracle, g.navigator)
            self.files_to_write.extend([(g.name, g.navigator, "server", m) for m in nav_ms])
            self.files_to_write.extend([(g.name, g.oracle, "server", m) for m in oracle_ms])

            # Log client updates.
            log_fn = os.path.join(self.log_dir, g.name + ".log")
            with open(log_fn, 'a') as f:
                f.write('%d\tclient\t%s\n' % (self.curr_cycle, d))

            # If game is over, clear it.
            if game_over:
                self.games[self.u2g[uid]] = None

        if d["type"] == "exit":
            self.users.remove(uid)  # Remove the user from the queue so they dont get paired later
            self.exit_enabled.remove(uid)
            self.files_to_write.extend(
                [("none", uid, "server", {"type": "update", "action": "exit"})])

        # Mark this communication for removal.
        self.files_to_remove.append(fn)

    # Create a new user.
    def create_new_user(self, uid):
        print("Server: creating new user " + uid)
        self.users.append(uid)
        self.time_unpaired[uid] = self.max_cycles_unpaired

    def start_games(self):
        unassigned = [uid for uid in self.users if uid not in self.u2g]
        while len(unassigned) > 1:
            uid1 = unassigned.pop(0)
            uid2 = unassigned.pop(0)

            if uid1 in self.exit_enabled:
                self.exit_enabled.remove(uid1)
            if uid2 in self.exit_enabled:
                self.exit_enabled.remove(uid2)

            # TODO: select a house and tuple from house_targets in some kind of better, active fashion than this.
            house = np.random.choice(list(self.house_targets.keys()))
            pair_idx = np.random.randint(0, len(self.house_targets[house]))
            target_obj, start_pano, _, end_panos, dists = self.house_targets[house][pair_idx]

            print("Server: assign_pairs pairing users %s and %s to play in house %s with target obj %s (dists=" %
                  (uid1, uid2, house, target_obj) + str(dists) + ")")
            g = Game(uid1, uid2, house, target_obj, start_pano, end_panos)
            if None in self.games:
                gid = self.games.index(None)
                self.games[gid] = g
                self.games_timeout[gid] = self.max_cycles_per_turn
            else:
                gid = len(self.games)
                self.games.append(g)
                self.games_timeout.append(self.max_cycles_per_turn)
            self.u2g[uid1] = gid
            self.u2g[uid2] = gid

            # Get role file contents to write from game start.
            nav_ms, oracle_ms = g.assign_roles()
            self.files_to_write.extend([(g.name, g.navigator, "server", m) for m in nav_ms])
            self.files_to_write.extend([(g.name, g.oracle, "server", m) for m in oracle_ms])

            # Log user pairing.
            for uids, uido in [[uid1, uid2], [uid2, uid1]]:
                log_fn = os.path.join(self.log_dir, uids + ".log")
                with open(log_fn, 'a') as f:
                    f.write('%d\tserver\t%s\n' % (self.curr_cycle, {"type": "pair", "partner": uido}))

    # Removes flagged files, writes queued files, and logs writes as text.
    def flush_files(self):

        # Remove flagged files.
        for fn in self.files_to_remove:
            path = os.path.join(fn)
            cmd = "rm -f " + path
            print("Server executing: " + cmd)
            os.system(cmd)
        self.files_to_remove = []

        # Collate files to write by uid.
        msgs_for_uid = {}
        for game_name, uid, ext, s in self.files_to_write:
            if uid not in msgs_for_uid:
                msgs_for_uid[uid] = []
            msgs_for_uid[uid].append((game_name, ext, s))
        self.files_to_write = []

        # For every user, write communications file for next steps if client has processed existing one.
        uids_messaged = []
        for uid in msgs_for_uid:
            game_name, ext, _ = msgs_for_uid[uid][0]
            fn = os.path.join(self.client_dir, '.'.join([uid, ext, 'json']))
            if not os.path.isfile(fn):  # only proceed if the client has already processed existing messages.
                with open(fn, 'w') as f:
                    ss = [msg[2] for msg in msgs_for_uid[uid]]
                    print("Server writing '" + fn + "' with contents: \"" + str(ss) + "\"")
                    json.dump(ss, f)
                log_fn = os.path.join(self.log_dir, game_name + ".log")
                with open(log_fn, 'a') as f:
                    f.write('\n'.join(['%d\tserver\t%s' % (self.curr_cycle, s) for s in ss]) + '\n')
                uids_messaged.append(uid)

        # Re-queue files to write for users whose clients have not yet processed their files.
        for uid in msgs_for_uid:
            if uid not in uids_messaged: 
                self.files_to_write.extend([(game_name, uid, ext, s) for game_name, ext, s in msgs_for_uid[uid]])


# Spin up a server to sit and manage incoming connections.
def main(args):

    # Hard-coded server and game params.
    server_spin_time = 1
    max_seconds_per_turn = 480
    max_seconds_unpaired = 420

    print("main: loading house targets from '%s'" % args.house_target_fn)
    with open(args.house_target_fn, 'r') as f:
        house_targets = json.load(f)
    print("main: ... done; loaded %d houses of targets" % len(house_targets))

    # Start the Server.
    print("main: instantiated server...")
    s = Server(server_spin_time, max_seconds_per_turn, max_seconds_unpaired,
               args.client_dir, args.log_dir, house_targets)
    print("main: ... done")

    print("main: spinning server...")
    s.spin()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client_dir', type=str, required=True,
                        help="the directory to read/write client communication text files")
    parser.add_argument('--log_dir', type=str, required=True,
                        help="the directory to write logfiles to")
    parser.add_argument('--house_target_fn', type=str, required=True,
                        help="the file containing house targets for data collection")
    main(parser.parse_args())
