# Copyright (c) 2019 Intel Corporation
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

"""
Runner for driver tests
"""

import argparse
import logging
import os
import re
import sys
import pathlib
from copy import copy

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.helper import cmd_exec, ErrorCode
from common.logger_conf import configure_logger
from driver_tests.tests_cfg import TESTS


class Test:
    """
    Class for driver test
    """

    def __init__(self, test_id, test_info):
        self._id = test_id
        self._feature = test_info['feature']
        self._cmd = test_info['cmd']
        self._ref_type = test_info['ref_type']
        self._ref_value = test_info.get('ref_value', 'no reference value')

        self._output_file = None
        self._input_file = None
        self._width = None
        self._height = None

        self.log = logging.getLogger(test_id)

    def _env_check(self):
        """
        Check test environment

        :return: Boolean
        """

        self.log.info('-'*80)
        self.log.info('Check environment')

        code, _ = cmd_exec('lsmod | grep -q i915', log=self.log)
        if code:
            self.log.error("system does not load i915 module")
            return False

        self.log.info("i915 load successfully")

        code, vainfo = cmd_exec('vainfo', log=self.log)
        if code:
            self.log.info(vainfo)
            return False

        try:
            driver_version = re.search(f'.*Driver version: (.*)', vainfo).group(1).strip()
        except Exception:
            self.log.exception('Exception occurred:')
            return False

        self.log.info(f'Driver version: {driver_version}')

        if 'iHD' in driver_version:
            self.log.info('Current media driver is iHD and supports gen11+ and Whiskylake platform')
        elif 'i965' in driver_version:
            self.log.info('Current media driver is i965 and supports pre-gen11 platform')
        else:
            self.log.error('Unknown media driver')
            return False

        return True

    def _get_info(self):
        """
        Get information of a test

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info('Get test info')

        self.log.info(f'Test Id: {self._id}')

        self._input_file = self._cmd[self._cmd.index('-i') + 1]
        self.log.info(f'Input file: {self._input_file}')

        if '-s:v' in self._cmd:
            resolution = self._cmd[self._cmd.index('-s:v') + 1]
            self._width, self._height = resolution.split('x')

            self.log.info(f'Width: {self._width}')
            self.log.info(f'Height: {self._height}')

        if self._feature != 'playback':
            self._output_file = self._cmd[self._cmd.index('-y') + 1]
            output_file = pathlib.Path(self._output_file)
            if output_file.exists():
                output_file.unlink()
            output_file.parent.mkdir(exist_ok=True, parents=True)

        return True

    def _execute_test_cmd(self):
        """
        Run base command line of a test

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info('Execute test command line')

        code, out = cmd_exec(self._cmd, shell=False, log=self.log)
        if code:
            self.log.error(out)
            return False

        self.log.info(out)
        return True

    def _check_md5(self):
        """
        Compare reference md5sum with actual

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info('Check md5 sum')

        self.log.info(self._ref_value)
        self.log.info(self._output_file)

        code, out = cmd_exec(['md5sum', self._output_file], shell=False, log=self.log)
        if code:
            self.log.error(out)
            return False
        self.log.info(out)

        md5sum, _ = out.split(' ')

        self.log.info(f'reference md5: {self._ref_value}')
        self.log.info(f'actual md5: {md5sum}')

        if self._ref_value != md5sum:
            return False

        return True

    def _get_psnr(self, first_file, second_file, width, height):
        """
        Get PSNR value

        :param first_file: Name of first file to compare
        :param second_file: Name of second file to compare
        :param width: Width of sequences pixels
        :param height: Height of sequences pixels

        :return: PSNR | False
        """

        self.log.info('-' * 80)
        self.log.info('Get PSNR')

        metrics_calc_cmd = [
            'metrics_calc_lite',
            '-i1',
            '-i2',
            '-w',
            '-h',
            'psnr',
            'ssim',
            'all'
        ]

        metrics_calc_cmd.insert(metrics_calc_cmd.index('-i1') + 1, str(first_file))
        metrics_calc_cmd.insert(metrics_calc_cmd.index('-i2') + 1, str(second_file))
        metrics_calc_cmd.insert(metrics_calc_cmd.index('-w') + 1, width)
        metrics_calc_cmd.insert(metrics_calc_cmd.index('-h') + 1, height)

        code, out = cmd_exec(metrics_calc_cmd, shell=False, log=self.log)
        if code:
            self.log.error(out)
            return False
        self.log.info(out)

        psnr = re.search('<avg_metric=PSNR>(.*)</avg_metric>', out).group(1)
        return psnr

    def _compare_files(self, first_file, second_file):
        """
        Compare two files byte by byte

        :param first_file: Name of first file to compare
        :param second_file: Name of second file to compare

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info('Compare files')

        code, out = cmd_exec(['cmp', str(first_file), str(second_file)], shell=False, log=self.log)
        if code:
            self.log.warning('md5 checksum IS NOT SAME with ffmpeg sw decode')
            self.log.warning(out)
            return False

        self.log.info('md5 checksum IS SAME with ffmpeg sw decode')
        return True

    def _check_psnr(self):
        """
        Check PSNR consistence

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info('Check PSNR')

        psnr = None

        _output_file = pathlib.Path(self._output_file)
        if not _output_file.exists():
            self.log.error(f'{_output_file} does not exist')
            self.log.error(f'reference psnr: {self._ref_value}')
            self.log.error(f'actual psnr: {psnr}')
            return False

        cmd_copy = copy(self._cmd)

        if self._feature == 'decode':
            self.log.info('Decode the input file with ffmpeg sw')

            sw_output_file = _output_file.parent / f'{_output_file.name}_sw.yuv'

            # remove -hwaccel
            idx = cmd_copy.index('-hwaccel')
            cmd_copy.pop(idx)
            cmd_copy.pop(idx)

            # remove -hwaccel_device
            idx = cmd_copy.index('-hwaccel_device')
            cmd_copy.pop(idx)
            cmd_copy.pop(idx)

            # update output file
            cmd_copy[-1] = str(sw_output_file)

            # execute ffmpeg sw decode
            code, out = cmd_exec(cmd_copy, shell=False, log=self.log)
            if code:
                self.log.error(out)
                return False
            self.log.info(out)

            resolution = re.search(rf'.*Stream #.*, (\d*x\d*).*', out).group(1).strip()
            self._width, self._height = resolution.split('x')

            # compare outputs
            if not self._compare_files(self._output_file, sw_output_file):
                psnr = self._get_psnr(sw_output_file, self._output_file, self._width, self._height)

        elif self._feature == 'encode':
            self.log.info('Encode the input file with ffmpeg sw')

            output_yuv = _output_file.parent / f'{_output_file.name}.yuv'

            # get -vframes
            vframes = cmd_copy[cmd_copy.index('-vframes') + 1]

            ffmpeg_cmd = [
                'ffmpeg',
                '-v', 'debug',
                '-i', self._output_file,
                '-pix_fmt', 'yuv420p',
                '-f', 'rawvideo',
                '-vsync', 'passthrough',
                '-vframes', vframes,
                '-y', str(output_yuv)
            ]

            code, out = cmd_exec(ffmpeg_cmd, shell=False, log=self.log)
            if code:
                self.log.error(out)
                return False
            self.log.info(out)

            psnr = self._get_psnr(self._input_file, output_yuv, self._width, self._height)

        elif self._feature == 'vp':
            self.log.info('Scale the input file with ffmpeg sw')

            if '-vf' in cmd_copy:
                vf_args = cmd_copy[cmd_copy.index('-vf') + 1]
                if 'scale_vaapi' in vf_args:
                    sw_output_file = _output_file.parent / f'{_output_file.name}_sw.yuv'

                    self._width, self._height = re.search(r'.*scale_vaapi=w=(\d+):h=(\d+).*',
                                                          vf_args).groups()
                    self.log.info(f'Scale: width = {self._width}; height = {self._height}')

                    # remove -hwaccel
                    idx = cmd_copy.index('-hwaccel')
                    cmd_copy.pop(idx)
                    cmd_copy.pop(idx)

                    # remove -vaapi_device
                    idx = cmd_copy.index('-vaapi_device')
                    cmd_copy.pop(idx)
                    cmd_copy.pop(idx)

                    # update -vf
                    cmd_copy[cmd_copy.index('-vf') + 1] = f'scale={self._width}:{self._height}'

                    # update output file
                    cmd_copy[-1] = str(sw_output_file)

                    # scaling with ffmpeg sw
                    code, out = cmd_exec(cmd_copy, shell=False, log=self.log)
                    if code:
                        self.log.error(out)
                        return False
                    self.log.info(out)

                    # compare outputs
                    if not self._compare_files(self._output_file, sw_output_file):
                        psnr = self._get_psnr(sw_output_file, self._output_file,
                                              self._width, self._height)
        else:
            self.log.error(f'Feature {self._feature} is not supported')
            return False

        if psnr is None:
            return True
        if not psnr:
            return False

        self.log.info(f'reference psnr: {self._ref_value}')
        self.log.info(f'actual psnr: {psnr}')

        psnr_gap = 100*(float(psnr) - float(self._ref_value))/float(self._ref_value)
        psnr_gap = round(psnr_gap, 4)
        self.log.info(f'psnr gap: {psnr_gap}%')

        if psnr_gap < -5:
            return False

        return True

    def run(self):
        """
        Run test

        :return: Boolean
        """

        if not self._env_check():
            return False
        if not self._get_info():
            return False
        if not self._execute_test_cmd():
            return False

        if self._ref_type.lower() == 'md5':
            return self._check_md5()
        if self._ref_type.lower() == 'psnr':
            return self._check_psnr()

        if self._feature != 'playback':
            self.log.error('Invaild reference type, only support md5 and psnr')
            return False

        return True


def main():
    """
    Arguments parser and test executor
    """

    parser = argparse.ArgumentParser(prog="run_test.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('id', help="Id of a test")
    args = parser.parse_args()

    configure_logger()

    test_info = TESTS.get(args.id, None)
    if not test_info:
        test_info.log.error(f'{args.id} does not exist')
        exit(ErrorCode.CRITICAL)
    os.environ['DISPLAY'] = ":0.0"

    test = Test(args.id, test_info)
    result = test.run()

    test.log.info('#' * 80)
    if not result:
        test.log.error('TEST FAILED')
    else:
        test.log.info('TEST PASSED')
    test.log.info('#' * 80)
    exit(not result)


if __name__ == '__main__':
    main()
