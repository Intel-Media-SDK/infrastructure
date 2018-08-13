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

import adapter_conf


class TestAdapter(object):
    """
    Wrapper for 'ted'
    """

    #TODO: add relevant path and delete it
    test_driver_dir = pathlib.Path('/localdisk/bb/worker/infrastructure') #TODO: hardcoded path
    test_results_dir = test_driver_dir / 'ted/results'
    tests_timeout = 300  # 5 minutes

    def __init__(self, build_artifacts_dir, tests_artifacts_dir, root_dir):
        """
        :param build_artifacts_dir: Path to build artifacts
        :type build_artifacts_dir: pathlib.Path

        :param tests_artifacts_dir: Path to tests artifacts
        :type tests_artifacts_dir: pathlib.Path

        :param root_dir: Path to workdir for unpacking build artifacts
        :type root_dir: pathlib.Path
        """

        self.build_artifacts_dir = build_artifacts_dir
        self.tests_artifacts_dir = tests_artifacts_dir
        self.root_dir = root_dir

    def _get_artifacts(self):
        """
        Get artifacts archive from share
        and extract them

        :return: None
        """

        pkg_name = 'install_pkg.tar'
        remote_pkg = self.build_artifacts_dir / pkg_name

        #TODO: implement exceptions

        # Clean workdir and re-create it
        self._remove(str(self.root_dir))
        self._mkdir(str(self.root_dir))

        # Copy `install_pkg.tar` to the workdir and untar it
        self._copy(str(remote_pkg), str(self.root_dir))
        #_untar(str(self.root_dir / pkg_name))
        self._untar(str(self.root_dir / pkg_name), str(self.root_dir))

        # Remove old `/opt/intel/mediasdk` and copy fresh built artifacts
        self._remove(str(adapter_conf.MEDIASDK_PATH), sudo=True)
        self._copy(str(self.root_dir / 'opt' / 'intel' / 'mediasdk'), str(adapter_conf.MEDIASDK_PATH), sudo=True)


    def run_test(self):
        """
        'Ted' runner

        :return: Count of failed cases
        :rtype: Integer | Exception
        """

        self._get_artifacts()

        env = os.environ.copy()
        env['MFX_HOME'] = str(adapter_conf.MEDIASDK_PATH)
        env['LIBVA_DRIVERS_PATH'] = str(adapter_conf.DRIVER_PATH)

        process = subprocess.run('python3 ted/ted.py',
                                 shell=True,
                                 cwd=self.test_driver_dir,
                                 env=env,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode

    def copy_logs_to_share(self):
        rotate_dir(self.tests_artifacts_dir)
        print(f'Copy results to {self.tests_artifacts_dir}')

        # Workaround for copying to samba share on Linux to avoid exceptions while setting Linux permissions.
        _orig_copystat = shutil.copystat
        shutil.copystat = lambda x, y, follow_symlinks=True: x
        shutil.copytree(self.test_results_dir, self.tests_artifacts_dir, ignore=shutil.ignore_patterns('bin'))
        shutil.copystat = _orig_copystat

    def _remove(self, directory: str, sudo=False):
        return self._execute_command(f"{prefix} rm -rf {directory}", sudo)

    def _copy(self, target_directory: str, destination_directory: str, sudo=False):
        return self._execute_command(f"{prefix} cp -r {target_directory} {destination_directory}", sudo)

    def _untar(self, archive_path, destination_path):
        #return _execute_command(f"tar xvf {filename}")
        with tarfile.open(archive_path) as archive:
            archive.extractall(path=destination_path)

    def _mkdir(self, path):
        return self._execute_command(f"mkdir -p {path}")

    def _execute_command(self, command, sudo=False):
        prefix = "sudo" if sudo else ""
        process = subprocess.run(f"{prefix} command",
                                 shell=True,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode


def driver_exists():
    return (adapter_conf.DRIVER_PATH / adapter_conf.DRIVER).exists()

def main():
    """
    Tests runner

    :return: None
    """

    if not driver_exists():
        path = str(adapter_conf.DRIVER_PATH)
        print(f"Driver was not found in this location: {path}")
        print(f"Install the driver and run ted again.")
        exit(1)


    parser = argparse.ArgumentParser(prog="build_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument('-br', "--branch", metavar="String", required=True,
                        help="Branch of triggered repository")
    parser.add_argument('-e', "--build-event", default='commit',
                        choices=['pre_commit', 'commit', 'nightly', 'weekly'],
                        help='Event of commit')
    parser.add_argument('-c', "--commit-id", metavar="String", required=True,
                        help="SHA of triggered commit")
    parser.add_argument('-p', "--product-type", default='linux',
                        choices=['linux', 'embedded', 'open_source', 'windows', 'api_latest'],
                        help='Type of product')
    parser.add_argument('-b', "--build-type", default='release',
                        choices=['release', 'debug'],
                        help='Type of build')
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    args = parser.parse_args()

    directories_layout = [
        args.branch,
        args.build_event,
        args.commit_id,
        args.product_type,
        args.build_type
    ]

    build_artifacts_dir = MediaSdkDirectories.get_build_dir(*directories_layout)
    tests_artifacts_dir = MediaSdkDirectories.get_tests_dir(*directories_layout)

    adapter = TestAdapter(build_artifacts_dir, tests_artifacts_dir, root_dir=pathlib.Path(args.root_dir))
    try:
        failed_cases = adapter.run_test()
    except:
        print("Exception occurred:\n", traceback.format_exc())
        # TODO return json string
        failed_cases = 1

    try:
        adapter.copy_logs_to_share()
    except:
        print("Exception occurred while copying results:\n", traceback.format_exc())
        failed_cases = 1

    exit(failed_cases)

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common import MediaSdkDirectories
    from common.helper import rotate_dir
    main()
