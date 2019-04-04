#!/usr/bin/env python

''' Script to precompute object detections using a YOLO CNN, using 36 discretized views
    at each viewpoint in 30 degree increments, and the provided camera WIDTH, HEIGHT
    and VFOV parameters. '''

import numpy as np
import cv2
import json
import math
import base64
import csv
import sys

csv.field_size_limit(sys.maxsize)

# Caffe and MatterSim need to be on the Python path
sys.path.insert(0, 'build')
import MatterSim

# import mxnet as mx
# from gluoncv import model_zoo, data, utils

import torch
from torch.utils.data import DataLoader
from yolo.models import Darknet

# caffe_root = '../'  # your caffe build
# sys.path.insert(0, caffe_root + 'python')
# import caffe

from timer import Timer


TSV_FIELDNAMES = ['scanId', 'viewpointId', 'image_w', 'image_h', 'vfov', 'detections']
VIEWPOINT_SIZE = 36  # Number of discretized views from one viewpoint
FEATURE_SIZE = 4
CLASS_SIZE = 80
BATCH_SIZE = 4  # Some fraction of viewpoint size - batch size 4 equals 11GB memory
GPU_ID = 0
# MODEL = 'models/resnet152_places365.caffemodel'
OUTFILE = 'img_features/yolov3.tsv'
GRAPHS = 'connectivity/'

# Simulator image parameters
VFOV = 60
YOLO_IMAGE_SIZE=416
WIDTH=YOLO_IMAGE_SIZE
HEIGHT=YOLO_IMAGE_SIZE

def load_classes(path):
    """
    Loads class labels at 'path'
    """
    fp = open(path, "r")
    names = fp.read().split("\n")[:-1]
    return names

classes = load_classes('scripts/yolo/data/coco.names')

def non_max_suppression(prediction, num_classes, conf_thres=0.5, nms_thres=0.4):
    """
    Removes detections with lower object confidence score than 'conf_thres' and performs
    Non-Maximum Suppression to further filter detections.
    Returns detections with shape:
        (x1, y1, x2, y2, object_conf, class_score, class_pred)
    """

    # From (center x, center y, width, height) to (x1, y1, x2, y2)
    box_corner = prediction.new(prediction.shape)
    box_corner[:, :, 0] = prediction[:, :, 0] - prediction[:, :, 2] / 2
    box_corner[:, :, 1] = prediction[:, :, 1] - prediction[:, :, 3] / 2
    box_corner[:, :, 2] = prediction[:, :, 0] + prediction[:, :, 2] / 2
    box_corner[:, :, 3] = prediction[:, :, 1] + prediction[:, :, 3] / 2
    prediction[:, :, :4] = box_corner[:, :, :4]

    output = [None for _ in range(len(prediction))]
    for image_i, image_pred in enumerate(prediction):
        # Filter out confidence scores below threshold
        conf_mask = (image_pred[:, 4] >= conf_thres).squeeze()
        image_pred = image_pred[conf_mask]
        # If none are remaining => process next image
        if not image_pred.size(0):
            continue
        # Get score and class with highest confidence
        class_conf, class_pred = torch.max(image_pred[:, 5 : 5 + num_classes], 1, keepdim=True)
        # Detections ordered as (x1, y1, x2, y2, obj_conf, class_conf, class_pred)
        detections = torch.cat((image_pred[:, :5], class_conf.float(), class_pred.float()), 1)
        # Iterate through all predicted classes
        unique_labels = detections[:, -1].cpu().unique()
        if prediction.is_cuda:
            unique_labels = unique_labels.cuda()
        for c in unique_labels:
            # Get the detections with the particular class
            detections_class = detections[detections[:, -1] == c]
            # Sort the detections by maximum objectness confidence
            _, conf_sort_index = torch.sort(detections_class[:, 4], descending=True)
            detections_class = detections_class[conf_sort_index]
            # Perform non-maximum suppression
            max_detections = []
            while detections_class.size(0):
                # Get detection with highest confidence and save as max detection
                max_detections.append(detections_class[0].unsqueeze(0))
                # Stop if we're at the last detection
                if len(detections_class) == 1:
                    break
                # Get the IOUs for all boxes with lower confidence
                ious = bbox_iou(max_detections[-1], detections_class[1:])
                # Remove detections with IoU >= NMS threshold
                detections_class = detections_class[1:][ious < nms_thres]

            max_detections = torch.cat(max_detections).data
            # Add max detections to outputs
            output[image_i] = (
                max_detections if output[image_i] is None else torch.cat((output[image_i], max_detections))
            )

    return output


def bbox_iou(box1, box2, x1y1x2y2=True):
    """
    Returns the IoU of two bounding boxes
    """
    if not x1y1x2y2:
        # Transform from center and width to exact coordinates
        b1_x1, b1_x2 = box1[:, 0] - box1[:, 2] / 2, box1[:, 0] + box1[:, 2] / 2
        b1_y1, b1_y2 = box1[:, 1] - box1[:, 3] / 2, box1[:, 1] + box1[:, 3] / 2
        b2_x1, b2_x2 = box2[:, 0] - box2[:, 2] / 2, box2[:, 0] + box2[:, 2] / 2
        b2_y1, b2_y2 = box2[:, 1] - box2[:, 3] / 2, box2[:, 1] + box2[:, 3] / 2
    else:
        # Get the coordinates of bounding boxes
        b1_x1, b1_y1, b1_x2, b1_y2 = box1[:, 0], box1[:, 1], box1[:, 2], box1[:, 3]
        b2_x1, b2_y1, b2_x2, b2_y2 = box2[:, 0], box2[:, 1], box2[:, 2], box2[:, 3]

    # get the corrdinates of the intersection rectangle
    inter_rect_x1 = torch.max(b1_x1, b2_x1)
    inter_rect_y1 = torch.max(b1_y1, b2_y1)
    inter_rect_x2 = torch.min(b1_x2, b2_x2)
    inter_rect_y2 = torch.min(b1_y2, b2_y2)
    # Intersection area
    inter_area = torch.clamp(inter_rect_x2 - inter_rect_x1 + 1, min=0) * torch.clamp(
        inter_rect_y2 - inter_rect_y1 + 1, min=0
    )
    # Union Area
    b1_area = (b1_x2 - b1_x1 + 1) * (b1_y2 - b1_y1 + 1)
    b2_area = (b2_x2 - b2_x1 + 1) * (b2_y2 - b2_y1 + 1)

    iou = inter_area / (b1_area + b2_area - inter_area + 1e-16)

    return iou


def bbox_iou_numpy(box1, box2):
    """Computes IoU between bounding boxes.
    Parameters
    ----------
    box1 : ndarray
        (N, 4) shaped array with bboxes
    box2 : ndarray
        (M, 4) shaped array with bboxes
    Returns
    -------
    : ndarray
        (N, M) shaped array with IoUs
    """
    area = (box2[:, 2] - box2[:, 0]) * (box2[:, 3] - box2[:, 1])

    iw = np.minimum(np.expand_dims(box1[:, 2], axis=1), box2[:, 2]) - np.maximum(
        np.expand_dims(box1[:, 0], 1), box2[:, 0]
    )
    ih = np.minimum(np.expand_dims(box1[:, 3], axis=1), box2[:, 3]) - np.maximum(
        np.expand_dims(box1[:, 1], 1), box2[:, 1]
    )

    iw = np.maximum(iw, 0)
    ih = np.maximum(ih, 0)

    ua = np.expand_dims((box1[:, 2] - box1[:, 0]) * (box1[:, 3] - box1[:, 1]), axis=1) + area - iw * ih

    ua = np.maximum(ua, np.finfo(float).eps)

    intersection = iw * ih

    return intersection / ua

def load_viewpointids():
    viewpointIds = []
    with open(GRAPHS + 'scans.txt') as f:
        scans = [scan.strip() for scan in f.readlines()]
        for scan in scans:
            with open(GRAPHS + scan + '_connectivity.json')  as j:
                data = json.load(j)
                for item in data:
                    if item['included']:
                        viewpointIds.append((scan, item['image_id']))
    print
    'Loaded %d viewpoints' % len(viewpointIds)
    return viewpointIds


def transform_img(im):
    ''' Prep opencv 3 channel image for the network '''
    im_orig = im.astype(np.float32, copy=True)
    im_orig -= np.array([[[103.1, 115.9, 123.2]]])  # BGR pixel mean
    blob = np.zeros((1, im.shape[0], im.shape[1], 3), dtype=np.float32)
    blob[0, :, :, :] = im_orig
    blob = blob.transpose((0, 3, 1, 2))
    return blob

def quadrants(detections):
    # return None

    q1 = np.zeros(len(classes))
    q2 = np.zeros(len(classes))
    q3 = np.zeros(len(classes))
    q4 = np.zeros(len(classes))

    mid = 416 / 2

    if detections is not None:
        for x1, y1, x2, y2, conf, cls_conf, cls_pred in detections:

            pt1 = (x1,y1)
            pt2 = (x1,y2)
            pt3 = (x2,y1)
            pt4 = (x2,y2)
            pts = [pt1,pt2,pt3,pt4]

            if len([p for p in pts if p[0] >= mid and p[1] < mid]) > 0:
                q1[int(cls_pred)] = max(q1[int(cls_pred)], cls_conf)
            if len([p for p in pts if p[0] < mid and p[1] < mid]) > 0:
                q2[int(cls_pred)] = max(q2[int(cls_pred)], cls_conf)
            if len([p for p in pts if p[0] < mid and p[1] >= mid]) > 0:
                q3[int(cls_pred)] = max(q3[int(cls_pred)], cls_conf)
            if len([p for p in pts if p[0] >= mid and p[1] >= mid]) > 0:
                q4[int(cls_pred)] = max(q4[int(cls_pred)], cls_conf)

    return np.concatenate([q1,q2,q3,q4])

def build_tsv():
    # Set up the simulator
    sim = MatterSim.Simulator()
    sim.setCameraResolution(WIDTH, HEIGHT)
    sim.setCameraVFOV(math.radians(VFOV))
    sim.setDiscretizedViewingAngles(True)
    sim.initialize()

    # Set up yolo
    print "loading yolo v3..."
    with torch.no_grad():
        darknet = Darknet('scripts/yolo/config/yolov3.cfg', img_size=YOLO_IMAGE_SIZE)
        darknet.load_weights('scripts/yolo/weights/yolov3.weights')
    print "yolo loaded"

    count = 0
    t_render = Timer()
    t_net = Timer()

    with open(OUTFILE, 'wb') as tsvfile:
        writer = csv.DictWriter(tsvfile, delimiter='\t', fieldnames=TSV_FIELDNAMES)

        # Loop all the viewpoints in the simulator
        viewpointIds = load_viewpointids()
        viewpointIds = viewpointIds[1645:]
        for scanId, viewpointId in viewpointIds:
            t_render.tic()
            # Loop all discretized views from this location
            blobs = []
            detections = np.empty([VIEWPOINT_SIZE, CLASS_SIZE*4], dtype=np.float32)

            for ix in range(VIEWPOINT_SIZE):
                # print(ix)
                if ix == 0:
                    sim.newEpisode([scanId], [viewpointId], [0], [math.radians(-30)])
                elif ix % 12 == 0:
                    sim.makeAction([0], [1.0], [1.0])
                else:
                    sim.makeAction([0], [1.0], [0])

                state = sim.getState()[0]
                assert state.viewIndex == ix

                # Transform and save generated image
                input_img = np.array(state.rgb, copy=False)
                input_img = np.transpose(input_img, (2, 0, 1))
                input_img = torch.from_numpy(input_img)
                input_img = input_img.type('torch.FloatTensor')

                blobs.append(input_img)

            t_render.toc()
            t_net.tic()

            viewpoint_data = DataLoader(blobs, batch_size=BATCH_SIZE, shuffle=False)


            for i_batch, batch in enumerate(viewpoint_data):
                with torch.no_grad():
                    # print("batch: {}".format(batch.shape))
                    output = darknet(batch)
                    output = non_max_suppression(output, 80, 0.8, 0.4)
                    q = quadrants(output[0])
                    detections[i_batch * BATCH_SIZE:(i_batch + 1) * BATCH_SIZE, :] = q

            writer.writerow({
                'scanId': scanId,
                'viewpointId': viewpointId,
                'image_w': WIDTH,
                'image_h': HEIGHT,
                'vfov': VFOV,
                'detections': base64.b64encode(detections)
            })
            count += 1
            t_net.toc()
            if count % 1 == 0:
                print 'Processed %d / %d viewpoints, %.1fs avg render time, %.1fs avg net time, projected %.1f hours' % \
                (count, len(viewpointIds), t_render.average_time, t_net.average_time,
                 (t_render.average_time + t_net.average_time) * len(viewpointIds) / 3600)


def read_tsv(infile):
    # Verify we can read a tsv
    in_data = []
    with open(infile, "r+b") as tsv_in_file:
        reader = csv.DictReader(tsv_in_file, delimiter='\t', fieldnames=TSV_FIELDNAMES)
        for item in reader:
            item['image_h'] = int(item['image_h'])
            item['image_w'] = int(item['image_w'])
            item['vfov'] = int(item['vfov'])
            item['detections'] = np.frombuffer(base64.decodestring(item['detections']),
                                             dtype=np.float32).reshape((VIEWPOINT_SIZE, FEATURE_SIZE, CLASS_SIZE))
            in_data.append(item)
    return in_data


if __name__ == "__main__":
    build_tsv()
    data = read_tsv(OUTFILE)
    print
    'Completed %d viewpoints' % len(data)

