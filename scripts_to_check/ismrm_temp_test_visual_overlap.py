#!/usr/bin/env python

from __future__ import division

import argparse
import os
import pickle
import logging

from dipy.viz import window, actor

import tractometer.pipeline_helper as helper
from tractometer.pipeline_helper import mkdir
import tractometer.ismrm_metrics as metrics
from tractometer.utils.attribute_computer import get_attribs_for_file,\
                                                 load_attribs

from tractometer.io.streamlines import get_tracts_voxel_space_for_dipy


###############
# Script part #
###############
DESCRIPTION = 'Scoring script for ISMRM tractography challenge.\n\n' \
              'Dissociated from the basic scoring.py because the behaviors\n' \
              'and prerequisite are not the same.\n' \
              'Once behaviors are uniformized (if they ever are), we could merge.'


def _show_bundles(tractogram_fname, bundle_fname, tract_attribs,
                  bundle_attribs, ref_anat_fname):
    tracto_gen = get_tracts_voxel_space_for_dipy(tractogram_fname,
                                                 ref_anat_fname,
                                                 tract_attribs)
    #tracto_strl = [s for s in tracto_gen]
    tracto_strl = []
    cnt = 0
    for s in tracto_gen:
        if cnt > 20000:
            break
        cnt += 1
        tracto_strl.append(s)

    gt_gen = get_tracts_voxel_space_for_dipy(bundle_fname, ref_anat_fname,
                                             bundle_attribs)
    gt_strl = [s for s in gt_gen]

    renderer = window.Renderer()
    stream_actor = actor.line(gt_strl, (1.0, 0.0, 0.0))
    renderer.add(stream_actor)

    stream_actor1 = actor.line(tracto_strl)
    renderer.add(stream_actor1)

    show_m = window.ShowManager(renderer, size=(1000, 1000))
    show_m.initialize()

    global shown
    shown = True

    def key_press_show(obj, event):
        key = obj.GetKeySym()

        global shown

        if key == 't' or key == 'T':
            print('Hiding / showing gt bundle')
            shown = not shown
            print(shown)

            if not shown:
                renderer.rm(stream_actor)
            else:
                renderer.add(stream_actor)

            show_m.render()

    show_m.iren.AddObserver('KeyPressEvent', key_press_show)
    show_m.render()
    show_m.start()
    #window.show(renderer, size=(1000, 1000), reset_camera=False)


def buildArgsParser():
    p = argparse.ArgumentParser(description=DESCRIPTION,
                                formatter_class=argparse.RawTextHelpFormatter)

    p.add_argument('tractogram', action='store',
                   metavar='TRACTS', type=str, help='Tractogram file')

    p.add_argument('bundle',   action='store',
                   metavar='GT_BUNDLE',  type=str,
                   help='GT bundle to display')

    p.add_argument('metadata_file', action='store',
                   metavar='SUBMISSIONS_ATTRIBUTES', type=str,
                   help='attributes file of the submissions. ' +\
                        'Needs to contain the orientation.\n' +\
                        'Normally, use metadata/ismrm_challenge_2015/' +\
                        'anon_submissions_attributes.json.\n' +\
                        'Can be computed with ' +\
                        'ismrm_compute_submissions_attributes.py.')

    p.add_argument('basic_bundles_attribs', action='store',
                   metavar='GT_ATTRIBUTES', type=str,
                   help='attributes of the basic bundles. ' +\
                        'Same format as SUBMISSIONS_ATTRIBUTES')

    p.add_argument('ref_anat', action='store', metavar='REF_ANAT', type=str,
                   help='reference anat')
    p.add_argument('--ori', action='store', metavar='ORIENTATION', type=str,
                   choices=['LPS', 'RAS'],
                   help='Provide orientation for tractogram. Will not use metadata_file')

    # p.add_argument('out_dir',    action='store',
    #                metavar='OUT_DIR',  type=str,
    #                help='directory where to send score files')
    #
    # p.add_argument('version', action='store',
    #                metavar='ALGO_VERSION', choices=range(1,5),
    #                type=int,
    #                help='version of the algorithm to use.\n' +
    #                     'choices:\n  1: VC: auto_extract -> VCWP candidates ' +
    #                     '-> IC -> remove from VCWP -> rest = NC\n' +
    #                     '  2: Extract NC from whole, then do as 1. (NOT IMPLEMENTED)\n' +
    #                     '  3: Classical pipeline, no auto_extract\n' +
    #                     '  4: Do as 1, but assign ICs to as many IB as they can.')
    #
    # p.add_argument('--save_tracts', action='store_true',
    #                help='save the segmented streamlines')
    # p.add_argument('--save_ib', action='store_true',
    #                help='save IB independently.')
    # p.add_argument('--save_vb', action='store_true',
    #                help='save VB independently.')
    # p.add_argument('--save_vcwp', action='store_true',
    #                help='save VCWP independently.')
    #
    # #Other
    # p.add_argument('-f', dest='is_forcing', action='store_true',
    #                required=False, help='overwrite output files')
    # p.add_argument('-v', dest='is_verbose', action='store_true',
    #                required=False, help='produce verbose output')

    return p


def main():
    parser = buildArgsParser()
    args = parser.parse_args()

    tractogram = args.tractogram
    gt_bundle = args.bundle
    attribs_file = args.metadata_file

    if not os.path.isfile(tractogram):
        parser.error('"{0}" must be a file!'.format(tractogram))

    if not os.path.isfile(gt_bundle):
        parser.error('"{0}" must be a file!'.format(gt_bundle))

    if not args.ori and not os.path.isfile(attribs_file):
        parser.error('"{0}" must be a file!'.format(attribs_file))

    if not os.path.isfile(args.basic_bundles_attribs):
        parser.error('"{0}" is not a file!'.format(args.basic_bundles_attribs))

    if not args.ori:
        tracts_attribs = get_attribs_for_file(attribs_file, os.path.basename(tractogram))
    else:
        tracts_attribs = {'orientation': args.ori}
    #basic_bundles_attribs = load_attribs(args.basic_bundles_attribs)
    gt_bundle_attribs = get_attribs_for_file(args.basic_bundles_attribs,
                                             os.path.basename(gt_bundle))

    _show_bundles(tractogram, gt_bundle, tracts_attribs, gt_bundle_attribs,
                  args.ref_anat)


if __name__ == "__main__":
    main()
