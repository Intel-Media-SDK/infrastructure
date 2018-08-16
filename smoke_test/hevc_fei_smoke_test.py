# -*- coding: utf-8 -*-

# Copyright (c) 2017 Intel Corporation
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


import os
import subprocess
import sys
import shutil
import time
import filecmp
import enum
import pathlib
from collections import abc
from string import Template


# classes definition
class ReturnCode(enum.Enum):
    ERROR_SUCCESS = 0
    ERROR_TEST_FAILED = 1
    ERROR_ACCESS_DENIED = 2

class Path(type(pathlib.Path())):
    # overridden method for opening file with mode a+
    def write_text(self, data, encoding=None, errors=None):
        if not isinstance(data, str):
            raise TypeError('data must be str, not %s' %
                            data.__class__.__name__)
        with self.open(mode='a+', encoding=encoding, errors=errors) as file:
            return file.write(data)

    def clear_text_file(self):
        with self.open(mode='w') as file:
            return file.write('')


class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def run_test_case(self, test_case_object, case_id):

        err_code = test_case_object.run(case_id)

        if err_code:
            self.failed += 1
            string_err = 'Fail'
        else:
            self.passed += 1
            string_err = 'OK'

        print(f'     {string_err}', end='')
        test_case_object.write_details()
        string_for_log = ' \n' + string_err + '\n' + "="*100
        LOG.write_text(string_for_log)


class TestCase:
    case_name = ''
    stages = []
    err_code = False   # shows that  all stages have to run with false return code

    def __init__(self, case_name, stages):
        self.case_name = case_name
        self.stages = stages

    def run(self, case_id):
        template_for_log = Template('$case_name \n#' + str(case_id) + '\n')
        if self.case_name:
            string_for_log = template_for_log.substitute(case_name=self.case_name)
        else:
            string_for_log = template_for_log.substitute(case_name='')

        print(string_for_log, end='')
        LOG.write_text('\n\n')
        LOG.write_text(string_for_log)

        for stage in self.stages:
            try:
                process = subprocess.run([stage.path_to_bin] + stage.params.split(),  check=True,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stage.log_content = process.stdout.strip().decode("utf-8")
            except subprocess.CalledProcessError as exception:
                stage.return_code = exception.returncode
                self.err_code = True
                return self.err_code
        return self.err_code

    def write_details(self):
        for stage in self.stages:
            string_for_log = "cmd: " + str(stage.path_to_bin) + " " + stage.params + "\n\n"
            string_for_log += stage.log_content
            if stage.return_code != 0:
                string_for_log += f'ERROR: app failed with return code: {stage.return_code}'
                LOG.write_text(string_for_log)
                break
            LOG.write_text(string_for_log)


class TestCaseBitExact(TestCase):
    is_bit_exact = False

    def run(self, case_id):
        TestCase.run(self, case_id)
        if self.err_code:
            return True
        self.is_bit_exact = filecmp.cmp(PATH_TO_IO / f'{case_id:04}.hevc',
                                        PATH_TO_IO / f'{case_id:04}.cmp')
        return not self.is_bit_exact

    def write_details(self):
        TestCase.write_details(self)
        if not self.err_code:
            bit_exact_status = 'PASS' if self.is_bit_exact else 'FAILED'
            string_for_log = '\n---------VERIFICATION---------\n\nBit to bit comparing:\n'
            string_for_log += bit_exact_status
            LOG.write_text(string_for_log)


class RunnableBinary:
    path_to_bin = ''
    params = ''
    log_content = ''
    return_code = 0

    def __init__(self, path_to_bin, params):
        self.path_to_bin = path_to_bin
        self.params = params


class TestCasesCreator:
    def __init__(self,):
        self.test_cases = []

    def create_test_cases(self, cases_dict):
        test_cases_list = TestCasesCreator.nested_dict_iter(cases_dict)

        for num_of_case, test_case in enumerate(test_cases_list, 1):
            test_case_name = test_case[0]
            stages = []
            for cases_dict in test_case[1]:
                for key, cmd in cases_dict.items():
                    if key == 'case type':
                        case_type = cmd
                    else:
                        stages.append(RunnableBinary(PATH_DICT[key],
                                                     cmd.format(path_to_io=
                                                                f'{PATH_TO_IO / f"{num_of_case:04}"}')))

            self.test_cases.append(case_type(test_case_name, stages))

        return self.test_cases

    @staticmethod
    def nested_dict_iter(nested_dict):
        for key, value in nested_dict.items():
            if isinstance(value, abc.Mapping):
                yield from TestCasesCreator.nested_dict_iter(value)
            else:
                yield key, value


class GroupNamesOfCases:
    def __init__(self,):
        self.names = []

    def create_groupe_names(self, cases_dict):
        self.names = list(GroupNamesOfCases.nested_dict_iter(cases_dict, 0, ' '))
        return self.names

    @staticmethod
    def nested_dict_iter(nested_dict, indent, name):
        for key, value in nested_dict.items():
            if isinstance(value, dict):
                name += '\t' * indent + str(key)
                yield from GroupNamesOfCases.nested_dict_iter(value, indent + 1, name)
                name = ' '
            else:
                yield name + '\n' + '\t' * indent
                name = ' '


# constants
PATH_DIR_NAME = Path(__file__).resolve().parent

# paths to every needed binary
ASG = PATH_DIR_NAME.joinpath('asg-hevc')
FEI_EXTRACTOR = PATH_DIR_NAME.joinpath('hevc_fei_extractor')
SAMPLE_FEI = Path('/opt/intel/mediasdk/samples/sample_hevc_fei')
SAMPLE_ENCODE = Path('/opt/intel/mediasdk/samples/sample_encode')

PATH_DICT = {'ASG': ASG, 'FEI_EXTRACTOR': FEI_EXTRACTOR, 'SAMPLE_FEI': SAMPLE_FEI,
             'SAMPLE_ENCODE': SAMPLE_ENCODE}

# parameters of the test stream (key:value)
TEST_STREAM = {'name': 'test_stream_176x96.yuv', 'w': '176', 'h': '96', 'frames': '100',
               'picstruct': 'tff'}

PATH_TEST_STREAM = PATH_DIR_NAME.parent / f'ted/content/{TEST_STREAM["name"]}'

# file for log
LOG = PATH_DIR_NAME / 'res.log'
LOG.clear_text_file()

# path for input and output files
PATH_TO_IO = PATH_DIR_NAME / 'IOFiles'

# end of constants


if __name__ == '__main__':

    from config import TEST_CASES_DICT

    START_TIME = time.time()

    # delete path and create new if it exists
    if PATH_TO_IO.exists():
        shutil.rmtree(PATH_TO_IO)
    PATH_TO_IO.mkdir()

    for name, path in PATH_DICT.items():
        if not os.access(path, os.X_OK):
            print(f'No {name} or it cannot be executed')
            sys.exit(ReturnCode.ERROR_ACCESS_DENIED.value)

    TEST_CASES_CREATOR = TestCasesCreator()
    TEST_CASES = TEST_CASES_CREATOR.create_test_cases(TEST_CASES_DICT)

    GROUP_NAMES_OF_CASES = GroupNamesOfCases().create_groupe_names(TEST_CASES_DICT)

    RUNNER = TestRunner()

    for num_of_case, test_case in enumerate(TEST_CASES, 1):
        print('\n' + GROUP_NAMES_OF_CASES[num_of_case-1], end='')
        RUNNER.run_test_case(test_case, num_of_case)

    INFO_FOR_LOG = '\n' + f'PASSED {RUNNER.passed} of {len(TEST_CASES)}'
    print(INFO_FOR_LOG)
    LOG.write_text(INFO_FOR_LOG)

    if PATH_TO_IO.exists():
        shutil.rmtree(PATH_TO_IO)

    print(f'See details in {LOG.name}')
    print(f'Time:  {(time.time() - START_TIME):.5f} seconds')

    if RUNNER.failed != 0:
        sys.exit(ReturnCode.ERROR_TEST_FAILED.value)
    sys.exit(ReturnCode.ERROR_SUCCESS.value)
