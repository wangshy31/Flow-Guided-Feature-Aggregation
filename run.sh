#!/usr/bin/env sh
now=$(date +"%Y%m%d_%H%M%S")
python experiments/fgfa_rfcn/fgfa_rfcn_end2end_train_test.py --cfg experiments/fgfa_rfcn/cfgs/resnet_v1_101_flownet_imagenet_vid_rfcn_end2end_ohem.yaml 2>&1 | tee log/test-$now.log
