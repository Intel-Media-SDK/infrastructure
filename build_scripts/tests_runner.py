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
This module uses for CI testing of MediaSDK product.

During manual running, only the "test" step is performed if stage is not specified
"""

import sys
import shutil
import logging
import pathlib
import argparse

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from build_scripts.common_runner import ConfigGenerator, RunnerException
from test_scripts.components_installer import install_components
from common.mediasdk_directories import MediaSdkDirectories
from common.helper import TestStage, ErrorCode, Product_type
from common.logger_conf import configure_logger
from common.manifest_manager import Manifest


class ArtifactsNotFoundException(RunnerException):
    """
        Exception for artifacts existence
    """

    pass


class TestScenarioNotFoundException(RunnerException):
    """
        Exception for test scenario
    """

    pass


class TestRunner(ConfigGenerator):
    """
    Main class.
    Contains commands for testing product.
    """

    def __init__(self, root_dir, test_config, manifest, component, current_stage, product_type=None):
        self._manifest = None
        self._infrastructure_path = pathlib.Path(__file__).resolve().parents[1]

        self._manifest = Manifest(manifest)
        self._component = self._manifest.get_component(component)
        self._default_stage = TestStage.TEST.value
        self._artifacts_layout = None
        self._product_type = product_type
        super().__init__(root_dir, test_config, current_stage)

    def _update_global_vars(self):
        self._global_vars.update({
            'stage': TestStage,
            'infra_path': self._infrastructure_path
        })

    def _get_config_vars(self):
        if 'ARTIFACTS_LAYOUT' in self._config_variables:
            self._artifacts_layout = self._config_variables['ARTIFACTS_LAYOUT']

    def _clean(self):
        """
        Clean build directories

        :return: None | Exception
        """

        self._log.info('-' * 50)
        self._log.info("CLEANING")

        remove_dirs = {'ROOT_DIR'}

        for directory in remove_dirs:
            dir_path = self._options.get(directory)
            if dir_path.exists():
                self._log.info(f'remove directory {dir_path}')
                shutil.rmtree(dir_path)

        self._options["LOGS_DIR"].mkdir(parents=True, exist_ok=True)

        return True

    def _install(self):
        self._log.info('-' * 50)
        self._log.info("INSTALLING")

        components = self._config_variables.get('INSTALL', [])

        if not components:
            self._log.error('Nothing to install')
            return False

        return install_components(self._manifest, components)

    def _test(self):
        self._log.info('-' * 50)
        self._log.info("TESTING")

        if not self._run_build_config_actions(TestStage.TEST.value):
            return False
        return True

    def _copy(self):
        self._log.info('-' * 50)
        self._log.info("COPYING")

        repo = self._component.trigger_repository

        args = {
            'branch': repo.target_branch or repo.branch,
            'build_event': self._component.build_info.build_event,
            'commit_id': repo.revision,
            'build_type': self._component.build_info.build_type,
            'product_type': self._product_type or self._component.build_info.product_type,
            'product': self._component.name
        }

        artifacts_dir = MediaSdkDirectories.get_test_dir(**args)
        artifacts_url = MediaSdkDirectories.get_test_url(**args)

        if self._artifacts_layout:
            _orig_copystat = shutil.copystat
            shutil.copystat = lambda x, y, follow_symlinks=True: x

            for local_path, share_dir in self._artifacts_layout.items():
                local_path = pathlib.Path(local_path).resolve()
                if local_path.is_dir():
                    shutil.copytree(local_path, artifacts_dir / share_dir, ignore=shutil.ignore_patterns('bin'))
                elif local_path.is_file():
                    shutil.copyfile(local_path, artifacts_dir / share_dir)

            shutil.copystat = _orig_copystat

            self._log.info(f'Artifacts copied to: {artifacts_dir}')
            self._log.info(f'Artifacts available by link: {artifacts_url}')
        else:
            self._log.info('Nothing to copy')

        return True


def main():
    """
        Run stages of test product

        :return: None
    """

    parser = argparse.ArgumentParser(prog="tests_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    parser.add_argument('-tc', "--test-config", metavar="PATH", required=True,
                        help="Path to a test configuration")
    parser.add_argument('-ar', "--manifest", metavar="PATH", required=True,
                        help="Path to a manifest file or directory with the file")
    parser.add_argument('-c', "--component", metavar="String", required=True,
                        help="Component name that will be built from manifest")
    parser.add_argument('-p', "--product-type",
                        choices=[product_type.value for product_type in Product_type],
                        help='Type of product')
    parser.add_argument("--stage", default=TestStage.TEST.value,
                        choices=[stage.value for stage in TestStage],
                        help="Current executable stage")
    args = parser.parse_args()

    configure_logger()
    if args.stage != TestStage.CLEAN.value:
        configure_logger(logs_path=pathlib.Path(args.root_dir) / 'logs' / f'{args.stage}.log')
    log = logging.getLogger('tests_runner.main')

    try:
        tests_runner = TestRunner(root_dir=pathlib.Path(args.root_dir),
                                  test_config=pathlib.Path(args.test_config),
                                  manifest=pathlib.Path(args.manifest),
                                  component=args.component,
                                  current_stage=args.stage,
                                  product_type=args.product_type)

        if tests_runner.generate_config():
            no_errors = tests_runner.run_stage(args.stage)
        else:
            log.critical('Failed to process the product configuration')
            no_errors = False
    except Exception:
        no_errors = False
        log.exception('Exception occurred:')

    if no_errors:
        log.info('-' * 50)
        log.info("%s STAGE COMPLETED", args.stage.upper())
    else:
        log.error('-' * 50)
        log.error("%s STAGE FAILED", args.stage.upper())
        exit(ErrorCode.CRITICAL.value)


if __name__ == '__main__':
    main()
