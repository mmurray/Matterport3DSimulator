import argparse
from jinja2 import Template
import os
import ast
import json
import networkx as nx
import numpy as np


# Edited from 'tasks/R2R/utils.py'
def load_gold_paths(scans):

    def distance(pose1, pose2):
        return ((pose1['pose'][3]-pose2['pose'][3])**2 +
                (pose1['pose'][7]-pose2['pose'][7])**2 +
                (pose1['pose'][11]-pose2['pose'][11])**2)**0.5

    paths = {}
    for scan in scans:
        with open('../../../connectivity/%s_connectivity.json' % scan) as f:
            g = nx.Graph()
            positions = {}
            data = json.load(f)
            for i,item in enumerate(data):
                if item['included']:
                    for j,conn in enumerate(item['unobstructed']):
                        if conn and data[j]['included']:
                            positions[item['image_id']] = np.array([item['pose'][3],
                                                                    item['pose'][7], item['pose'][11]])
                            assert data[j]['unobstructed'][i], 'Graph should be undirected'
                            g.add_edge(item['image_id'], data[j]['image_id'], weight=distance(item, data[j]))
            nx.set_node_attributes(g, values=positions, name='position')
            paths[scan] = dict(nx.all_pairs_dijkstra_path(g))

    return paths


def main(args):

    sessions = []
    total_traj = 0
    total_traj_count = 0

    # TODO: get these from scans.txt
    gold_paths = load_gold_paths(['17DRP5sb8fy', 'sT4fr6TAbpF', 'wc2JMjhGNzB'])


    for log_filename in os.listdir(os.path.join(args.input_dir, 'log')):
        if "_" in log_filename:
            session = {
                "id": log_filename.split(".")[0],
                "dialog": [],
                "feedback": [],
                "traj_count": 0,
                "success": False,
                "started": False,
                "status_label": "Unstarted",
                "status_class": "danger"
            }

            # session log
            with open(os.path.join(args.input_dir, 'log', log_filename)) as log_file:
                session_log = log_file.read()

                session["log"] = session_log

                lines = session_log.split("\n")

                image_id = ""

                for line in lines:
                    pieces = line.split("\t")
                    if len(pieces) <= 2:
                        continue

                    log_entry = ast.literal_eval(pieces[2])

                    # metadata
                    if log_entry['action'] == 'set_house':
                        session['house'] = log_entry['value']
                    if log_entry['action'] == 'set_target_obj':
                        session['target_obj'] = log_entry['value']
                    if log_entry['action'] == 'set_start_pano':
                        session['start_pano'] = log_entry['value']
                        image_id = log_entry['value']
                    if log_entry['action'] == 'set_end_panos':
                        session['end_panos'] = log_entry['value']


                    # nav
                    if log_entry['action'] == 'nav':
                        if log_entry['message']['img_id'] != image_id:
                            image_id = log_entry['message']['img_id']
                            session["traj_count"] += 1
                            session["started"] = True
                            session["status_label"] = "Incomplete"
                            session["status_class"] = "warning"

                    # dialog
                    if log_entry['action'] == 'chat':
                        session['dialog'].append(log_entry['message'])

                    if log_entry['action'] == 'set_aux' and log_entry['message'] == 'Congrats, you found the room!':
                        session['success'] = True
                        session["status_label"] = "Success"
                        session["status_class"] = "success"


            # feedback
            users = log_filename.split(".")[0].split("_")
            for user in users:
                feedback_path = os.path.join(args.input_dir, "feedback", user + ".json")
                if not os.path.exists(feedback_path):
                    continue
                with open(feedback_path) as feedback_file:
                    feedback_json = feedback_file.read()
                    feedback_dict = json.loads(feedback_json)
                    if feedback_dict['uid'] == feedback_dict['oracle']:
                        session["navigator_rating"] = feedback_dict["rating"]
                        session["feedback"].append("(From Oracle): " + feedback_dict['free_form_feedback'])

                    if feedback_dict['uid'] == feedback_dict['navigator']:
                        session["oracle_rating"] = feedback_dict["rating"]
                        session["feedback"].append("(From Navigator): " + feedback_dict['free_form_feedback'])



            if session['traj_count'] > 0:
                total_traj_count += 1
                total_traj += session['traj_count']


            session["gold_path_len"] = len(gold_paths[session['house']][session['start_pano']][session['end_panos'].split(',')[0]])

            sessions.append(session)

    with open(os.path.dirname(os.path.abspath(__file__)) + '/resources/batch_report_template.html') as template_html_file:
        t = Template(template_html_file.read())
        result = t.render(sessions=sessions,
                          num=len(sessions),
                          num_success=len([s for s in sessions if s['success']]),
                          avg_traj=total_traj/total_traj_count)
        with open(args.output, 'w') as out_file:
            out_file.write(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=str, required=True,
                        help="Output file")
    parser.add_argument('--input_dir', type=str, required=True,
                        help="Path to input dir containing log, client, and feedback dirs")
    main(parser.parse_args())
