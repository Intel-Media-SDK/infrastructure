# -*- coding: utf-8 -*-

# Copyright (c) 2018 Intel Corporation
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.


import enum
from pathlib import Path
from collections import namedtuple
import hevc_fei_smoke_test


class ReturnCode(enum.Enum):
    ERROR_SUCCESS = 0
    ERROR_TEST_FAILED = 1
    ERROR_ACCESS_DENIED = 2


def get_samples_folder():
    for samples_folder in POSSIBLE_SAMPLES_FOLDER:
        if samples_folder.exists():
            print(f'Samples found in: {samples_folder}')
            return samples_folder #success

    print(f'Samples were not found.')
    print(f'Put samples to the one of the following locations and restart:')
    print(POSSIBLE_SAMPLES_FOLDER)
    exit(ReturnCode.ERROR_ACCESS_DENIED.value)


# constants
PATH_DIR_NAME = Path(__file__).resolve().parent

MEDIASDK_FOLDER = Path('/opt/intel/mediasdk')

POSSIBLE_SAMPLES_FOLDER = [
    MEDIASDK_FOLDER / 'share' / 'mfx' / 'samples',
    MEDIASDK_FOLDER / 'samples',
]
SAMPLES_FOLDER = get_samples_folder()

ASG = PATH_DIR_NAME / 'asg-hevc'
FEI_EXTRACTOR = PATH_DIR_NAME / 'hevc_fei_extractor'
SAMPLE_FEI = SAMPLES_FOLDER / 'sample_hevc_fei'

PATH_DICT = {'ASG': ASG, 'FEI_EXTRACTOR': FEI_EXTRACTOR, 'SAMPLE_FEI': SAMPLE_FEI}

# parameters of the test stream (key=value)
STREAM = namedtuple('STREAM', ['name', 'w', 'h', 'frames', 'picstruct'])
TEST_STREAM = STREAM(name='test_stream_176x96.yuv', w='176', h='96', frames='100',
                     picstruct='tff')

PATH_TEST_STREAM = PATH_DIR_NAME.parent / f'ted/content/{TEST_STREAM.name}'

# file for log
LOG = hevc_fei_smoke_test.PathPlus(PATH_DIR_NAME / 'res.log')

# path for input and output files
PATH_TO_IO = PATH_DIR_NAME / 'IOFiles'


TEST_CASES_DICT = {
    'Encode': {
        'P frames': {
            'gpb:on':
                {
                    'EMVP_singleRef ME=quarter-pixel cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -f 25 -qp 2 -g 2 '
                                 f'-GopRefDist 1 -gpb:on -NumRefFrame 1 -NumRefActiveP 1 '
                                 f'-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_multiRef ME=quarter-pixel cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -f 25 -qp 2 -g 3 '
                                 f'-GopRefDist 1 -gpb:on -NumRefFrame 2 -NumRefActiveP 2 '
                                 f'-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_singleRef ME=quarter-pixel cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 2 '
                                 f'-GopRefDist 1 -gpb:on -NumRefFrame 1 -NumRefActiveP 1 '
                                 f'-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_multiRef ME=quarter-pixel cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 3 '
                                 f'-GopRefDist 1 -gpb:on -NumRefFrame 2 -NumRefActiveP 2 '
                                 f'-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 3 -x 2'
                                 f' -num_active_P 2 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ]
                },
            'gpb:off':
                {
                    'EMVP_singleRef ME=quarter-pixel cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 2 '
                                 f'-GopRefDist 1 -gpb:off -NumRefFrame 1 -NumRefActiveP 1 '
                                 f'-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_multiRef ME=quarter-pixel cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off '
                                 f'-NumRefFrame 2 -NumRefActiveP 2 -NumPredictorsL0 4 '
                                 f'-NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_singleRef ME=quarter-pixel cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:off '
                                 f'-NumRefFrame 1 -NumRefActiveP 1 -NumPredictorsL0 4 '
                                 f'-NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 2 -x 1 -num_active_P 1 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ],

                    'EMVP_multiRef ME=quarter-pixel cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off '
                                 f'-NumRefFrame 2 -NumRefActiveP 2 -NumPredictorsL0 4 '
                                 f'-NumPredictorsL1 4 -EncodedOrder -encode '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -sub_pel_mode 3 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 70 -split_thres 70'}
                        ]
                }
        },
        'B frames': {
            'gpb:on':
                {
                    'EMVP_singleRef ME=integer cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 32 -x 2 -num_active_P 1 -num_active_BL0 1 -num_active_BL1 1 '
                                 f'-r 4 -log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 0 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 32 -GopRefDist 4 -gpb:on '
                                 f'-NumRefFrame 2 -NumRefActiveP 1 -NumRefActiveBL0 1 '
                                 f'-NumRefActiveBL1 1 -NumPredictorsL0 4 -NumPredictorsL1 4'
                                 f' -encode -EncodedOrder '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 32 -x 2 -num_active_P 1 -num_active_BL0 1 -num_active_BL1 1 '
                                 f'-r 4 -log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 0 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 50 -split_thres 50 -numpredictors 4'}
                        ],
                    'EMVP_multiRef ME=integer cu_size32':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 32 -x 3 -num_active_P 1 -num_active_BL0 2 '
                                 f'-num_active_BL1 1 -r 4 -log2_ctu_size 5 -no_cu_to_pu_split '
                                 f'-max_log2_cu_size 5 -min_log2_cu_size 5 -sub_pel_mode 0 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 32 -GopRefDist 4 -gpb:on '
                                 f'-NumRefFrame 3 -NumRefActiveP 1 -NumRefActiveBL0 2 '
                                 f'-NumRefActiveBL1 1 -NumPredictorsL0 4 -NumPredictorsL1 4'
                                 f' -EncodedOrder -encode -mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 32 -x 3 -num_active_P 1 -num_active_BL0 2 -num_active_BL1 1 '
                                 f'-r 4 -log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 '
                                 f'-min_log2_cu_size 5 -sub_pel_mode 0 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 50 -split_thres 50 -numpredictors 4'}
                        ]
                }
        },
        'P frames \tIntra_inter_mix': {
            'gpb:on':
                {
                    'EMVP_singleRef ME=integer cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                 f'-no_cu_to_pu_split -max_log2_cu_size 4 -min_log2_cu_size 4 '
                                 f'-mvp_block_size 1 -sub_pel_mode 0 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp '
                                 f'-o {{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:on '
                                 f'-NumRefFrame 2 -NumRefActiveP 2 -NumPredictorsL0 4 '
                                 f'-NumPredictorsL1 4 -encode -EncodedOrder '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -mvp_block_size 1 -sub_pel_mode 0 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 80 -split_thres 80 -numpredictors 4'}
                        ]
                },
            'gpb:off':
                {
                    'EMVP_singleRef ME=integer cu_size16':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'ASG':
                                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-o {{path_to_io}}.prmvmvp '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 -gpb_off '
                                 f'-no_cu_to_pu_split -max_log2_cu_size 4 -min_log2_cu_size 4 '
                                 f'-mvp_block_size 1 -gpb_off -sub_pel_mode 0 '
                                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
                            {'SAMPLE_FEI':
                                 f'-i {{path_to_io}}.prmvmvp -o '
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off '
                                 f'-NumRefFrame 2 -NumRefActiveP 2 -NumPredictorsL0 4 '
                                 f'-NumPredictorsL1 4 -encode -EncodedOrder '
                                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.prmvmvp.mvmvp.hevc '
                                 f'{{path_to_io}}_mvmvp.ctustat '
                                 f'{{path_to_io}}_mvmvp.custat'},
                            {'ASG':
                                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-g 3 -x 2 -num_active_P 2 -r 1 -gpb_off '
                                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 4 '
                                 f'-min_log2_cu_size 4 -mvp_block_size 1 -gpb_off -sub_pel_mode 0 '
                                 f'-pak_ctu_file {{path_to_io}}_mvmvp.ctustat '
                                 f'-pak_cu_file {{path_to_io}}_mvmvp.custat '
                                 f'-mv_thres 80 -split_thres 80 -numpredictors 4'}
                        ]
                }
        }
    },
    'Multi-pass PAK':
        {
            'GOP_size-1':
                {
                    'QP-24':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 24 -g 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 24 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 24 -g 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak '
                                 f'-InitialQP 24'}
                        ],
                    'QP-26':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 26 -g 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 26 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 26 -g 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 26'}
                        ],
                    'QP-28':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 28 -g 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 28 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 28 -g 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 28'}
                        ],
                    'QP-31':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 31 -g 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 31 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames}'
                                 f' -w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 31 -g 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 31'}
                        ]
                },
            'GOP_size-2 \t GopRefDist-1':
                {
                    'QP-24':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 24 -g 2 -GopRefDist 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 2 -r 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 24 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -qp 24 -g 2 '
                                 f'-GopRefDist 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 2 -r 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 24'}
                        ],
                    'QP-28':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 28 -g 2 -GopRefDist 1 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 2 -r 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 28 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 28 -g 2 -GopRefDist 1 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 2 -r 1 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 28'}
                        ]
                },
            'GOP_size-5 \t GopRefDist-3':
                {
                    'QP-26':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 26 -g 5 -GopRefDist 3 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 5 -r 3 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 26 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames}'
                                 f' -w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -qp 26 -g 5 '
                                 f'-GopRefDist 3 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 5 -r 3 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 26'}
                        ],
                    'QP-31':
                        [
                            {'case type': hevc_fei_smoke_test.TestCase},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.hevc '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -qp 31 -g 5 '
                                 f'-GopRefDist 3 -encode -EncodedOrder'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.hevc '
                                 f'-multi_pak_str {{path_to_io}}.multipak'},
                            {'ASG':
                                 f'-generate -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 5 -r 3 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_str_file {{path_to_io}}.multipak '
                                 f'-InitialQP 31 -DeltaQP 1 1 2 2 3 3 4 4'},
                            {'SAMPLE_FEI':
                                 f'-i {PATH_TEST_STREAM} '
                                 f'-o {{path_to_io}}.repack '
                                 f'-n {TEST_STREAM.frames}'
                                 f' -w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} '
                                 f'-qp 31 -g 5 -GopRefDist 3 -encode -EncodedOrder '
                                 f'-repackctrl {{path_to_io}}.repakctrl '
                                 f'-repackstat {{path_to_io}}.repakstat'},
                            {'FEI_EXTRACTOR':
                                 f'{{path_to_io}}.repack '
                                 f'-multi_pak_str {{path_to_io}}_repak.multipak'},
                            {'ASG':
                                 f'-verify -gen_repack_ctrl '
                                 f'-n {TEST_STREAM.frames} '
                                 f'-w {TEST_STREAM.w} '
                                 f'-h {TEST_STREAM.h} -g 5 -r 3 '
                                 f'-repack_ctrl_file {{path_to_io}}.repakctrl '
                                 f'-repack_stat_file {{path_to_io}}.repakstat '
                                 f'-repack_str_file {{path_to_io}}_repak.multipak -InitialQP 31'}
                        ]
                }

        },
    'Num_mvpredictors':
        [
            {'case type': hevc_fei_smoke_test.TestCase},
            {'ASG':
                 f'-generate -gen_inter -gen_mv -gen_pred -gen_split '
                 f'-i {PATH_TEST_STREAM} '
                 f'-n {TEST_STREAM.frames} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-o {{path_to_io}}.prmvmvp -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5  '
                 f'-no_cu_to_pu_split -max_log2_cu_size 5 -min_log2_cu_size 5 -sub_pel_mode 3 '
                 f'-pred_file {{path_to_io}}_mvmvp.mvin'},
            {'SAMPLE_FEI':
                 f'-i {{path_to_io}}.prmvmvp '
                 f'-o {{path_to_io}}.prmvmvp.mvmvp_2_NumPredictors.hevc '
                 f'-n {TEST_STREAM.frames} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:on -NumRefFrame 1 -NumRefActiveP 1 '
                 f'-NumPredictorsL0 2 -NumPredictorsL1 2 -encode -EncodedOrder '
                 f'-mvpin {{path_to_io}}_mvmvp.mvin'},
            {'FEI_EXTRACTOR':
                 f'{{path_to_io}}.prmvmvp.mvmvp_2_NumPredictors.hevc '
                 f'{{path_to_io}}_2.ctustat_mvmvp_numpredictors '
                 f'{{path_to_io}}_2.custat_mvmvp_numpredictors'},
            {'ASG':
                 f'-verify -gen_inter -gen_mv -gen_pred -gen_split '
                 f'-n {TEST_STREAM.frames} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-g 2 -x 1 -num_active_P 1 -r 1 -sub_pel_mode 3 '
                 f'-log2_ctu_size 5 -no_cu_to_pu_split -max_log2_cu_size 5 -min_log2_cu_size 5 '
                 f'-pak_ctu_file {{path_to_io}}_2.ctustat_mvmvp_numpredictors '
                 f'-pak_cu_file {{path_to_io}}_2.custat_mvmvp_numpredictors '
                 f'-mv_thres 80 -numpredictors 2'}
        ],
    'PREENC DS':
        [
            {'case type': hevc_fei_smoke_test.TestCase},
            {'SAMPLE_FEI':
                 f'-i {PATH_TEST_STREAM} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-n {TEST_STREAM.frames} '
                 f'-preenc 4 -qp 30 -l 1 -g 30 -GopRefDist 4 -NumRefFrame 4 -bref'}
        ],
    'PREENC + ENCODE':
        [
            {'case type': hevc_fei_smoke_test.TestCase},
            {'SAMPLE_FEI':
                 f'-i {PATH_TEST_STREAM} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-n {TEST_STREAM.frames} '
                 f'-o {{path_to_io}}.hevc '
                 f'-preenc -encode -qp 30 -l 1 -g 30 -GopRefDist 4 -NumRefFrame 4 -bref'}
        ],
    'EncodedOrder':
        [
            {'case type': hevc_fei_smoke_test.TestCaseBitExact},
            {'SAMPLE_FEI':
                 f'-i {PATH_TEST_STREAM} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-n {TEST_STREAM.frames} '
                 f'-o {{path_to_io}}.hevc '
                 f'-f 25 -qp 24 -g 31 -GopRefDist 4 -gpb:on -NumRefFrame 0 -bref -encode '
                 f'-EncodedOrder -DisableQPOffset'},
            {'SAMPLE_FEI':
                 f'-i {PATH_TEST_STREAM} '
                 f'-w {TEST_STREAM.w} '
                 f'-h {TEST_STREAM.h} '
                 f'-n {TEST_STREAM.frames} '
                 f'-o {{path_to_io}}.cmp '
                 f'-f 25 -qp 24 -g 31 -GopRefDist 4 -gpb:on -NumRefFrame 0 -bref -encode '
                 f'-DisableQPOffset'}
        ]
}
