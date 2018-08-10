#!/usr/bin/python

import os
import subprocess
import sys  # for sys.exit()
import errno
import shutil  # for shutil.rmtree
import re
import time
import filecmp
import enum

START_TIME = time.time()

# Link to test stream and reference tools:
# //jfspercbits001.amr.corp.intel.com/shared_outgoing/MSDK_Project/hevc_fei_smoke_test

# constants

PATH_DIR_NAME = os.path.dirname(os.path.abspath(__file__))

# paths to every needed binary
ASG = os.path.normpath(PATH_DIR_NAME + '/asg-hevc')
FEI_EXTRACTOR = os.path.normpath(PATH_DIR_NAME + '/hevc_fei_extractor')
SAMPLE_FEI = os.path.normpath('/opt/intel/mediasdk/samples/sample_hevc_fei')
SAMPLE_ENCODE = os.path.normpath('/opt/intel/mediasdk/samples/sample_encode')
MFX_PLAYER = os.path.normpath(PATH_DIR_NAME + '/mfx_player')

# parameters of the test stream (key:value)
TEST_STREAM = {'name': 'test_stream_176x96.yuv', 'w': '176', 'h': '96', 'frames': '100',
               'picstruct': 'tff'}

PATH_TEST_STREAM = os.path.split(PATH_DIR_NAME)[0] + '/ted/content/' + TEST_STREAM['name']

# file for log
LOG = open(PATH_DIR_NAME + '/res.log', 'w')

# path for input and output files
PATH_TO_IO = PATH_DIR_NAME + '/IOFiles'

# end of constants

# delete path and create new if it exists
if os.path.exists(PATH_TO_IO):
    shutil.rmtree(PATH_TO_IO)
os.mkdir(PATH_TO_IO)


# classes definition
class ReturnCode(enum.Enum):
    ERROR_SUCCESS = 0
    ERROR_ACCESS_DENIED = 1
    ERROR_FAIL_TEST = 2


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run_test_case(self, test_case_object, case_id):

        err_code = test_case_object.run(case_id)

        if err_code != 0:
            self.failed += 1
            string_err = 'Fail'
        else:
            self.passed += 1
            string_err = 'OK'

        print('\t' + string_err)
        test_case_object.write_details()
        LOG.write('\n' + string_err + '\n' + "="*100)
        LOG.flush()


class TestCase:
    case_name = ''
    binaries = []
    err_code = 0   # shows that  all binaries have run with return code 0

    def __init__(self, case_name, *binaries):
        self.case_name = case_name
        self.binaries = binaries

    def run(self, case_id):
        if self.case_name:
            string_for_log = '\n' + self.case_name + '\n#' + str(case_id)
        else:
            string_for_log = '#' + str(case_id)

        LOG.write('\n' + string_for_log + '\n')
        print(string_for_log)

        for i in self.binaries:
            process = subprocess.Popen([i.path_to_bin] + i.params.split(), stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE)
            i.log_content = process.stderr.read() + process.stdout.read()
            i.log_content = i.log_content.decode("utf-8")
            process.communicate()
            i.return_code = process.returncode
            if i.return_code != 0:
                self.err_code = 1
                break

        LOG.flush()

        return self.err_code

    def write_details(self):
        for i in self.binaries:
            LOG.write("cmd: " + i.path_to_bin.split("/")[-1] + " " + i.params + "\n\n")
            LOG.write(i.log_content)
            LOG.flush()
            if i.return_code != 0:
                LOG.write("ERROR: app failed with return code: " + str(i.return_code))
                break
        return 0


class TestCaseQuality(TestCase):
    psnr_ref = 0
    psnr_test = 0
    size_ref = 0
    size_test = 0
    legacy_threshold = 0

    def __init__(self, case_name, threshold, *binaries):
        TestCase.__init__(self, case_name, *binaries)
        self.legacy_threshold = threshold

    def run(self, case_id):
        TestCase.run(self, case_id)
        if self.err_code != 0:
            return 1
        psnrs = []
        for i in self.binaries:
            if i.path_to_bin == MFX_PLAYER:
                regular_str = re.compile(r'([YUV])-PSNR> (\d+\.\d+)')
                psnr_find = regular_str.findall(i.log_content)
                psnr_y = float(psnr_find[0][1])
                psnr_u = float(psnr_find[1][1])
                psnr_v = float(psnr_find[2][1])
                psnrs.append((4*psnr_y + psnr_u + psnr_v)/6)
        self.psnr_ref = psnrs[0]
        self.psnr_test = psnrs[1]

        self.size_ref = os.path.getsize(PATH_TO_IO + '/' + str(case_id).rjust(4, '0') + '.hevc')
        self.size_test = os.path.getsize(PATH_TO_IO + '/' + str(case_id).rjust(4, '0') +
                                         '.cmp.hevc')

        if self.psnr_ref > self.legacy_threshold \
                and abs(self.psnr_ref - self.psnr_test) <= 0.05*min(self.psnr_ref,
                                                                    self.psnr_test) \
                and abs(self.size_ref - self.size_test) <= 0.2*min(self.size_ref,
                                                                   self.size_test):
            return 0
        return 1

    def write_details(self):
        TestCase.write_details(self)
        if self.err_code == 0:
            LOG.write('Legacy PSNR'.ljust(17) + ' : ' + str(round(self.psnr_ref, 5)) + '\n')
            LOG.write('Threshold'.ljust(17) + ' : ' + str(self.legacy_threshold) + '\n')

            if self.psnr_ref > self.legacy_threshold:
                LOG.write('legacy - ok\n')
            else:
                LOG.write('legacy - fail\n')

            LOG.write('\n' + 'sample_encode PSNR'.ljust(25) + ' : ' + str(round(self.psnr_ref, 5)) +
                      '\n')
            LOG.write('sample_fei PSNR'.ljust(25) + ' : ' + str(round(self.psnr_test, 5)) + '\n')

            diff_psnr = round(abs(self.psnr_ref - self.psnr_test) / min(self.psnr_ref,
                                                                        self.psnr_test) * 100, 5)
            if abs(self.psnr_ref - self.psnr_test) <= 0.05*min(self.psnr_ref, self.psnr_test):
                LOG.write('Diff: 0 <= ' + str(diff_psnr) + '% <= 5% - ok\n')
            else:
                LOG.write('Diff: ' + str(diff_psnr) + '% < 0 or ' + str(diff_psnr) +
                          '% > 5% - fail\n')

            LOG.write('\n' + 'size after sample_encode'.ljust(25) + ' : ' +
                      str(round(float(self.size_ref)/2**20, 3)) + 'MB\n')
            LOG.write('size after sample_fei'.ljust(25) + ' : ' +
                      str(round(float(self.size_test)/2**20, 3)) + 'MB\n')

            diff_size = round(100 * float(abs(self.size_ref - self.size_test)) /
                              min(self.size_ref, self.size_test), 5)
            if abs(self.size_ref - self.size_test) <= 0.2*min(self.size_ref, self.size_test):
                LOG.write('Diff: 0 <= ' + str(diff_size) + '% <= 20% - ok\n')
            else:
                LOG.write('Diff: ' + str(diff_size) + '% < 0 or ' + str(diff_size) +
                          '% > 20% - fail\n')


class TestCaseBitExact(TestCase):
    is_bit_exact = False

    def run(self, case_id):
        TestCase.run(self, case_id)
        if self.err_code != 0:
            return 1
        self.is_bit_exact = filecmp.cmp(PATH_TO_IO + '/' + str(case_id).rjust(4, '0') + '.hevc',
                                        PATH_TO_IO + '/' + str(case_id).rjust(4, '0') + '.cmp')
        if self.is_bit_exact:
            return 0
        return 1

    def write_details(self):
        TestCase.write_details(self)
        if self.err_code == 0:
            LOG.write('\n---------VERIFICATION---------\n\nBit to bit comparing:\n')

            if self.is_bit_exact:
                LOG.write('PASS\n')
            else:
                LOG.write('FAILED\n')


class RunnableBinary:
    path_to_bin = ''
    params = ''
    log_content = ''
    return_code = 0

    def __init__(self, binary, params):
        self.path_to_bin = binary
        self.params = params


def silent_file_remove(filename):
    try:
        os.remove(filename)
    except OSError as err:  # this would be "except OSError, e:"
        if err.errno != errno.ENOENT:  # errno.ENOENT = no such file or directory
            raise  # re-raise exception if a different error occured


# check binaries and streams
if not os.access(ASG, os.X_OK):
    print('No ASG or it cannot be executed')
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)
if not os.access(FEI_EXTRACTOR, os.X_OK):
    print('No hevc_fei_extractor or it cannot be executed')
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)
if not os.access(SAMPLE_FEI, os.X_OK):
    print('No sample_hevc_fei or it cannot be executed')
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)
if not os.access(SAMPLE_ENCODE, os.X_OK):
    print('No sample_encode or it cannot be executed')
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)
if not os.access(MFX_PLAYER, os.X_OK):
    print('No mfx_player or it cannot be executed')
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)
if not os.access(os.path.normpath(PATH_TEST_STREAM), os.F_OK):
    print(os.path.normpath(PATH_TEST_STREAM) + " doesn't exist")
    sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)

# test cases
TEST_CASES = []

# case counter is used for case numbering
NUM_CASE = 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# add pipelines
TEST_CASES.append(TestCase('Encode\nP frames \t \tgpb:on\n\tEMVP_singleRef '
                           'ME=quarter-pixel cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:on '
                                          '-NumRefFrame 1 -NumRefActiveP 1 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_multiRef ME=quarter-pixel cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:on '
                                          '-NumRefFrame 2 -NumRefActiveP 2 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_singleRef ME=quarter-pixel cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 4'
                                          ' -min_log2_cu_size 4 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:on '
                                          '-NumRefFrame 1 -NumRefActiveP 1 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split '
                                          '-max_log2_cu_size 4 -min_log2_cu_size 4 -sub_pel_mode 3 '
                                          '-pak_ctu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.ctustat -pak_cu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.custat '
                                          '-mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_multiRef ME=quarter-pixel cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 3 -x 2 '
                                          '-num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:on '
                                          '-NumRefFrame 2 -NumRefActiveP 2 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t gpb:off\n\tEMVP_singleRef ME=quarter-pixel cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 5'
                                          ' -min_log2_cu_size 5 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:off '
                                          '-NumRefFrame 1 -NumRefActiveP 1 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_multiRef ME=quarter-pixel cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 3 -x 2 '
                                          '-num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 -pred_file '
                                          + PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off '
                                          '-NumRefFrame 2 -NumRefActiveP 2 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split '
                                          '-max_log2_cu_size 5 -min_log2_cu_size 5 -sub_pel_mode 3 '
                                          '-pak_ctu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.ctustat -pak_cu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.custat '
                                          '-mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_singleRef ME=quarter-pixel cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 4'
                                          ' -min_log2_cu_size 4 -sub_pel_mode 3 -pred_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:off '
                                          '-NumRefFrame 1 -NumRefActiveP 1 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_multiRef ME=quarter-pixel cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 3 -x 2 '
                                          '-num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4'
                                          ' -min_log2_cu_size 4 -sub_pel_mode 3 -pred_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off '
                                          '-NumRefFrame 2 -NumRefActiveP 2 '
                                          '-NumPredictorsL0 4 -NumPredictorsL1 4 -EncodedOrder '
                                          '-encode -mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -sub_pel_mode 3  -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 70 -split_thres 70')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\nB frames \t gpb:on \n\tEMVP_singleRef ME=integer cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 32 -x 2 -num_active_P 1 -num_active_BL0 1 '
                                          '-num_active_BL1 1 -r 4 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 0 -pred_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 32 -GopRefDist 4 -gpb:on '
                                          '-NumRefFrame 2 -NumRefActiveP 1 -NumRefActiveBL0 1 '
                                          '-NumRefActiveBL1 1 -NumPredictorsL0 4 -NumPredictorsL1 4'
                                          ' -encode -EncodedOrder -mvpin ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 32 -x 2 -num_active_P 1 -num_active_BL0 1 '
                                          '-num_active_BL1 1 -r 4 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 '
                                          '-sub_pel_mode 0 -pak_ctu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.ctustat -pak_cu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat '
                                          '-mv_thres 50 -split_thres 50 -numpredictors 4')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\tEMVP_multiRef ME=integer cu_size32',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 32 -x 2 -num_active_P 1 -num_active_BL0 1 '
                                          '-num_active_BL1 1 -r 4 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 0 -pred_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 32 -GopRefDist 4 -gpb:on '
                                          '-NumRefFrame 2 -NumRefActiveP 1 -NumRefActiveBL0 1 '
                                          '-NumRefActiveBL1 1 -NumPredictorsL0 4 -NumPredictorsL1 4'
                                          ' -EncodedOrder -encode -mvpin ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 32 -x 2 -num_active_P 1 -num_active_BL0 1 '
                                          '-num_active_BL1 1 -r 4 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 0 '
                                          '-pak_ctu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.ctustat -pak_cu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.custat '
                                          '-mv_thres 50 -split_thres 50 -numpredictors 4')))


NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\nP frames \tIntra_inter_mix \t gpb:on \n\tEMVP_singleRef '
                           'ME=integer cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp -g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5'
                                          ' -no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -mvp_block_size 1 -sub_pel_mode 0 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:on '
                                          '-NumRefFrame 2 -NumRefActiveP 2 -NumPredictorsL0 4 '
                                          '-NumPredictorsL1 4 -encode -EncodedOrder '
                                          '-mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -mvp_block_size 1 -sub_pel_mode 0 '
                                          '-pak_ctu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.ctustat -pak_cu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.custat '
                                          '-mv_thres 80 -split_thres 80 -numpredictors 4')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t \t \t gpb:off\n\tEMVP_singleRef ME=integer cu_size16',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' + '-n ' +
                                          TEST_STREAM['frames'] + ' ' + '-w ' + TEST_STREAM['w'] +
                                          ' -h ' + TEST_STREAM['h'] + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp '
                                          '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -mvp_block_size 1 -gpb_off '
                                          '-sub_pel_mode 0 -pred_file ' + PATH_TO_IO + '/'
                                          + NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' + '-w ' +
                                          TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' ' +
                                          '-f 25 -qp 2 -g 3 -GopRefDist 1 -gpb:off -NumRefFrame 2 '
                                          '-NumRefActiveP 2 -NumPredictorsL0 4 -NumPredictorsL1 4 '
                                          '-encode -EncodedOrder -mvpin ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp.mvmvp.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.ctustat ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '_mvmvp.custat'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 3 -x 2 -num_active_P 2 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 4 '
                                          '-min_log2_cu_size 4 -mvp_block_size 1 -gpb_off '
                                          '-sub_pel_mode 0 -pak_ctu_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_mvmvp.ctustat -pak_cu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.custat -mv_thres 80 -split_thres 80 '
                                          '-numpredictors 4')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# hevce_fei_encode_multi_pass_pak
TEST_CASES.append(TestCase('\nmulti-pass PAK \n\t GOP_size-1 \n\t \t \t QP-24',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 24 -g 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 24 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 24 -g 1 -encode -EncodedOrder -repackctrl ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakctrl '
                                          '-repackstat ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakstat -repack_str_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak '
                                          '-InitialQP 24')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t QP-26',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 26 -g 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' ' + '-g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.multipak -InitialQP 26 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 26 -g 1 -encode -EncodedOrder -repackctrl ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakctrl '
                                          '-repackstat ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 26')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t QP-28',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 28 -g 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 28 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 28 -g 1 -encode -EncodedOrder -repackctrl ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakctrl '
                                          '-repackstat ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 28')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t QP-31',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 31 -g 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 31 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 31 -g 1 -encode -EncodedOrder -repackctrl ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakctrl '
                                          '-repackstat ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 31')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t GOP_size-2 \t GopRefDist-1 \t QP-24',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 24 -g 2 -GopRefDist 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -r 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 24 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 24 -g 2 -GopRefDist 1 -encode -EncodedOrder -'
                                          'repackctrl ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repackstat ' + PATH_TO_IO +
                                          '/' + NUM_CASE_STR + '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -r 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak -InitialQP 24')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t \t \t QP-28',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 28 -g 2 -GopRefDist 1 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc -'
                                          'multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -r 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 28 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 28 -g 2 -GopRefDist 1 -encode -EncodedOrder '
                                          '-repackctrl ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.repakctrl -repackstat ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -r 1 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 28')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t GOP_size-5 \t GopRefDist-3  \t QP-26',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 26 -g 5 -GopRefDist 3 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 5 -r 3 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.multipak -InitialQP 26 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 26 -g 5 -GopRefDist 3 -encode -EncodedOrder '
                                          '-repackctrl ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repackstat ' + PATH_TO_IO +
                                          '/' + NUM_CASE_STR + '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 5 -r 3 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 26')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
TEST_CASES.append(TestCase('\t \t \t \t \t QP-31',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -qp 31 -g 5 -GopRefDist 3 -encode -EncodedOrder'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.multipak'),
                           RunnableBinary(ASG,
                                          '-generate -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 5 -r 3 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_str_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.multipak '
                                          '-InitialQP 31 -DeltaQP 1 1 2 2 3 3 4 4'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.repack ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] + ' '
                                          '-qp 31 -g 5 -GopRefDist 3 -encode -EncodedOrder '
                                          '-repackctrl ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repackstat ' + PATH_TO_IO +
                                          '/' + NUM_CASE_STR + '.repakstat'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repack '
                                          '-multi_pak_str ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '_repak.multipak'),
                           RunnableBinary(ASG,
                                          '-verify -gen_repack_ctrl '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 5 -r 3 -repack_ctrl_file ' + PATH_TO_IO + '/' +
                                          NUM_CASE_STR + '.repakctrl -repack_stat_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR + '.repakstat '
                                          '-repack_str_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_repak.multipak -InitialQP 31')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# hevce_fei_encode_nummvpredictors
TEST_CASES.append(TestCase('num_mvpredictors',
                           RunnableBinary(ASG,
                                          '-generate -gen_inter -gen_mv -gen_pred -gen_split -i '
                                          + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp '
                                          '-g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5  '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 '
                                          '-pred_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp.mvmvp_4_NumPredictors.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:on -NumRefFrame 1 '
                                          '-NumRefActiveP 1 -NumPredictorsL0 4 -NumPredictorsL1 4 '
                                          '-encode -EncodedOrder '
                                          '-mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.prmvmvp -o ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp.mvmvp_2_NumPredictors.hevc '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -f 25 -qp 2 -g 2 -GopRefDist 1 -gpb:on -NumRefFrame 1 '
                                          '-NumRefActiveP 1 -NumPredictorsL0 2 -NumPredictorsL1 2 '
                                          '-encode -EncodedOrder '
                                          '-mvpin ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_mvmvp.mvin'),
                           RunnableBinary(FEI_EXTRACTOR,
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '.prmvmvp.mvmvp_2_NumPredictors.hevc ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_2.ctustat_mvmvp_numpredictors ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_2.custat_mvmvp_numpredictors'),
                           RunnableBinary(ASG,
                                          '-verify -gen_inter -gen_mv -gen_pred -gen_split '
                                          '-n ' + TEST_STREAM['frames'] + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -g 2 -x 1 -num_active_P 1 -r 1 -log2_ctu_size 5 '
                                          '-no_cu_to_pu_split -max_log2_cu_size 5 '
                                          '-min_log2_cu_size 5 -sub_pel_mode 3 -pak_ctu_file ' +
                                          PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_2.ctustat_mvmvp_numpredictors '
                                          '-pak_cu_file ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                          '_2.custat_mvmvp_numpredictors '
                                          '-mv_thres 80 -numpredictors 2')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# preenc ds
TEST_CASES.append(TestCase('PREENC DS',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -n ' + TEST_STREAM['frames'] + ' ' +
                                          '-preenc 4 -qp 30 -l 1 -g 30 -GopRefDist 4 '
                                          '-NumRefFrame 4 -bref')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# preenc + encode
TEST_CASES.append(TestCase('PREENC + ENCODE',
                           RunnableBinary(SAMPLE_FEI,
                                          '-i ' + os.path.normpath(PATH_TEST_STREAM) + ' ' +
                                          '-w ' + TEST_STREAM['w'] + ' -h ' + TEST_STREAM['h'] +
                                          ' -n ' + TEST_STREAM['frames'] + ' ' +
                                          '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR + '.hevc -preenc '
                                          '-encode -qp 30 -l 1 -g 30 -GopRefDist 4 '
                                          '-NumRefFrame 4 -bref')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# encode quality
TEST_CASES.append(TestCaseQuality('Quality', 30,
                                  RunnableBinary(SAMPLE_ENCODE,
                                                 'h265 '
                                                 '-i ' + os.path.normpath(PATH_TEST_STREAM) +
                                                 ' ' + '-w ' + TEST_STREAM['w'] + ' -h ' +
                                                 TEST_STREAM['h'] + ' ' +
                                                 '-n ' + TEST_STREAM['frames'] + ' ' +
                                                 '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                 '.hevc -f 25 -x 4 -g 30 -r 4 -cqp -qpi '
                                                 '30 -qpp 30 -qpb 30 -num_slice 1 -bref'),
                                  RunnableBinary(MFX_PLAYER,
                                                 '-i:hevc ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                 '.hevc -o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                 '.dec.yuv -n ' + TEST_STREAM['frames'] + ' ' +
                                                 '-decode_plugin_guid '
                                                 '33a61c0b4c27454ca8d85dde757c6f8e '
                                                 '-cmp ' + os.path.normpath(PATH_TEST_STREAM) +
                                                 ' -psnr -hw'),
                                  RunnableBinary(SAMPLE_FEI,
                                                 '-i ' + os.path.normpath(PATH_TEST_STREAM) +
                                                 ' -w ' + TEST_STREAM['w'] + ' -h ' +
                                                 TEST_STREAM['h'] + ' ' + '-n ' +
                                                 TEST_STREAM['frames'] + ' ' + '-o ' + PATH_TO_IO +
                                                 '/' + NUM_CASE_STR + '.cmp.hevc -f 25 -qp 30 -l 1 '
                                                 '-NumRefFrame 4 -g 30 -NumRefActiveP 2 '
                                                 '-NumRefActiveBL0 2 -NumRefActiveBL1 1 '
                                                 '-GopRefDist 4 -bref -encode'),
                                  RunnableBinary(MFX_PLAYER,
                                                 '-i:hevc ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                 '.cmp.hevc -o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                 '.cmp.dec.yuv -n ' + TEST_STREAM['frames'] + ' ' +
                                                 '-decode_plugin_guid '
                                                 '33a61c0b4c27454ca8d85dde757c6f8e '
                                                 '-cmp ' + os.path.normpath(PATH_TEST_STREAM) +
                                                 ' -psnr -hw')))

NUM_CASE += 1
NUM_CASE_STR = str(NUM_CASE).rjust(4, '0')
# Encoded order
TEST_CASES.append(TestCaseBitExact('EncodedOrder',
                                   RunnableBinary(SAMPLE_FEI,
                                                  '-i ' + os.path.normpath(PATH_TEST_STREAM) +
                                                  ' -w ' + TEST_STREAM['w'] + ' -h ' +
                                                  TEST_STREAM['h'] + ' ' + '-n ' +
                                                  TEST_STREAM['frames'] + ' ' +
                                                  '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                  '.hevc -f 25 -qp 24 -g 31 -GopRefDist 4 -gpb:on '
                                                  '-NumRefFrame 0 -bref -encode '
                                                  '-EncodedOrder -DisableQPOffset'),
                                   RunnableBinary(SAMPLE_FEI,
                                                  '-i ' + os.path.normpath(PATH_TEST_STREAM) +
                                                  ' -w ' + TEST_STREAM['w'] + ' -h ' +
                                                  TEST_STREAM['h'] + ' ' + '-n ' +
                                                  TEST_STREAM['frames'] + ' ' +
                                                  '-o ' + PATH_TO_IO + '/' + NUM_CASE_STR +
                                                  '.cmp -f 25 -qp 24 '
                                                  '-g 31 -GopRefDist 4 -gpb:on -NumRefFrame 0 '
                                                  '-bref -encode -DisableQPOffset')))

RUNNER = TestRunner()
for test_case in TEST_CASES:
    RUNNER.run_test_case(test_case, TEST_CASES.index(test_case) + 1)

INFO_FOR_LOG = 'PASSED ' + str(RUNNER.passed) + ' of ' + str(len(TEST_CASES))
print(INFO_FOR_LOG)
LOG.write('\n' + INFO_FOR_LOG)

LOG.close()
if os.path.exists(PATH_TO_IO):
    shutil.rmtree(PATH_TO_IO)

print('See details in ' + PATH_DIR_NAME + '/res.log')
print('Time: ' + str(time.time() - START_TIME) + ' seconds')

if RUNNER.failed != 0:
    sys.exit(ReturnCode.ERROR_FAIL_TEST.value)
sys.exit(ReturnCode.ERROR_SUCCESS.value)
