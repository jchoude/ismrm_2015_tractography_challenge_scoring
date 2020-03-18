#!/usr/bin/env python

from __future__ import division

import argparse
from collections import Counter
import glob
import logging
import os
import pickle
import random

import dipy.segment.quickbundles as qb
from dipy.tracking.metrics import length as slength
from tractconverter.formats.tck import TCK

from tractometer.io.streamlines import (get_tracts_voxel_space_for_dipy,
                                        save_tracts_tck_from_dipy_voxel_space)
from tractometer.metrics.invalid_connections import get_closest_roi_pairs_for_all_streamlines
import tractometer.pipeline_helper as helper
from tractometer.pipeline_helper import mkdir
from tractometer.utils.filenames import get_root_image_name

import nibabel as nb
import numpy as np


###############
# Script part #
###############
DESCRIPTION = 'Temporary scoring script for ISMRM tractography challenge.\n\n' \
              'Computes the IB and NC scores from precomputed ICs, NCs and \n' \
              'VCWPs files. Expects them to be from technique 1 or 4.\n' \
              'Once this type of technique is merged in scoring, remove this script.'


def buildArgsParser():
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument('ic_tractogram', action='store',
                   metavar='TRACTS', type=str,
                   help='IC tractogram name. Other file names will be '
                        'extrapolated from this one.')
    p.add_argument('score_file', action='store', metavar='SCORE', type=str,
                   help='Score file for the current tractogram.')

    p.add_argument('base_dir',   action='store',
                   metavar='BASE_DIR',  type=str,
                   help='base directory for scoring data')

    p.add_argument('out_dir',    action='store',
                   metavar='OUT_DIR',  type=str,
                   help='directory where to send results. Must not contain score_file')
    p.add_argument('--save_tracts', action='store_true',
                   help='save the segmented streamlines')

    #Other
    p.add_argument('-f', dest='is_forcing', action='store_true',
                   required=False, help='overwrite output files')
    p.add_argument('-v', dest='is_verbose', action='store_true',
                   required=False, help='produce verbose output')

    return p


def main():
    parser = buildArgsParser()
    args = parser.parse_args()

    ic_tractogram = args.ic_tractogram
    base_dir = args.base_dir
    out_dir = args.out_dir

    isForcing = args.is_forcing
    isVerbose = args.is_verbose

    if isVerbose:
        helper.VERBOSE = True
        logging.basicConfig(level=logging.DEBUG)

    if not os.path.isdir(out_dir):
        parser.error('Output directory does not exist.')

    # TODO cleanup of outputs for current submission if they exist
    segmented_dir = os.path.join(out_dir, 'segmented/')
    if not os.path.isdir(segmented_dir):
        mkdir(segmented_dir)

    scores_dir = os.path.join(out_dir, 'scores/')
    if not os.path.isdir(scores_dir):
        mkdir(scores_dir)

    vcwp_tractogram = ic_tractogram.replace('_IC.', '_VCWP.')
    nc_tractogram = ic_tractogram.replace('_IC.', '_NC.')
    candidate_files = [ic_tractogram, nc_tractogram, vcwp_tractogram]

    for f in candidate_files:
        if not os.path.isfile(f):
            parser.error('"{0}" must be a file!'.format(f))

    if not os.path.isdir(base_dir):
        parser.error('"{0}" must be a directory!'.format(base_dir))

    if not os.path.isfile(args.score_file):
        parser.error('Input score file does not exist.')

    if os.path.join(scores_dir, os.path.basename(args.score_file)) == \
        args.score_file:
        parser.error('Input score file would be overwritten on output. Not allowed.')

    # New algorithm
    # Step 1: merge NC, IC, VCWP
    # Step 2: remove streamlines shorter than threshold (currently 35)
    # Step 3: apply Quickbundle with a distance threshold of 20
    # Step 4: remove singletons
    # Step 5: assign to closest ROIs pair

    # Step 1 and 2 are merged to shrink processing time
    merged_streamlines = []
    short_streamlines = []
    masks_dir = base_dir + "/masks/"
    wm_file = os.path.join(masks_dir, "wm.nii.gz")
    attr = {"orientation": "RAS"}
    length_thres = 35.

    for f in candidate_files:
        strl_gen = get_tracts_voxel_space_for_dipy(f, wm_file, attr)
        for s in strl_gen:
            if slength(s) >= length_thres:
                merged_streamlines.append(s.astype('f4'))
            else:
                short_streamlines.append(s.astype('f4'))

    logging.info('Found {} candidate IC'.format(len(merged_streamlines)))
    logging.info('Found {} streamlines that were too short'.format(len(short_streamlines)))

    # Fix seed to always generate the same output
    # Shuffle to try to reduce the ordering dependency for QB
    random.seed(0.2)
    random.shuffle(merged_streamlines)

    # Step 3
    # TODO threshold on distance as arg
    out_data = qb.QuickBundles(merged_streamlines,
                               dist_thr=20.,
                               pts=12)
    clusters = out_data.clusters()

    logging.info("Found {} different IB clusters".format(len(clusters)))

    # Step 4 and 5 done at same time
    rois_masks_filenames = glob.glob(os.path.join(masks_dir, 'rois', '*.nii.gz'))
    rois_info = []

    # TODO this should be better handled
    for roi_fname in rois_masks_filenames:
        rois_info.append((get_root_image_name(roi_fname),
                          np.array(np.where(nb.load(roi_fname).get_data())).T))

    all_ics_closest_pairs = get_closest_roi_pairs_for_all_streamlines(merged_streamlines, rois_info)

    ib_pairs = {}
    ic_counts = 0
    for c_idx, c in enumerate(clusters):
        closest_for_cluster = [all_ics_closest_pairs[i] for i in clusters[c]['indices']]

        if len(clusters[c]['indices']) > 1:
            ic_counts += len(clusters[c]['indices'])
            occurences = Counter(closest_for_cluster)

            # TODO handle either an equality or maybe a range
            most_frequent = occurences.most_common(1)[0][0]

            val = ib_pairs.get(most_frequent)
            if val is None:
                # Check if flipped pair exists
                val1 = ib_pairs.get((most_frequent[1], most_frequent[0]))
                if val1 is not None:
                    val1.append(c_idx)
                else:
                    ib_pairs[most_frequent] = [c_idx]
            else:
                val.append(c_idx)
        else:
            short_streamlines.append(merged_streamlines[clusters[c]['indices'][0]])

    sub_basename = os.path.basename(ic_tractogram).rstrip('_IC.tck')

    for k, v in ib_pairs.iteritems():
        if args.save_tracts:
            out_strl = []
            for c_idx in v:
                out_strl.extend([s for s in np.array(merged_streamlines)[clusters[c_idx]['indices']]])

            out_ib_name = "{}_{}_{}.tck".format(sub_basename, k[0], k[1])
            out_fname = os.path.join(segmented_dir, out_ib_name)

            out_file = TCK.create(out_fname)
            save_tracts_tck_from_dipy_voxel_space(out_file, wm_file, out_strl)

    if len(short_streamlines) > 0 and args.save_tracts:
        out_nc_fname = os.path.join(segmented_dir, '{}_NC.tck'.format(sub_basename))
        out_file = TCK.create(out_nc_fname)
        save_tracts_tck_from_dipy_voxel_space(out_file, wm_file, short_streamlines)

    with open(args.score_file) as scores_file:
        original_scores = pickle.load(scores_file)

    updated_scores = original_scores
    updated_scores['IB'] = len(ib_pairs.keys())
    updated_scores['VCWP'] = 0
    updated_scores['IC'] = ic_counts / original_scores['total_streamlines_count']
    updated_scores['NC'] = len(short_streamlines) / original_scores['total_streamlines_count']
    updated_scores['algo_version'] = 5

    with open(os.path.join(scores_dir, os.path.basename(args.score_file)), 'w') as scores_file:
        pickle.dump(updated_scores, scores_file)


if __name__ == "__main__":
    main()
