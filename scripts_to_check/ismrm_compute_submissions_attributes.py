#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import os

from tractometer.ismrm_challenge_specific.orientations import \
    guess_tracts_orientation
from tractometer.ismrm_challenge_specific.attribute_types import \
    get_tract_count, get_min_step_size, get_max_step_size

from tractometer.utils.attribute_computer import (load_attribs,
                                                  compute_attrib_files,
                                                  merge_attribs,
                                                  save_attribs)


POSSIBLE_ATTRIBUTES = {'orientation': guess_tracts_orientation,
                       'count': get_tract_count,
                       'min_step': get_min_step_size,
                       'max_step': get_max_step_size}


def _buildArgsParser():
    p = argparse.ArgumentParser(
        formatter_class=argparse.RawTextHelpFormatter,
        description='Compute the submission attributes that might be needed '
                    'by the scoring script.')
    p.add_argument('root_dir', action='store',
                   metavar='DIR', type=str,
                   help='root directory containing all tracts to process')
    p.add_argument('out_file', action='store',
                   metavar='OUT_FILE', type=str,
                   help='path of output json file. Will be appended if exists.')
    p.add_argument('attribute', action='store',
                   metavar='ATTR', choices=POSSIBLE_ATTRIBUTES.keys(),
                   help='type of attribute to be computed. Must be one of:\n' +
                        ', '.join(POSSIBLE_ATTRIBUTES.keys()))
    return p


def main():
    parser = _buildArgsParser()
    args = parser.parse_args()

    if not os.path.isdir(args.root_dir):
        parser.error('"{0}" must be a directory!'.format(args.root_dir))

    orig_attribs = {}
    if os.path.isfile(args.out_file):
        orig_attribs = load_attribs(args.out_file)

    new_attribs = compute_attrib_files(args.root_dir,
                                       POSSIBLE_ATTRIBUTES[args.attribute],
                                       args.attribute)

    orig_attribs = merge_attribs(orig_attribs, new_attribs, overwrite=True)

    save_attribs(args.out_file, orig_attribs)


if __name__ == "__main__":
    main()
