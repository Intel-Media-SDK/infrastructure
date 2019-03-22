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
import logging

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from ted_adapter import adapter_conf
from common.mediasdk_directories import MediaSdkDirectories, THIRD_PARTY
from common.helper import TestReturnCodes, Product_type, Build_type, Build_event, rotate_dir
from smoke_test.config import LOG_PATH, LOG_NAME
from common.logger_conf import configure_logger
from test_scripts import components_installer


class TedAdapter(object):
    """
    Wrapper for 'ted'
    """

    test_driver_dir = pathlib.Path(__file__).resolve().parents[2] / 'infrastructure'
    test_results_dir = test_driver_dir / 'ted/results'
    dispatcher_dir = adapter_conf.MEDIASDK_PATH / 'lib64'
    test_adapter_log_dir = test_driver_dir / 'ted_adapter/logs'
    test_adapter_log_name = 'test_adapter.log'
    tests_timeout = 300  # 5 minutes

    def __init__(self, build_artifacts_dir, tests_artifacts_dir, tests_artifacts_url, root_dir):
        """
        :param build_artifacts_dir: Path to build artifacts
        :type build_artifacts_dir: pathlib.Path

        :param tests_artifacts_dir: Path to tests artifacts
        :type tests_artifacts_dir: pathlib.Path

        :param tests_artifacts_url: URL to tests artifacts
        :type tests_artifacts_url: String

        :param root_dir: Path to workdir for unpacking build artifacts
        :type root_dir: pathlib.Path
        """

        self.build_artifacts_dir = build_artifacts_dir
        self.tests_artifacts_dir = tests_artifacts_dir
        self.tests_artifacts_url = tests_artifacts_url
        self.root_dir = root_dir

        self.env = os.environ.copy()
        # Path to dispatcher lib should be in the libraries search path
        self.env['LD_LIBRARY_PATH'] = self.dispatcher_dir

        configure_logger(logs_path=self.test_adapter_log_dir / 'test_adapter.log')
        self.log = logging.getLogger(self.test_adapter_log_name)

    def _get_artifacts(self):
        """
        Get artifacts archive from share
        and extract them

        :return: None
        """

        pkg_name = 'install_pkg.tar.gz'
        remote_pkg = self.build_artifacts_dir / pkg_name

        # TODO: implement exceptions

        # Clean workdir and re-create it
        self._remove(str(self.root_dir))
        self._mkdir(str(self.root_dir))

        # Copy `install_pkg.tar` to the workdir and untar it
        self._copy(str(remote_pkg), str(self.root_dir))
        self._untar(str(self.root_dir / pkg_name), str(self.root_dir))

    def install_pkgs(self, pkgs, clean_dir=False):
        """

        Install packages required for testing

        :param pkgs: packages to install
        :type: list

        :param clean_dir: flag for clean up after package uninstalling
        :type: bool

        :return: Flag whether all required packages installed
        :rtype: Bool
        """

        # Workaround for manual artifacts copying
        # Change permission of folder /opt/intel/mediasdk for mediasdk user to call rm without sudo
        if adapter_conf.MEDIASDK_PATH.exists():
            self._change_permission(adapter_conf.MEDIASDK_PATH)
        if clean_dir and self._remove(adapter_conf.MEDIASDK_PATH) != 0:
            # Force clean up package directory
            self.log.info(f'Directory {adapter_conf.MEDIASDK_PATH} was not cleaned up')

        manifest_path = self.build_artifacts_dir / 'manifest.yml'
        components_installer.install_components(manifest_path, pkgs)

        if adapter_conf.MEDIASDK_PATH.exists():
            self._change_permission(adapter_conf.MEDIASDK_PATH)

        return True

    def run_test(self):
        """
        'Ted' runner

        :return: Count of failed cases
        :rtype: Integer | Exception
        """

        self._get_artifacts()

        # Path to mediasdk fodler which will be tested
        self.env['MFX_HOME'] = adapter_conf.MEDIASDK_PATH
        # Path to the folder lib64 where located driver
        self.env['LIBVA_DRIVERS_PATH'] = adapter_conf.DRIVER_PATH

        process = subprocess.run('python3 ted/ted.py',
                                 shell=True,
                                 cwd=self.test_driver_dir,
                                 env=self.env,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode

    def run_fei_tests(self):
        """
        'hevc_fei_smoke_test' runner

        :return: SUCCESS = 0, ERROR_TEST_FAILED = 1, ERROR_ACCESS_DENIED = 2
        :rtype: Integer | Exception
        """
        print(f'Running hevc fei smoke tests...', flush=True)
        process = subprocess.run(f'python3 ../smoke_test/hevc_fei_smoke_test.py',
                                 shell=True,
                                 env=self.env,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode

    def copy_logs_to_share(self):
        rotate_dir(self.tests_artifacts_dir)
        print(f'Copy results to {self.tests_artifacts_dir}')
        print(f'Artifacts are available by: {self.tests_artifacts_url}')

        # Workaround for copying to samba share on Linux to avoid exceptions while setting Linux permissions.
        _orig_copystat = shutil.copystat
        shutil.copystat = lambda x, y, follow_symlinks=True: x
        shutil.copytree(self.test_results_dir, self.tests_artifacts_dir, ignore=shutil.ignore_patterns('bin'))
        shutil.copyfile(LOG_PATH, str(self.tests_artifacts_dir / LOG_NAME))
        shutil.copyfile(str(self.test_adapter_log_dir / self.test_adapter_log_name),
                        str(self.root_dir / self.test_adapter_log_name))
        shutil.copystat = _orig_copystat

    # Direct calls of rm, cp commands needs to use them with `sudo`
    # because we need to copy CI build artifacts to the
    # `/opt/intel/mediasdk`
    # Note: user should be sudoer without asking the password!
    def _remove(self, directory: str, sudo=False):
        return self._execute_command(f"rm -rf {directory}", sudo)

    def _change_permission(self, directory: str, user='mediasdk', sudo=True):
        return self._execute_command(f"chown -R {user}:{user} {directory}", sudo)

    def _copy(self, target_directory: str, destination_directory: str, sudo=False):
        return self._execute_command(f"cp -r {target_directory} {destination_directory}", sudo)

    # TODO use extract_archive() from common.helper
    def _untar(self, archive_path, destination_path):
        with tarfile.open(archive_path, 'r:gz') as archive:
            archive.extractall(path=destination_path)

    def _mkdir(self, path):
        return self._execute_command(f"mkdir -p {path}")

    def _execute_command(self, command, sudo=False):
        prefix = "sudo" if sudo else ""
        process = subprocess.run(f"{prefix} {command}",
                                 shell=True,
                                 timeout=self.tests_timeout,
                                 encoding='utf-8',
                                 errors='backslashreplace')
        return process.returncode


def _driver_exists():
    return (adapter_conf.DRIVER_PATH / adapter_conf.DRIVER).exists()


def check_driver():
    if not _driver_exists():
        print(f"Driver was not found in this location: {adapter_conf.DRIVER_PATH}")
        print(f"Install the driver and run ted again.")
        exit(1)


def main():
    """
    Tests runner

    :return: None
    """

    # Check existence of driver
    check_driver()

    parser = argparse.ArgumentParser(prog="test_adapter.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument('-br', "--branch", metavar="String", required=True,
                        help="Branch of triggered repository")
    parser.add_argument('-e', "--build-event", default='commit',
                        choices=[build_event.value for build_event in Build_event],
                        help='Event of commit')
    parser.add_argument('-c', "--commit-id", metavar="String", required=True,
                        help="SHA of triggered commit")
    parser.add_argument('-p', "--product-type", default='closed_linux',
                        choices=[product_type.value for product_type in Product_type],
                        help='Type of product')
    parser.add_argument('-b', "--build-type", default='release',
                        choices=[build_type.value for build_type in Build_type],
                        help='Type of build')
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    args = parser.parse_args()

    directories_layout = {
        'branch': args.branch,
        'build_event': args.build_event,
        'commit_id': args.commit_id,
        'product_type': args.product_type,
        'build_type': args.build_type,
    }
    build_artifacts_dir = MediaSdkDirectories.get_build_dir(**directories_layout)
    tests_artifacts_dir = MediaSdkDirectories.get_test_dir(**directories_layout)
    tests_artifacts_url = MediaSdkDirectories.get_test_url(**directories_layout)

    log = logging.getLogger('test_adapter.log')
    adapter = TedAdapter(build_artifacts_dir, tests_artifacts_dir, tests_artifacts_url,
                         root_dir=pathlib.Path(args.root_dir))

    # Install third parties for msdk
    if not adapter.install_pkgs(THIRD_PARTY):
        log.info(f'Required packages "{THIRD_PARTY}" were not installed\n')
        exit(TestReturnCodes.INFRASTRUCTURE_ERROR.value)

    # Install msdk
    if not adapter.install_pkgs(['mediasdk'], clean_dir=True):
        log.info(f'Package "mediasdk" was not installed\n')
        exit(TestReturnCodes.INFRASTRUCTURE_ERROR.value)

    try:
        tests_return_code = adapter.run_test()
    except Exception:
        print("Exception occurred:\n", traceback.format_exc())
        # TODO return json string
        tests_return_code = TestReturnCodes.INFRASTRUCTURE_ERROR.value

    try:
        tests_return_code |= adapter.run_fei_tests()
    except Exception:
        print("Exception occurred:\n", traceback.format_exc())
        # TODO return json string
        tests_return_code |= TestReturnCodes.INFRASTRUCTURE_ERROR.value

    try:
        adapter.copy_logs_to_share()
    except Exception:
        print("Exception occurred while copying results:\n", traceback.format_exc())
        tests_return_code |= TestReturnCodes.INFRASTRUCTURE_ERROR.value

    exit(tests_return_code)


if __name__ == '__main__':
    main()
