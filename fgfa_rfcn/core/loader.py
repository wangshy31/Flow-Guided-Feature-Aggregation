# --------------------------------------------------------
# Flow-Guided Feature Aggregation
# Copyright (c) 2016 by Contributors
# Copyright (c) 2017 Microsoft
# Licensed under The Apache-2.0 License [see LICENSE for details]
# Modified by Yuqing Zhu, Shuhao Fu, Xizhou Zhu, Yuwen Xiong
# --------------------------------------------------------

import numpy as np
import mxnet as mx
from mxnet.executor_manager import _split_input_slice

from config.config import config
from utils.image import tensor_vstack
from rpn.rpn import get_rpn_testbatch, get_rpn_triple_batch, assign_anchor
from rcnn import get_rcnn_testbatch, get_rcnn_batch

class TestLoader(mx.io.DataIter):
    def __init__(self, roidb, config, batch_size=1, shuffle=False,
                 has_rpn=False):
        super(TestLoader, self).__init__()

        # save parameters as properties
        self.cfg = config
        self.roidb = roidb
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.has_rpn = has_rpn

        # infer properties from roidb
        self.size = np.sum([x['frame_seg_len'] for x in self.roidb])
        self.index = np.arange(self.size)

        # decide data and label names (only for training)
        #self.data_name = ['data', 'im_info', 'data_cache', 'feat_cache']
        self.data_name = ['data', 'data_bef', 'data_pattern', 'im_info', \
                          'max_mem_block5', \
                          'filename', 'filename_pre', 'pre_filename', 'pre_filename_pre']
        self.label_name = None

        #
        self.cur_roidb_index = 0
        self.cur_frameid = 0
        self.cur_seg_len = 0
        self.key_frame_flag = -1

        # status variable for synchronization between get_data and get_label
        self.cur = 0
        self.data = None
        self.label = []
        self.im_info = None

        # get first batch to fill in provide_data and provide_label
        self.reset()
        self.get_init_batch()

    @property
    def provide_data(self):
        return [[(k, v.shape) for k, v in zip(self.data_name, idata)] for idata in self.data]

    @property
    def provide_label(self):
        return [None for _ in range(len(self.data))]

    @property
    def provide_data_single(self):
        return [(k, v.shape) for k, v in zip(self.data_name, self.data[0])]

    @property
    def provide_label_single(self):
        return None

    def reset(self):
        self.cur = 0
        if self.shuffle:
            np.random.shuffle(self.index)

    def iter_next(self):
        return self.cur < self.size

    def next(self):
        if self.iter_next():
            self.get_batch()
            self.cur += self.batch_size
            self.cur_frameid += 1
            if self.cur_frameid == self.cur_seg_len:
                self.cur_roidb_index += 1
                self.cur_frameid = 0
                self.key_frame_flag = 1
            return self.im_info, self.key_frame_flag, mx.io.DataBatch(data=self.data, label=self.label,
                                   pad=self.getpad(), index=self.getindex(),
                                   provide_data=self.provide_data, provide_label=self.provide_label)
        else:
            raise StopIteration

    def getindex(self):
        return self.cur / self.batch_size

    def getpad(self):
        if self.cur + self.batch_size > self.size:
            return self.cur + self.batch_size - self.size
        else:
            return 0

    def get_batch(self):
        cur_roidb = self.roidb[self.cur_roidb_index].copy()
        cur_roidb['image'] = cur_roidb['pattern'] % self.cur_frameid
        self.cur_seg_len = cur_roidb['frame_seg_len']
        cur_roidb_index = []
        cur_roidb_index.append(self.cur_roidb_index)
        cur_frameid = []
        cur_frameid.append(self.cur_frameid)
        data, label, im_info = get_rpn_testbatch([cur_roidb], self.cfg, cur_roidb_index, cur_frameid)
        if self.cur_frameid == 0: # new video
                self.key_frame_flag = 0
        else:       # normal frame
            self.key_frame_flag = 2

        extend_data = [{'data': data[0]['data'] ,
                        'data_bef': data[0]['data_bef'],
                        'data_pattern': data[0]['data_pattern'],
                        'im_info': data[0]['im_info'],
                        'filename_pre': data[0]['filename_pre'],
                        'filename': data[0]['filename'],
                        'pre_filename_pre': data[0]['pre_filename_pre'],
                        'pre_filename': data[0]['pre_filename'],
                        #'max_mem_block2': data[0]['max_mem_block2'],
                        #'max_mem_block3': data[0]['max_mem_block3'],
                        #'max_mem_block4': data[0]['max_mem_block4'],
                        'max_mem_block5': data[0]['max_mem_block5']
                        }]
        self.data = [[mx.nd.array(extend_data[i][name]) for name in self.data_name] for i in xrange(len(data))]
        self.im_info = im_info

    def get_init_batch(self):
        cur_roidb = self.roidb[self.cur_roidb_index].copy()
        cur_roidb['image'] = cur_roidb['pattern'] % self.cur_frameid
        self.cur_seg_len = cur_roidb['frame_seg_len']
        cur_roidb_index = []
        cur_roidb_index.append(self.cur_roidb_index)
        cur_frameid = []
        cur_frameid.append(self.cur_frameid)
        data, label, im_info = get_rpn_testbatch([cur_roidb], self.cfg, cur_roidb_index, cur_frameid)
        if self.cur_frameid == 0: # new frame
                self.key_frame_flag = 0
        else:       # normal frame
            self.key_frame_flag = 2

        feat_stride = float(self.cfg.network.RCNN_FEAT_STRIDE)
        extend_data = [{'data': data[0]['data'] ,
                        'data_bef': data[0]['data_bef'],
                        'data_pattern': data[0]['data_pattern'],
                        'im_info': data[0]['im_info'],
                        'filename_pre': data[0]['filename_pre'],
                        'filename': data[0]['filename'],
                        'pre_filename_pre': data[0]['pre_filename_pre'],
                        'pre_filename': data[0]['pre_filename'],
                        #'max_mem_block2': data[0]['max_mem_block2'],
                        #'max_mem_block3': data[0]['max_mem_block3'],
                        #'max_mem_block4': data[0]['max_mem_block4'],
                        'max_mem_block5': data[0]['max_mem_block5']
                        }]
                        #'data_cache': np.zeros((19, 3, max([v[0] for v in self.cfg.SCALES]), max([v[1] for v in self.cfg.SCALES]))),
                        #'feat_cache': np.zeros((19, self.cfg.network.FGFA_FEAT_DIM,
                                                #np.ceil(max([v[0] for v in self.cfg.SCALES]) / feat_stride).astype(np.int),
                                                #np.ceil(max([v[1] for v in self.cfg.SCALES]) / feat_stride).astype(np.int)))}]
        self.data = [[mx.nd.array(extend_data[i][name]) for name in self.data_name] for i in xrange(len(data))]
        self.im_info = im_info

class AnchorLoader(mx.io.DataIter):

    def __init__(self, feat_sym, roidb, cfg, batch_size=1, shuffle=False, ctx=None, work_load_list=None,
                 feat_stride=16, anchor_scales=(8, 16, 32), anchor_ratios=(0.5, 1, 2), allowed_border=0,
                 aspect_grouping=False, normalize_target=False, bbox_mean=(0.0, 0.0, 0.0, 0.0),
                 bbox_std=(0.1, 0.1, 0.4, 0.4)):
        """
        This Iter will provide roi data to Fast R-CNN network
        :param feat_sym: to infer shape of assign_output
        :param roidb: must be preprocessed
        :param batch_size: must divide BATCH_SIZE(128)
        :param shuffle: bool
        :param ctx: list of contexts
        :param work_load_list: list of work load
        :param aspect_grouping: group images with similar aspects
        :param normalize_target: normalize rpn target
        :param bbox_mean: anchor target mean
        :param bbox_std: anchor target std
        :return: AnchorLoader
        """
        super(AnchorLoader, self).__init__()

        # save parameters as properties
        self.feat_sym = feat_sym
        self.roidb = roidb
        self.cfg = cfg
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.ctx = ctx
        if self.ctx is None:
            self.ctx = [mx.cpu()]
        self.work_load_list = work_load_list
        self.feat_stride = feat_stride
        self.anchor_scales = anchor_scales
        self.anchor_ratios = anchor_ratios
        self.allowed_border = allowed_border
        self.aspect_grouping = aspect_grouping
        self.normalize_target = normalize_target
        self.bbox_mean = bbox_mean
        self.bbox_std = bbox_std
        self.pre_list = np.zeros(len(self.ctx), dtype=np.int32)

        # infer properties from roidb
        self.size = len(roidb)
        self.index = np.arange(self.size)

        # decide data and label names
        if config.TRAIN.END2END:
            #self.data_name = ['data', 'filename_pre', 'filename', 'data_bef', 'data_aft', 'im_info', 'gt_boxes']
            self.data_name = ['data', 'data_bef', 'data_pattern', 'im_info', 'gt_boxes', \
                              'max_mem_block5', \
                              'filename', 'filename_pre', 'pre_filename', 'pre_filename_pre']
        else:
            self.data_name = ['data']
        self.label_name = ['label', 'bbox_target', 'bbox_weight']

        # status variable for synchronization between get_data and get_label
        self.cur = 0
        self.batch = None
        self.data = None
        self.label = None

        # get first batch to fill in provide_data and provide_label
        self.reset()
        self.get_batch_individual()

    @property
    def provide_data(self):
        #tmp1 = [[(k, v.shape) for k, v in zip(self.data_name, self.data[i])] for i in xrange(len(self.data))]
        #print 'tmp1!!!!'
        #print tmp1
        tmp = []
        for i in xrange(len(self.data)):
            tmp2 = []
            for k, v in zip(self.data_name, self.data[i]):
                tmp2.append((k, v.shape))
            tmp.append(tmp2)
            #tmp.append([(k, v.shape) for k, v in zip(self.data_name, self.data[i])])
        return tmp


    @property
    def provide_label(self):
        return [[(k, v.shape) for k, v in zip(self.label_name, self.label[i])] for i in xrange(len(self.data))]

    @property
    def provide_data_single(self):
        return [(k, v.shape) for k, v in zip(self.data_name, self.data[0])]

    @property
    def provide_label_single(self):
        return [(k, v.shape) for k, v in zip(self.label_name, self.label[0])]

    def shuffle_seg(self):
        image_list = []
        pre = ''
        tmp_list = []
        for i in range(len(self.roidb)):
            line = self.roidb[i]['image'].split('/')[-2]
            if self.roidb[i]['pattern']=='':
                if len(tmp_list) != 0:
                    image_list.append(tmp_list)
                tmp_list = []
                image_list.append([i])
            else:
                if line == pre:
                    if len(tmp_list)<10:
                        tmp_list.append(i)
                    else:
                        image_list.append(tmp_list)
                        tmp_list = []
                        tmp_list.append(i)
                else:
                    if len(tmp_list) != 0:
                        image_list.append(tmp_list)
                        tmp_list = []
                        tmp_list.append(i)
                    else:
                        tmp_list.append(i)
            pre = line
        if len(tmp_list) != 0:
            image_list.append(tmp_list)
        np.random.shuffle(image_list)
        with open('list_org.txt','w') as f:
            for i in self.index:
                f.write(str(i)+'\n')

        self.index = []
        with open('list_shuffle.txt','w') as f:
            for i in image_list:
                for j in i:
                    self.index.append(j)
                    f.write(str(j)+"\n")




    def reset(self):
        self.cur = 0
        if self.shuffle:
            if self.aspect_grouping:
                widths = np.array([r['width'] for r in self.roidb])
                heights = np.array([r['height'] for r in self.roidb])
                horz = (widths >= heights)
                vert = np.logical_not(horz)
                horz_inds = np.where(horz)[0]
                vert_inds = np.where(vert)[0]
                inds = np.hstack((np.random.permutation(horz_inds), np.random.permutation(vert_inds)))
                print 'inds: ', inds
                extra = inds.shape[0] % self.batch_size
                inds_ = np.reshape(inds[:-extra], (-1, self.batch_size))
                print 'inds_ ',inds_
                row_perm = np.random.permutation(np.arange(inds_.shape[0]))
                print 'row_perm: ', row_perm
                inds[:-extra] = np.reshape(inds_[row_perm, :], (-1,))
                self.index = inds
                print 'self.index: ', self.index
            else:
                self.shuffle_seg()
                #np.random.shuffle(self.index)

    def iter_next(self):
        return self.cur + self.batch_size <= self.size

    def next(self):
        if self.iter_next():
            self.get_batch_individual()
            self.cur += self.batch_size
            return mx.io.DataBatch(data=self.data, label=self.label,
                                   pad=self.getpad(), index=self.getindex(),
                                   provide_data=self.provide_data, provide_label=self.provide_label)
        else:
            raise StopIteration

    def getindex(self):
        return self.cur / self.batch_size

    def getpad(self):
        if self.cur + self.batch_size > self.size:
            return self.cur + self.batch_size - self.size
        else:
            return 0

    def infer_shape(self, max_data_shape=None, max_label_shape=None):
        """ Return maximum data and label shape for single gpu """
        if max_data_shape is None:
            max_data_shape = []
        if max_label_shape is None:
            max_label_shape = []
        max_shapes = dict(max_data_shape + max_label_shape)
        input_batch_size = max_shapes['data'][0]
        im_info = [[max_shapes['data'][2], max_shapes['data'][3], 1.0]]
        _, feat_shape, _ = self.feat_sym.infer_shape(**max_shapes)
        label = assign_anchor(feat_shape[0], np.zeros((0, 5)), im_info, self.cfg,
                              self.feat_stride, self.anchor_scales, self.anchor_ratios, self.allowed_border,
                              self.normalize_target, self.bbox_mean, self.bbox_std)
        label = [label[k] for k in self.label_name]
        label_shape = [(k, tuple([input_batch_size] + list(v.shape[1:]))) for k, v in zip(self.label_name, label)]
        return max_data_shape, label_shape

    def get_batch(self):
        # slice roidb
        cur_from = self.cur
        cur_to = min(cur_from + self.batch_size, self.size)
        roidb = [self.roidb[self.index[i]] for i in range(cur_from, cur_to)]
        pre_roidb = [self.roidb[self.index[i]]['frame_seg_id'] for i in self.pre_list]

        # decide multi device slice
        work_load_list = self.work_load_list
        ctx = self.ctx
        if work_load_list is None:
            work_load_list = [1] * len(ctx)
        assert isinstance(work_load_list, list) and len(work_load_list) == len(ctx), \
            "Invalid settings for work load. "
        slices = _split_input_slice(self.batch_size, work_load_list)

        # get testing data for multigpu
        data_list = []
        label_list = []
        for islice in slices:
            iroidb = [roidb[i] for i in range(islice.start, islice.stop)]
            ipre_roidb = [pre_roidb[i] for i in range(islice.start, islice.stop)]
            data, label = get_rpn_triple_batch(iroidb, self.cfg, ipre_roidb)
            data_list.append(data)
            label_list.append(label)

        # pad data first and then assign anchor (read label)
        data_tensor = tensor_vstack([batch['data'] for batch in data_list])
        for data, data_pad in zip(data_list, data_tensor):
            data['data'] = data_pad[np.newaxis, :]

        new_label_list = []
        for data, label in zip(data_list, label_list):
            # infer label shape
            data_shape = {k: v.shape for k, v in data.items()}
            del data_shape['im_info']
            _, feat_shape, _ = self.feat_sym.infer_shape(**data_shape)
            feat_shape = [int(i) for i in feat_shape[0]]

            # add gt_boxes to data for e2e
            data['gt_boxes'] = label['gt_boxes'][np.newaxis, :, :]

            # assign anchor for label
            label = assign_anchor(feat_shape, label['gt_boxes'], data['im_info'], self.cfg,
                                  self.feat_stride, self.anchor_scales,
                                  self.anchor_ratios, self.allowed_border,
                                  self.normalize_target, self.bbox_mean, self.bbox_std)
            new_label_list.append(label)

        all_data = dict()
        for key in self.data_name:
            all_data[key] = tensor_vstack([batch[key] for batch in data_list])

        all_label = dict()
        for key in self.label_name:
            pad = -1 if key == 'label' else 0
            all_label[key] = tensor_vstack([batch[key] for batch in new_label_list], pad=pad)

        self.data = [mx.nd.array(all_data[key]) for key in self.data_name]
        self.label = [mx.nd.array(all_label[key]) for key in self.label_name]

    def get_batch_individual(self):
        cur_from = self.cur
        cur_to = min(cur_from + self.batch_size, self.size)

        assert cur_from % len(self.ctx) == 0, "cur_from mod len(ctx) must equal to 0"
        range_list = []
        tmplen = self.size / len(self.ctx)
        for i in range(len(self.ctx)):
            tmpindex = (i*tmplen + cur_from / len(self.ctx))%self.size
            range_list.append(tmpindex)

        #roidb = [self.roidb[self.index[i]] for i in range(cur_from, cur_to)]
        pre_roidb = [self.roidb[self.index[i]]['frame_seg_id'] for i in self.pre_list]
        self.pre_list = range_list
        roidb = [self.roidb[self.index[i]] for i in range_list]
        # decide multi device slice
        work_load_list = self.work_load_list
        ctx = self.ctx
        if work_load_list is None:
            work_load_list = [1] * len(ctx)
        assert isinstance(work_load_list, list) and len(work_load_list) == len(ctx), \
            "Invalid settings for work load. "
        slices = _split_input_slice(self.batch_size, work_load_list)
        rst = []
        for idx, islice in enumerate(slices):
            iroidb = [roidb[i] for i in range(islice.start, islice.stop)]
            ipre_roidb = [pre_roidb[i] for i in range(islice.start, islice.stop)]
            rst.append(self.parfetch(iroidb, ipre_roidb))

        all_data = [_['data'] for _ in rst]
        all_label = [_['label'] for _ in rst]
        self.data = [[mx.nd.array(data[key]) for key in self.data_name] for data in all_data]
        self.label = [[mx.nd.array(label[key]) for key in self.label_name] for label in all_label]

    def parfetch(self, iroidb, ipre_roidb):
        # get testing data for multigpu
        data, label = get_rpn_triple_batch(iroidb, self.cfg, ipre_roidb)
        data_shape = {k: v.shape for k, v in data.items()}
        #data_shape['pre_filename_pre'] = (1,)
        #data_shape['pre_filename'] = (1,)
        del data_shape['im_info']
        #del data_shape['filename']
        #del data_shape['filename_pre']
        _, feat_shape, _ = self.feat_sym.infer_shape(**data_shape)
        feat_shape = [int(i) for i in feat_shape[0]]

        # add gt_boxes to data for e2e
        data['gt_boxes'] = label['gt_boxes'][np.newaxis, :, :]

        # assign anchor for label
        label = assign_anchor(feat_shape, label['gt_boxes'], data['im_info'], self.cfg,
                              self.feat_stride, self.anchor_scales,
                              self.anchor_ratios, self.allowed_border,
                              self.normalize_target, self.bbox_mean, self.bbox_std)
        return {'data': data, 'label': label}

