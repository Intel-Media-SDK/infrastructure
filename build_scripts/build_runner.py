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
This module uses for CI building of MediaSDK product.

It contains steps:
    clean - preparing directory to build
    extract - preparing sources for build (getting repositories)
    build - building product
    install - creating installation of the product
    pack - create archives with logs of each step, results of building and installation
    copy - copying archives to share folder

During manual running, only the "build" step is performed if stage is not specified
"""

import argparse
import json
import multiprocessing
import os
import pathlib
import platform
import re
import shutil
import sys
import logging
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from build_scripts.common_runner import ConfigGenerator, Action, RunnerException
from common.helper import Stage, Product_type, Build_event, Build_type, make_archive, \
    copy_win_files, rotate_dir, cmd_exec, copytree, get_packing_cmd, ErrorCode, TargetArch, extract_archive, create_file

from common.logger_conf import configure_logger
from common.git_worker import ProductState
from common.mediasdk_directories import MediaSdkDirectories
from common.build_number import get_build_number
from common.manifest_manager import Manifest, Component, Repository


class UnsupportedVSError(RunnerException):
    """
    Error, which need to be raised
    if Visual Studio version not supported
    """


class VsComponent(Action):
    """
    Windows .sln files builder
    """

    _vs_paths = {
        'vs2005': {
            'ms_build': r'C:\Windows\Microsoft.NET\Framework\v2.0.50727;',
            'vcvars': r'C:\Program Files (x86)\Microsoft Visual Studio 8\VC;'
        },
        'vs2013': {
            'ms_build': r'C:\Program Files (x86)\MSBuild\12.0\Bin;',
            'vcvars': r'C:\Program Files (x86)\Microsoft Visual Studio 12.0\VC;'
        },
        'vs2015': {
            'ms_build': r'C:\Program Files (x86)\MSBuild\14.0\Bin;',
            'vcvars': r'C:\Program Files (x86)\Microsoft Visual Studio 14.0\VC;'
        },
        'vs2017': {
            'ms_build': r'C:\Program Files (x86)\Microsoft Visual Studio 15.0\MSBuild\15.0\Bin;',
            'vcvars': r'C:\Program Files (x86)\Microsoft Visual Studio 15.0\VC\Auxiliary\Build;'
        }
    }

    def __init__(self, name, solution_path, msbuild_args, vs_version,
                 dependencies, env, verbose):
        """
        :param name: Name of action
        :type name: String

        :param solution_path: Path to solution file
        :type solution_path: pathlib.Path

        :param msbuild_args: Arguments of 'msbuild'
        :type msbuild_args: Dictionary

        :param vs_version: Version of Visual Studio
        :type vs_version: String

        :param dependencies: Dependency of other actions
        :type dependencies: List

        :param env: Environment variables for script
        :type env: None | Dict

        :param verbose: Flag for output all logs
        :type verbose: Boolean

        :return: None | Exception
        """

        if vs_version not in self._vs_paths:
            raise UnsupportedVSError(f"{vs_version} is not supported")

        super().__init__(name, Stage.BUILD.value, None, None, env, None, verbose)

        self.solution_path = solution_path
        self.vs_version = vs_version
        self.msbuild_args = msbuild_args
        self.dependencies = dependencies

    def _generate_cmd(self):
        """
        Prepare command line of 'msbuild'

        :return: None
        """

        self.env['PATH'] = f'{os.environ["PATH"]};' \
                           f'{self._vs_paths[self.vs_version]["ms_build"]};' \
                           f'{self._vs_paths[self.vs_version]["vcvars"]}'

        if self.vs_version == 'vs2005':
            # maxcpucount not supported in Visual Studio 2005
            if '/maxcpucount' in self.msbuild_args:
                del self.msbuild_args['/maxcpucount']

        ms_build = f'msbuild {self.solution_path}'
        for arg_name, data in self.msbuild_args.items():
            if isinstance(data, dict):
                properties = []
                for prop, value in data.items():
                    properties.append('{}="{}"'.format(prop, value))
                ms_build = f'{ms_build} {arg_name}:{";".join(properties)}'

            else:
                ms_build = f'{ms_build} {arg_name}:{data}'

        if self.vs_version == 'vs2017':
            self.cmd = ['call vcvars64.bat', ms_build]
        else:
            self.cmd = ['call vcvarsall.bat', ms_build]

    def _enable_vs_multi_processor_compilation(self):
        """
        Set multiprocessor compilation for solution projects

        :return: None
        """

        sln_dir = self.solution_path.parent

        with self.solution_path.open('r') as sln_file:
            items = []
            for line in sln_file:
                for item in line.split(', '):
                    if '.vcxproj' in item:
                        items.append(item[1:-1])

        for project in items:
            project = pathlib.Path(project)
            project_path = sln_dir / project
            new_project_name = 'new_' + project.name
            new_project_path = sln_dir / project.parent / new_project_name

            if project_path.exists():
                with new_project_path.open('w') as outfile:
                    with project_path.open('r') as infile:
                        lines = infile.readlines()
                        for index, line in enumerate(lines):
                            outfile.write(line)
                            if line.startswith('    <ClCompile>') and 'MultiProcessorCompilation' \
                                    not in lines[index + 1]:
                                outfile.write(u'      '
                                              u'<MultiProcessorCompilation>'
                                              u'true'
                                              u'</MultiProcessorCompilation>\n')
                project_path.unlink()
                new_project_path.rename(project_path)

    def run(self, options=None):
        """
        Script runner

        :return: None | subprocess.CalledProcessError
        """

        self._generate_cmd()
        self._enable_vs_multi_processor_compilation()

        return super().run(options)


class BuildGenerator(ConfigGenerator):
    """
    Main class.
    Contains commands for building product.
    """

    def __init__(self, build_config_path, root_dir, build_type, product_type, build_event, stage,
                 commit_time=None, changed_repo=None, repo_states_file_path=None, target_arch=None,
                 custom_cli_args=None, target_branch=None, manifest_file=None, component_name=None):
        """
        :param build_config_path: Path to build configuration file
        :type build_config_path: pathlib.Path

        :param root_dir: Main directory for product building
        :type root_dir: pathlib.Path

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :param product_type: Type of product (linux|linux_embedded|linux_pre_si|windows)
        :type product_type: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param stage: Build stage
        :type stage: String

        :param commit_time: Time for getting slice of commits of repositories
        :type commit_time: datetime

        :param changed_repo: Information about changed source repository
        :type changed_repo: String

        :param repo_states_file_path: Path to sources file with revisions
                                      of repositories to reproduce the same build
        :type repo_states_file_path: String

        :param target_arch: Architecture of target platform
        :type target_arch: List

        :param custom_cli_args: Dict of custom command line arguments (ex. 'arg': 'value')
        :type custom_cli_args: Dict
        """

        self._default_stage = Stage.BUILD.value
        super().__init__(root_dir, build_config_path, stage)

        self._product_repos = {}
        self._product = None
        self._product_type = product_type
        self._build_event = build_event
        self._commit_time = commit_time
        self._changed_repo = changed_repo
        self._repo_states = None
        self._build_state_file = root_dir / "build_state"
        self._options.update({
            "REPOS_DIR": root_dir / "repos",
            "BUILD_DIR": root_dir / "build",
            "INSTALL_DIR": root_dir / "install",
            "PACK_DIR": root_dir / "pack",
            "DEPENDENCIES_DIR": root_dir / "dependencies",
            "BUILD_TYPE": build_type,  # sets from command line argument ('release' by default)
            "CPU_CORES": multiprocessing.cpu_count(),  # count of logical CPU cores
            "VARS": {},  # Dictionary of dynamical variables for action() steps
            "ENV": {},  # Dictionary of dynamical environment variables
            "STRIP_BINARIES": False,  # Flag for stripping binaries of build
        })
        self._dev_pkg_data_to_archive = []
        self._install_pkg_data_to_archive = []
        self._custom_cli_args = custom_cli_args
        self._target_arch = target_arch
        self._target_branch = target_branch
        self._manifest_file = manifest_file

        manifest_path = manifest_file if manifest_file else self._config_path.parent / 'manifest.yml'
        if manifest_path.exists():
            self._manifest = Manifest(manifest_path)
        else:
            self._manifest = Manifest()
            self._log.warning('Created empty manifest.')

        if changed_repo:
            changed_repo_dict = changed_repo.split(':')
            self._branch_name = changed_repo_dict[1]
            self._changed_repo_name = changed_repo_dict[0]
        elif repo_states_file_path:
            self._branch_name = 'master'
            repo_states_file = pathlib.Path(repo_states_file_path)
            if repo_states_file.exists():
                with repo_states_file.open() as repo_states_json:
                    self._repo_states = json.load(repo_states_json)
                    for repo_name, repo_state in self._repo_states.items():
                        if repo_state['trigger']:
                            self._branch_name = repo_state['branch']
                            self._changed_repo_name = repo_name
                            break
            else:
                raise Exception(f'{repo_states_file} does not exist')
        elif manifest_file:
            component = self._manifest.get_component(component_name)
            repo = component.trigger_repository
            self._branch_name = repo.branch
            self._changed_repo_name = repo.name
        else:
            self._branch_name = 'master'
            self._changed_repo_name = None

    def _update_global_vars(self):
        self._global_vars.update({
            'vs_component': self._vs_component,
            'stage': Stage,
            'copy_win_files': copy_win_files,
            'args': self._custom_cli_args,
            'product_type': self._product_type,
            'build_event': self._build_event,
            # TODO should be in lower case
            'DEV_PKG_DATA_TO_ARCHIVE': self._dev_pkg_data_to_archive,
            'INSTALL_PKG_DATA_TO_ARCHIVE': self._install_pkg_data_to_archive,
            'get_build_number': get_build_number,
            'get_api_version': self._get_api_version,
            'branch_name': self._branch_name,
            'changed_repo_name': self._changed_repo_name,
            'update_config': self._update_config,
            'target_arch': self._target_arch,
            'commit_time': self._commit_time,
            'get_packing_cmd': get_packing_cmd,
            'get_commit_number': ProductState.get_commit_number,
            'copytree': copytree,
            'manifest': self._manifest,
            'create_file': create_file
        })

    def _get_config_vars(self):
        # TODO add product_repos to global_vars
        if 'PRODUCT_REPOS' in self._config_variables:
            for repo in self._config_variables['PRODUCT_REPOS']:
                self._product_repos[repo['name']] = {
                    'branch': repo.get('branch'),
                    'commit_id': repo.get('commit_id'),
                    'url': MediaSdkDirectories.get_repo_url_by_name(repo['name'])
                }

        self._product = self._config_variables.get('PRODUCT_NAME', 'mediasdk')

    def _action(self, name, stage=None, cmd=None, work_dir=None, env=None, callfunc=None, verbose=False):
        """
        Handler for 'action' from build config file

        :param name: Name of action
        :type name: String

        :param stage: Stage type
        :type stage: Stage

        :param cmd: command line script
        :type cmd: None | String

        :param work_dir: Path where script will execute
        :type work_dir: None | pathlib.Path

        :param env: Environment variables for script
        :type env: None | Dict

        :param callfunc: python function, which need to execute
        :type callfunc: tuple (function_name, args, kwargs) | None

        :return: None | Exception
        """

        if not stage:
            stage = Stage.BUILD.value
        else:
            stage = stage.value

        if not work_dir:
            work_dir = self._options["ROOT_DIR"]
            if stage in [Stage.BUILD.value, Stage.INSTALL.value]:
                work_dir = self._options["BUILD_DIR"]
        if stage == Stage.BUILD.value and self._current_stage == Stage.BUILD.value:
            configure_logger(name, self._options['LOGS_DIR'] / 'build' / f'{name}.log')
        self._actions[stage].append(Action(name, stage, cmd, work_dir, env, callfunc, verbose))

    def _vs_component(self, name, solution_path, msbuild_args=None, vs_version="vs2017",
                      dependencies=None, env=None, verbose=False):
        """
        Handler for VS components

        :param name: Name of action
        :type name: String

        :param solution_path: Path to solution file
        :type solution_path: pathlib.Path

        :param msbuild_args: Arguments of 'msbuild'
        :type msbuild_args: Dictionary

        :param vs_version: Version of Visual Studio
        :type vs_version: String

        :param dependencies: Dependency of other actions
        :type dependencies: List

        :param env: Environment variables for script
        :type env: None | Dict

        :return: None | Exception
        """

        ms_arguments = deepcopy(self._config_variables.get('MSBUILD_ARGUMENTS', {}))
        if msbuild_args:
            for key, value in msbuild_args.items():
                if isinstance(value, dict):
                    ms_arguments[key] = {**ms_arguments.get(key, {}), **msbuild_args[key]}
                else:
                    ms_arguments[key] = msbuild_args[key]
        if self._current_stage == Stage.BUILD.value:
            configure_logger(name, self._options['LOGS_DIR'] / 'build' / f'{name}.log')
        self._actions[Stage.BUILD.value].append(VsComponent(name, solution_path, ms_arguments, vs_version,
                                                            dependencies, env, verbose))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=30))
    def _clean(self):
        """
        Clean build directories

        :return: None | Exception
        """

        remove_dirs = {'BUILD_DIR', 'INSTALL_DIR', 'LOGS_DIR', 'PACK_DIR', 'DEPENDENCIES_DIR'}

        for directory in remove_dirs:
            dir_path = self._options.get(directory)
            if dir_path.exists():
                shutil.rmtree(dir_path)

        self._options["LOGS_DIR"].mkdir(parents=True, exist_ok=True)

        self._log.info('-' * 50)
        self._log.info('CLEANING')

        if self._build_state_file.exists():
            self._log.info('remove build state file %s', self._build_state_file)
            self._build_state_file.unlink()

        for dir_path in remove_dirs:
            self._log.info('remove directory %s', self._options.get(dir_path))

        if not self._run_build_config_actions(Stage.CLEAN.value):
            return False

        return True

    def _extract(self):
        """
        Get and prepare build repositories
        Uses git_worker.py module

        :return: None | Exception
        """

        print('-' * 50)
        self._log.info("EXTRACTING")

        self._options['REPOS_DIR'].mkdir(parents=True, exist_ok=True)
        self._options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        triggered_repo = 'unknown'

        if self._changed_repo:
            repo_name, branch, commit_id = self._changed_repo.split(':')
            triggered_repo = repo_name

            if repo_name not in self._product_repos:
                self._log.critical(f'{repo_name} repository is not defined in the product configuration PRODUCT_REPOS')
                return False

            for repo, data in self._product_repos.items():
                data['trigger'] = False
                if repo == repo_name:
                    data['trigger'] = True
                    if not data.get('branch'):
                        data['branch'] = branch
                        data['commit_id'] = commit_id
                elif not data.get('branch'):
                    if self._target_branch and MediaSdkDirectories.is_release_branch(self._target_branch):
                        data['branch'] = self._target_branch
                    elif MediaSdkDirectories.is_release_branch(branch) and not self._target_branch:
                        data['branch'] = branch
        elif self._repo_states:
            for repo_name, values in self._repo_states.items():
                if repo_name in self._product_repos:
                    if values['trigger']:
                        triggered_repo = repo_name
                    self._product_repos[repo_name]['branch'] = values['branch']
                    self._product_repos[repo_name]['commit_id'] = values['commit_id']
                    self._product_repos[repo_name]['url'] = values['url']
                    self._product_repos[repo_name]['trigger'] = values['trigger']
        elif self._manifest_file:
            component = self._manifest.get_component(self._product)
            for repo in component.repositories:
                if repo.name in self._product_repos:
                    if repo.is_trigger:
                        triggered_repo = repo.name
                    self._product_repos[repo.name]['branch'] = repo.branch
                    self._product_repos[repo.name]['commit_id'] = repo.revision
                    self._product_repos[repo.name]['url'] = repo.url
                    self._product_repos[repo.name]['trigger'] = repo.is_trigger

        product_state = ProductState(self._product_repos,
                                     self._options["REPOS_DIR"],
                                     self._commit_time)

        product_state.extract_all_repos()

        product_state.save_repo_states(self._options["PACK_DIR"] / 'repo_states.json',
                                       trigger=triggered_repo)

        self._save_manifest(product_state)

        shutil.copyfile(self._config_path,
                        self._options["PACK_DIR"] / self._config_path.name)

        test_scenario = self._config_path.parent / f'{self._config_path.stem}_test{self._config_path.suffix}'
        if test_scenario.exists():
            shutil.copyfile(test_scenario,
                            self._options["PACK_DIR"] / test_scenario.name)

        if not self._get_dependencies():
            return False

        if not self._run_build_config_actions(Stage.EXTRACT.value):
            return False

        return True

    def _build(self):
        """
        Execute 'build' stage

        :return: None | Exception
        """

        print('-' * 50)
        self._log.info("BUILDING")

        self._options['BUILD_DIR'].mkdir(parents=True, exist_ok=True)

        if not self._run_build_config_actions(Stage.BUILD.value):
            return False

        if self._options['STRIP_BINARIES']:
            if not self._strip_bins():
                return False

        return True

    def _install(self):
        """
        Execute 'install' stage

        :return: None | Exception
        """

        print('-' * 50)
        self._log.info("INSTALLING")

        self._options['INSTALL_DIR'].mkdir(parents=True, exist_ok=True)

        if not self._run_build_config_actions(Stage.INSTALL.value):
            return False

        return True

    def _pack(self):
        """
        Pack build results
        creates *.tar.gz archives

        Layout:
            pack_root_dir
                install_pkg.tar.gz (store 'install' stage results)
                developer_pkg.tar.gz (store 'build' stage results)
                logs.tar.gz
                repo_states.json

        :return: None | Exception
        """

        print('-' * 50)
        self._log.info("PACKING")

        self._options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        no_errors = True

        if not self._run_build_config_actions(Stage.PACK.value):
            no_errors = False

        if platform.system() == 'Windows':
            extension = "zip"
        elif platform.system() == 'Linux':
            extension = "tar.gz"
        else:
            self._log.critical(f'Can not pack data on this OS: {platform.system()}')
            return False

        # creating install package
        if self._install_pkg_data_to_archive:
            if not make_archive(self._options["PACK_DIR"] / f"install_pkg.{extension}",
                                self._install_pkg_data_to_archive):
                no_errors = False
        else:
            self._log.info('Install package empty. Skip packing.')

        # creating developer package
        if self._dev_pkg_data_to_archive:
            if not make_archive(self._options["PACK_DIR"] / f"developer_pkg.{extension}",
                                self._dev_pkg_data_to_archive):
                no_errors = False
        else:
            self._log.info('Developer package empty. Skip packing.')

        # creating logs package
        logs_data = [
            {
                'from_path': self._options['ROOT_DIR'],
                'relative': [
                    {
                        'path': 'logs'
                    },
                ]
            },
        ]
        if not make_archive(self._options["PACK_DIR"] / f"logs.{extension}",
                            logs_data):
            no_errors = False

        if not no_errors:
            self._log.error('Not all data was packed')
            return False

        return True

    def _copy(self):
        """
        Copy 'pack' stage results to share folder

        :return: None | Exception
        """

        print('-' * 50)
        self._log.info("COPYING")

        branch = 'unknown'
        commit_id = 'unknown'

        if self._changed_repo:
            repo_name, branch, commit_id = self._changed_repo.split(':')
            if commit_id == 'HEAD':
                commit_id = ProductState.get_head_revision(self._options['REPOS_DIR'] / repo_name)
        elif self._repo_states:
            for repo in self._repo_states.values():
                if repo['trigger']:
                    branch = repo['branch']
                    commit_id = repo['commit_id']
        elif self._manifest_file:
            component = self._manifest.get_component(self._product)
            repo = component.trigger_repository
            branch = repo.branch
            commit_id = repo.revision
        else:
            # "--changed-repo" or "--repo-states" arguments are not set, "HEAD" revision and "master" branch are used
            branch = 'master'
            commit_id = 'HEAD'

        build_dir = MediaSdkDirectories.get_build_dir(
            branch, self._build_event, commit_id,
            self._product_type, self._options["BUILD_TYPE"], product=self._product)

        build_url = MediaSdkDirectories.get_build_url(
            branch, self._build_event, commit_id,
            self._product_type, self._options["BUILD_TYPE"], product=self._product)

        build_root_dir = MediaSdkDirectories.get_root_builds_dir()
        rotate_dir(build_dir)

        self._log.info('Copy to %s', build_dir)
        self._log.info('Artifacts are available by: %s', build_url)

        # Workaround for copying to samba share on Linux
        # to avoid exceptions while setting Linux permissions.
        _orig_copystat = shutil.copystat
        shutil.copystat = lambda x, y, follow_symlinks=True: x
        shutil.copytree(self._options['PACK_DIR'], build_dir)
        shutil.copystat = _orig_copystat

        if not self._run_build_config_actions(Stage.COPY.value):
            return False

        if self._build_state_file.exists():
            with self._build_state_file.open() as state:
                build_state = json.load(state)

                if build_state['status'] == "PASS":
                    last_build_path = build_dir.relative_to(build_root_dir)
                    last_build_file = build_dir.parent.parent / f'last_build_{self._product_type}'
                    last_build_file.write_text(str(last_build_path))

        return True

    def _strip_bins(self):
        """
        Strip binaries and save debug information

        :return: Boolean
        """

        self._log.info('-' * 80)
        self._log.info(f'Stripping binaries')

        system_os = platform.system()

        if system_os == 'Linux':
            bins_to_strip = []
            binaries_with_error = []
            executable_bin_filter = ['', '.so']
            search_results = self._options['BUILD_DIR'].rglob('*')

            for path in search_results:
                if path.is_file():
                    if os.access(path, os.X_OK) and path.suffix in executable_bin_filter:
                        bins_to_strip.append(path)

            for result in bins_to_strip:
                orig_file = str(result.absolute())
                debug_file = str((result.parent / f'{result.stem}.sym').absolute())
                self._log.debug('-' * 80)
                self._log.debug(f'Stripping {orig_file}')

                strip_commands = OrderedDict([
                    ('copy_debug', ['objcopy',
                                    '--only-keep-debug',
                                    orig_file,
                                    debug_file]),
                    ('strip', ['strip',
                               '--strip-debug',
                               '--strip-unneeded',
                               '--remove-section=.comment',
                               orig_file]),
                    ('add_debug_link', ['objcopy',
                                        f'--add-gnu-debuglink={debug_file}',
                                        orig_file]),
                    ('set_chmod', ['chmod',
                                   '-x',
                                   debug_file])
                ])

                check_binary_command = f'file {orig_file} | grep ELF'

                for command in strip_commands.values():
                    err, out = cmd_exec(command, shell=False, log=self._log, verbose=False)
                    if err:
                        # Not strip file if it is not binary
                        return_code, out_check_binary = cmd_exec(check_binary_command, shell=True, log=self._log,
                                                                 verbose=False)
                        if return_code:
                            self._log.warning(f"File {orig_file} is not binary")
                            break
                        if orig_file not in binaries_with_error:
                            binaries_with_error.append(orig_file)
                        self._log.error(out)
                        continue

            if binaries_with_error:
                self._log.error('Stripping for next binaries was failed. See full log for details:\n%s',
                                '\n'.join(binaries_with_error))
                return False
        elif system_os == 'Windows':
            pass
        else:
            self._log.error(f'Can not strip binaries on {system_os}')
            return False

        return True

    def _get_api_version(self, repo_name):
        """
            Get major and minor API version for Windows build from mfxdefs.h
            Used for windows weekly build

            :param repo_name: name of repository
            :type repo_name: string

            :return: minor API version, major API version
            :rtype: Tuple
        """

        # TODO: update for using in linux closed and open source builds
        major_version = minor_version = "0"
        header_name = 'mfxdefs.h'

        mfxdefs_path = self._options['REPOS_DIR'] / repo_name / 'include' / header_name
        if mfxdefs_path.exists():
            is_major_version_found = False
            is_minor_version_found = False

            with open(mfxdefs_path, 'r') as lines:
                for line in lines:
                    major_version_pattern = re.search(r'MFX_VERSION_MAJOR\s(\d+)', line)
                    if major_version_pattern:
                        major_version = major_version_pattern.group(1)
                        is_major_version_found = True
                        continue

                    minor_version_pattern = re.search(r'MFX_VERSION_MINOR\s(\d+)', line)
                    if minor_version_pattern:
                        minor_version = minor_version_pattern.group(1)
                        is_minor_version_found = True

            if not is_major_version_found:
                self._log.warning(f'MFX_VERSION_MAJOR does not exist')

            if not is_minor_version_found:
                self._log.warning(f'MFX_VERSION_MINOR does not exist')
        else:
            self._log.warning(f'{header_name} does not exist')

        self._log.info(f'Returned versions: MAJOR {major_version}, MINOR {minor_version}')
        return major_version, minor_version

    def _update_config(self, pkgconfig_dir, update_data, copy_to=None, pattern='*.pc'):
        """
        Change prefix in pkgconfigs

        :param pkgconfig_dir: Path to package config directory
        :type: pathlib.Path

        :param update_data: new data to write to pkgconfigs
        :type: dict

        :param copy_to: optional parameter for creating new dir for pkgconfigs
        :type: String

        :return: Flag whether files were successfully modified
        """

        # Create new dir for pkgconfigs
        if copy_to:
            try:
                copytree(pkgconfig_dir, copy_to)
                pkgconfig_dir = copy_to
                self._log.debug(f"update_config: pkgconfigs were copied from {pkgconfig_dir} to {copy_to}")
            except OSError:
                self._log.error(f"update_config: Failed to copy package configs from {pkgconfig_dir} to {copy_to}")
                raise

        files_list = pkgconfig_dir.glob(pattern)
        for pkgconfig in files_list:
            with pkgconfig.open('r+') as fd:
                self._log.debug(f"update_config: Start updating {pkgconfig}")
                try:
                    current_config_data = fd.readlines()
                    fd.seek(0)
                    fd.truncate()
                    for line in current_config_data:
                        for pattern, data in update_data.items():
                            line = re.sub(pattern, data, line)
                        fd.write(line)
                    self._log.debug(f"update_config: {pkgconfig} is updated")
                except OSError:
                    self._log.error(f"update_config: Failed to update package config: {pkgconfig}")
                    raise

    def _get_dependencies(self):
        deps = self._config_variables.get("DEPENDENCIES", {})
        if not deps:
            return True

        try:
            deps_dir = self._options['DEPENDENCIES_DIR']
            self._log.info(f'Dependencies was found. Trying to extract to {deps_dir}')
            deps_dir.mkdir(parents=True, exist_ok=True)

            self._log.info(f'Creating manifest')

            for dependency in deps:
                self._log.info(f'Getting component {dependency}')
                comp = self._manifest.get_component(dependency)
                if comp:
                    trigger_repo = comp.trigger_repository
                    if trigger_repo:
                        dep_dir = MediaSdkDirectories.get_build_dir(
                            trigger_repo.branch,
                            Build_event.COMMIT.value,
                            trigger_repo.revision,
                            comp.product_type,
                            Build_type.RELEASE.value,
                            product=dependency
                        )

                        try:
                            self._log.info(f'Extracting {dependency} {comp.product_type} artifacts')
                            # TODO: Extension hardcoded for open source. Need to use only .zip in future.
                            extract_archive(dep_dir / f'install_pkg.tar.gz', deps_dir / dependency)
                        except Exception:
                            self._log.exception('Can not extract archive')
                            return False
                    else:
                        self._log.error('There is no repository as a trigger')
                        return False
                else:
                    self._log.error(f'Component {dependency} does not exist in manifest')
                    return False
        except Exception:
            self._log.exception('Exception occurred:')
            return False

        return True

    def _save_manifest(self, product_state):
        repos = []
        for repo in product_state.repo_states:
            repos.append(
                Repository(
                    name=repo.repo_name,
                    url=repo.url,
                    branch=repo.branch_name,
                    revision=repo.commit_id,
                    trigger=repo.is_trigger
                )
            )

        component = self._manifest.get_component(self._product)
        version = component.version if component else '1'

        self._manifest.add_component(Component(self._product, version, repos, self._product_type), replace=True)
        self._manifest.save_manifest(self._options["PACK_DIR"] / 'manifest.yml')


def main():
    """
    Run stages of product build

    :return: None
    """
    parser = argparse.ArgumentParser(prog="build_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--version", action="version", version="%(prog)s 1.0")
    parser.add_argument('-bc', "--build-config", metavar="PATH", required=True,
                        help="Path to a build configuration")
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    parser.add_argument('-r', "--changed-repo", metavar="String",
                        help='''Changed repository information
in format: <repo_name>:<branch>:<commit_id>
(ex: MediaSDK:master:52199a19d7809a77e3a474b195592cc427226c61)''')
    parser.add_argument('-s', "--repo-states", metavar="PATH",
                        help="Path to repo_states.json file")
    parser.add_argument('-m', "--manifest", metavar="PATH",
                        help="Path to manifest.yml file")
    parser.add_argument('-c', "--component", metavar="String",
                        help="Component name that will be built from manifest")
    parser.add_argument('-b', "--build-type", default=Build_type.RELEASE.value,
                        choices=[build_type.value for build_type in Build_type],
                        help='Type of build')
    parser.add_argument('-p', "--product-type", default=Product_type.CLOSED_LINUX.value,
                        choices=[product_type.value for product_type in Product_type],
                        help='Type of product')
    parser.add_argument('-e', "--build-event", default=Build_event.PRE_COMMIT.value,
                        choices=[build_event.value for build_event in Build_event],
                        help='Event of build')
    parser.add_argument("--stage", default=Stage.BUILD.value,
                        choices=[stage.value for stage in Stage],
                        help="Current executable stage")
    parser.add_argument('-t', "--commit-time", metavar='datetime',
                        help="Time of commits (ex. 2017-11-02 07:36:40)")
    parser.add_argument('-ta', "--target-arch",
                        nargs='*',
                        default=[target_arch.value for target_arch in TargetArch],
                        choices=[target_arch.value for target_arch in TargetArch],
                        help='Architecture of target platform')
    parser.add_argument('-tb', "--target-branch",
                        help=f'All not triggered repos will be checkout to this branch.')

    parsed_args, unknown_args = parser.parse_known_args()

    configure_logger()
    if parsed_args.stage != Stage.CLEAN.value:
        configure_logger(logs_path=pathlib.Path(parsed_args.root_dir) / 'logs' / f'{parsed_args.stage}.log')
    log = logging.getLogger('build_runner.main')

    # remove duplicated values
    target_arch = list(set(parsed_args.target_arch))

    custom_cli_args = {}
    if unknown_args:
        for arg in unknown_args:
            try:
                arg = arg.split('=')
                custom_cli_args[arg[0]] = arg[1]
            except:
                log.exception(f'Wrong argument layout: {arg}')
                exit(ErrorCode.CRITICAL)

    if parsed_args.commit_time:
        commit_time = datetime.strptime(parsed_args.commit_time, '%Y-%m-%d %H:%M:%S')
    else:
        commit_time = None

    try:
        build_config = BuildGenerator(
            build_config_path=pathlib.Path(parsed_args.build_config).absolute(),
            root_dir=pathlib.Path(parsed_args.root_dir).absolute(),
            build_type=parsed_args.build_type,
            product_type=parsed_args.product_type,
            build_event=parsed_args.build_event,
            commit_time=commit_time,
            changed_repo=parsed_args.changed_repo,
            repo_states_file_path=parsed_args.repo_states,
            custom_cli_args=custom_cli_args,
            stage=parsed_args.stage,
            target_arch=target_arch,
            target_branch=parsed_args.target_branch,
            manifest_file=parsed_args.manifest,
            component_name=parsed_args.component
        )

        if not parsed_args.changed_repo \
                and not parsed_args.repo_states \
                and (not parsed_args.manifest or not parsed_args.component):
            log.warning('"--changed-repo" or "--repo-states" or "--manifest" and "--component" '
                        'arguments are not set, "HEAD" revision and "master" branch will be used')
        elif parsed_args.changed_repo and parsed_args.repo_states:
            log.warning('The --repo-states argument is ignored because the --changed-repo is set')

        # prepare build configuration
        if build_config.generate_config():
            # run stage of build
            no_errors = build_config.run_stage(parsed_args.stage)
        else:
            log.critical('Failed to process the product configuration')
            no_errors = False

    except Exception:
        no_errors = False
        log.exception('Exception occurred')

    build_state_file = pathlib.Path(parsed_args.root_dir) / 'build_state'
    if no_errors:
        if not build_state_file.exists():
            build_state_file.write_text(json.dumps({'status': "PASS"}))
        log.info('-' * 50)
        log.info("%s STAGE COMPLETED", parsed_args.stage.upper())
    else:
        build_state_file.write_text(json.dumps({'status': "FAIL"}))
        log.error('-' * 50)
        log.error("%s STAGE FAILED", parsed_args.stage.upper())
        exit(ErrorCode.CRITICAL.value)


if __name__ == '__main__':
    main()
