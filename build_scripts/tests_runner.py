# Copyright (c) 2019-2020 Intel Corporation
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
import collections
import os

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from build_scripts.common_runner import ConfigGenerator, RunnerException
from test_scripts.components_installer import install_components
from common.helper import TestStage, ErrorCode, Product_type, Build_type, rotate_dir
from common.logger_conf import configure_logger
from common.git_worker import ProductState
from common.manifest_manager import Manifest, get_test_dir, get_test_url


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

    def __init__(self, root_dir, test_config, manifest, component, current_stage,
                 product_type=None, build_type=None, custom_types=None):
        self._manifest = None
        self._infrastructure_path = pathlib.Path(__file__).resolve().parents[1]

        self._manifest = Manifest(manifest)
        self._component = self._manifest.get_component(component)

        self._default_stage = TestStage.TEST.value
        self._artifacts_layout = None
        self._product_type = product_type

        # TODO: create mapper for all tests combinations of components in product-configs
        if build_type:
            self._component.build_info.set_build_type(build_type)
        if custom_types:
            for comp, prod_type in custom_types.items():
                self._manifest.get_component(comp).build_info.set_product_type(prod_type)

        super().__init__(root_dir, test_config, current_stage)

        self._options.update({"REPOS_DIR": root_dir / "repos"})

    def _update_global_vars(self):
        self._global_vars.update({
            'stage': TestStage,
            'infra_path': self._infrastructure_path,
            'PATH': os.environ["PATH"]
        })

    def _get_config_vars(self):
        if 'ARTIFACTS_LAYOUT' in self._config_variables:
            self._artifacts_layout = self._config_variables['ARTIFACTS_LAYOUT']

    def _run_build_config_actions(self, stage):
        """
        Run actions of selected stage

        :param stage: Stage name
        :type stage: String

        :return: Boolean
        """

        is_passed = True

        for action in self._actions[stage]:
            error_code = action.run(self._options)
            if error_code:
                is_passed = False

        return is_passed

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

        if not self._run_build_config_actions(TestStage.CLEAN.value):
            return False

        return True

    def _extract(self):
        """
        Get and prepare build repositories
        Uses git_worker.py module

        :return: None | Exception
        """

        self._log.info('-' * 50)
        self._log.info("EXTRACTING")

        self._options['REPOS_DIR'].mkdir(parents=True, exist_ok=True)

        repo_states = collections.defaultdict(dict)
        for repo in self._component.repositories:
            repo_states[repo.name]['target_branch'] = repo.target_branch
            repo_states[repo.name]['branch'] = repo.branch
            repo_states[repo.name]['commit_id'] = repo.revision
            repo_states[repo.name]['url'] = repo.url
            repo_states[repo.name]['trigger'] = repo.name == self._component.build_info.trigger

        product_state = ProductState(repo_states, self._options["REPOS_DIR"])

        product_state.extract_all_repos()

        if not self._run_build_config_actions(TestStage.EXTRACT.value):
            return False

        return True

    def _install(self):
        self._log.info('-' * 50)
        self._log.info("INSTALLING")

        components = self._config_variables.get('INSTALL', [])
        if components and not install_components(self._manifest, components):
            return False

        if not self._run_build_config_actions(TestStage.INSTALL.value):
            return False
        return True

    def _test(self):
        self._log.info('-' * 50)
        self._log.info("TESTING")

        is_success = True
        if not self._run_build_config_actions(TestStage.TEST.value):
            is_success = False

        return is_success

    def _copy(self):
        self._log.info('-' * 50)
        self._log.info("COPYING")

        if self._product_type:
            self._component.build_info.set_product_type(self._product_type)
        artifacts_dir = get_test_dir(self._manifest, self._component.name)
        artifacts_url = get_test_url(self._manifest, self._component.name)
        rotate_dir(artifacts_dir)

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

        if not self._run_build_config_actions(TestStage.COPY.value):
            return False

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
    parser.add_argument('-b', "--build-type", default=Build_type.RELEASE.value,
                        choices=[build_type.value for build_type in Build_type],
                        help='Type of build')
    parser.add_argument("--custom-types", nargs='*',
                        help="Set custom product types for components\n"
                             "(ex. component_name:product_type)")
    parser.add_argument("--stage", default=TestStage.TEST.value,
                        choices=[stage.value for stage in TestStage],
                        help="Current executable stage")
    args = parser.parse_args()

    configure_logger()
    if args.stage != TestStage.CLEAN.value:
        configure_logger(logs_path=pathlib.Path(args.root_dir) / 'logs' / f'{args.stage}.log')
    log = logging.getLogger('tests_runner.main')

    custom_types = None
    if args.custom_types:
        custom_types = dict(custom.split(':') for custom in args.custom_types)

    try:
        tests_runner = TestRunner(root_dir=pathlib.Path(args.root_dir),
                                  test_config=pathlib.Path(args.test_config),
                                  manifest=pathlib.Path(args.manifest),
                                  component=args.component,
                                  current_stage=args.stage,
                                  product_type=args.product_type,
                                  build_type=args.build_type,
                                  custom_types=custom_types)

        if tests_runner.generate_config():
            no_errors = tests_runner.run_stage(args.stage)
        else:
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
