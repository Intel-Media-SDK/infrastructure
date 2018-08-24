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


import os
import subprocess
import sys
import shutil
import time
import filecmp
from pathlib import Path
from string import Template


# classes definition
class PathPlus(type(Path())):
    def append_text(self, data, encoding=None, errors=None):
        if not isinstance(data, str):
            raise TypeError('data must be str, not %s' %
                            data.__class__.__name__)
        with self.open(mode='a+', encoding=encoding, errors=errors) as file:
            return file.write(data)

    def clear_text_file(self):
        with self.open(mode='w') as file:
            pass


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
        separator = '='*100
        log_string = f' \n{string_err}\n{separator}'
        cfg.LOG.append_text(log_string)


class TestCase:
    case_name = ''
    stages = []
    err_code = False   # shows that  all stages have to run with false return code

    def __init__(self, case_name, stages):
        self.case_name = case_name
        self.stages = stages

    def run(self, case_id):
        log_template = Template(f'$case_name \n#{case_id}\n')
        if self.case_name:
            log_string = log_template.substitute(case_name=self.case_name)
        else:
            log_string = log_template.substitute(case_name='')

        print(log_string, end='')
        cfg.LOG.append_text('\n\n')
        cfg.LOG.append_text(log_string)

        for stage in self.stages:
            try:
                process = subprocess.run([stage.path_to_bin] + stage.params.split(), check=True,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                stage.log_content = process.stdout.strip().decode("utf-8")
            except subprocess.CalledProcessError as exception:
                stage.log_content = exception.stdout.strip().decode("utf-8")
                stage.return_code = exception.returncode
                self.err_code = True
                return self.err_code
        return self.err_code

    def write_details(self):
        for stage in self.stages:
            lines = [
                f'cmd: {stage.path_to_bin} {stage.params}\n\n',
                stage.log_content,
                ]
            log_string = '\n'.join(lines)
            cfg.LOG.append_text(log_string)
            if stage.return_code != 0:
                log_string_err = f'\nERROR: app failed with return code: {stage.return_code}'
                cfg.LOG.append_text(log_string_err)
                break


class TestCaseBitExact(TestCase):
    is_bit_exact = False

    def run(self, case_id):
        TestCase.run(self, case_id)
        if self.err_code:
            return True
        self.is_bit_exact = filecmp.cmp(cfg.PATH_TO_IO / f'{case_id:04}.hevc',
                                        cfg.PATH_TO_IO / f'{case_id:04}.cmp')
        return not self.is_bit_exact

    def write_details(self):
        TestCase.write_details(self)
        if not self.err_code:
            log_lines = [
                'PASS' if self.is_bit_exact else 'FAILED',
                '---------VERIFICATION---------',
                'Bit to bit comparing:',
                ]
            log_string = '\n'.join(log_lines)
            cfg.LOG.append_text(log_string)


class TestCaseErr(TestCase):
    def __init__(self, case_name, err_msg):
        TestCase.__init__(self, case_name, [])
        self.err_msg = err_msg
        self.err_code = True

    def run(self, case_id):
        TestCase.run(self, case_id)
        return self.err_code

    def write_details(self):
        cfg.LOG.append_text(f'\n{self.err_msg}')


class RunnableBinary:
    path_to_bin = ''
    params = ''
    log_content = ''
    return_code = 0

    def __init__(self, path_to_bin, params):
        self.path_to_bin = path_to_bin
        self.params = params


class TestCasesCreator:
    def __init__(self, cases_dict):
        self.test_cases = []
        self.titles = []
        test_cases_list = nested_dict_iter(cases_dict)

        prev_parents = []

        for num_of_case, (parents, case_name, case) in enumerate(test_cases_list, 1):
            self.create_case(num_of_case, case_name, case)
            prev_parents = self.create_title(parents, prev_parents)

    def create_case(self, num_of_case, case_name, case):
        test_case_name = case_name
        stages = []
        case_type = None
        for test_dict in case:
            for key, cmd in test_dict.items():
                if key == 'case type':
                    case_type = cmd

                else:
                    stages.append(RunnableBinary(cfg.PATH_DICT[key],
                                                 cmd.format(path_to_io=
                                                            f'{cfg.PATH_TO_IO / f"{num_of_case:04}"}')))
        if case_type is None:
            err_msg = f'Case type is unidentified'
            self.test_cases.append(TestCaseErr(test_case_name, err_msg))
        elif not stages:
            err_msg = f'Test case is empty'
            self.test_cases.append(TestCaseErr(test_case_name, err_msg))
        else:
            self.test_cases.append(case_type(test_case_name, stages))

    def create_title(self, parents, prev_parents):
        title = ''
        indent = '\t'
        if parents != prev_parents:
            intersection = list(set(parents) & set(prev_parents))
            for level, label in enumerate(parents):
                if label in intersection:
                    title += indent
                else:
                    title += level * indent + label

        title += '\n' + indent * len(parents)
        self.titles.append(title)
        return parents


def nested_dict_iter(nested_dict, path=None):
    if path is None:
        path = []
    for k, v in nested_dict.items():
        if isinstance(v, dict):
            path.append(k)
            yield from nested_dict_iter(v, path)
            path.pop()
        else:
            path.append(k)
            *parents, key = path
            yield parents, key, v
            path.pop()


import config as cfg

if __name__ == '__main__':

    START_TIME = time.time()

    # delete path and create new if it exists
    if cfg.PATH_TO_IO.exists():
        shutil.rmtree(cfg.PATH_TO_IO)
    cfg.PATH_TO_IO.mkdir()

    cfg.LOG.clear_text_file()

    for name, path in cfg.PATH_DICT.items():
        if not os.access(path, os.X_OK):
            print(f'No {name} or it cannot be executed')
            sys.exit(cfg.ReturnCode.ERROR_ACCESS_DENIED.value)

    TEST_CASES_CREATOR = TestCasesCreator(cfg.TEST_CASES_DICT)
    TEST_CASES = TEST_CASES_CREATOR.test_cases
    TITLES = TEST_CASES_CREATOR.titles

    RUNNER = TestRunner()

    for num_of_case, test_case in enumerate(TEST_CASES, 1):
        print(f'\n{TITLES[num_of_case-1]}', end='')
        RUNNER.run_test_case(test_case, num_of_case)

    INFO_FOR_LOG = f'\nPASSED {RUNNER.passed} of {len(TEST_CASES)}'
    print(INFO_FOR_LOG)
    cfg.LOG.append_text(INFO_FOR_LOG)

    if cfg.PATH_TO_IO.exists():
        shutil.rmtree(cfg.PATH_TO_IO)

    print(f'See details in {cfg.LOG}')
    print(f'Time:  {(time.time() - START_TIME):.5f} seconds')

    if RUNNER.failed != 0:
        sys.exit(cfg.ReturnCode.ERROR_TEST_FAILED.value)
    sys.exit(cfg.ReturnCode.ERROR_SUCCESS.value)
