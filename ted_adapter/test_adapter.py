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

"""
Module for running tests for MediaSDK open source

This module gets binary files of CI MediaSDK build
from share folder and tests them by 'ted'
"""

import sys
import argparse
import shutil
import subprocess
import os
import pathlib
import tarfile
import traceback


class TestAdapter(object):
    """
    Wrapper for 'ted'
    """

    test_driver_dir = pathlib.Path('/localdisk/bb/worker/test/infrastructure') #TODO: hardcoded path
    tests_timeout = 300  # 5 minutes

    def __init__(self, build_artifacts_dir):
        """
        :param build_artifacts_dir: Path to build artifacts
        :type build_artifacts_dir: pathlib.Path
        """

        self.build_artifacts_dir = build_artifacts_dir

    def _get_artifacts(self):
        """
        Get artifacts archive from share
        and extract them

        :return: None
        """

        pkg_name = 'developer_pkg.tar'
        binaries_dir = self.test_driver_dir / 'bin'
        local_pkg = self.test_driver_dir / 'developer_pkg.tar'
        remote_pkg = self.build_artifacts_dir / pkg_name

        if local_pkg.exists():
            local_pkg.unlink()
        if binaries_dir.exists():
            shutil.rmtree(binaries_dir)

        shutil.copy(remote_pkg, self.test_driver_dir)

        with tarfile.open(local_pkg) as archive:
            archive.extractall(path=self.test_driver_dir)

    def run_test(self):
        """
        'Ted' runner

        :return: Count of failed cases
        :rtype: Integer | Exception
        """

        self._get_artifacts()

        env = os.environ.copy()
        env['MFX_HOME'] = str(self.test_driver_dir)

        process = subprocess.run('python3 ted/ted.py',
                                 shell=True,
                                 cwd=self.test_driver_dir,
                                 env=env,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode


def main():
    """
    Tests runner

    :return: None
    """

    parser = argparse.ArgumentParser(prog="build_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument('-br', "--branch", metavar="String", required=True,
                        help="Branch of triggered repository")
    parser.add_argument('-e', "--build-event", default='commit',
                        choices=['pre_commit', 'commit', 'nightly', 'weekly', 'other-branches', 'api_latest'],
                        help='Event of commit')
    parser.add_argument('-c', "--commit-id", metavar="String", required=True,
                        help="SHA of triggered commit")
    parser.add_argument('-p', "--product-type", default='linux',
                        choices=['linux', 'embedded', 'pre_si', 'windows'],
                        help='Type of product')
    parser.add_argument('-b', "--build-type", default='release',
                        choices=['release', 'debug'],
                        help='Type of build')
    args = parser.parse_args()

    build_artifacts_dir = MediaSdkDirectories.get_build_dir(
        args.branch, args.build_event, args.commit_id, args.product_type, args.build_type)

    try:
        adapter = TestAdapter(build_artifacts_dir)
        failed_cases = adapter.run_test()
    except:
        print("Exception occurred:\n", traceback.format_exc())
        # TODO return json string
        failed_cases = 1

    exit(failed_cases)

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common import MediaSdkDirectories
    main()
