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
import shutil
import sys
import logging
from logging.config import dictConfig
from collections import defaultdict, OrderedDict
from copy import deepcopy
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential


class UnsupportedVSError(Exception):
    """
    Error, which need to be raised
    if Visual Studio version not supported
    """

    pass


class Action(object):
    """
    Command line script runner
    """

    def __init__(self, name, stage, cmd, work_dir, env, callfunc, verbose):
        """
        :param name: Name of action
        :type name: String

        :param stage: Stage type
        :type stage: Stage

        :param cmd: command line script
        :type cmd: String

        :param work_dir: Path where script will execute
        :type work_dir: pathlib.Path

        :param env: Environment variables for script
        :type env: Dict

        :param callfunc: python function, which need to execute
        :type callfunc: tuple (function_name, args, kwargs)

        :param verbose: Flag for output all logs
        :type verbose: Boolean
        """

        self.name = name
        self.stage = stage
        self.cmd = cmd
        self.work_dir = work_dir
        self.env = env
        self.callfunc = callfunc
        self.verbose = verbose

        self.log = logging.getLogger()

    def run(self, options=None):
        """
        Script runner

        :return: None | subprocess.CalledProcessError
        """

        self.log.info('-' * 50)
        self.log.info('action: %s', self.name)

        if self.callfunc:
            func, args, kwargs = self.callfunc

            self.log.info('function: %s', func)
            self.log.info('args: %s', args)
            self.log.info('kwargs: %s', kwargs)

            func(*args, **kwargs)

        if self.cmd:
            if isinstance(self.cmd, list):
                self.cmd = ' && '.join(self.cmd)

            env = os.environ.copy()

            if options:
                self.cmd = self.cmd.format_map(options)
                if options.get('ENV'):
                    env.update(options['ENV'])

            if self.env:
                env.update(self.env)

            if self.work_dir:
                self.work_dir.mkdir(parents=True, exist_ok=True)

            error_code, out = cmd_exec(self.cmd, env=env, cwd=self.work_dir, log=self.log)

            if error_code:
                self._parse_logs(out)
            else:
                if self.verbose:
                    self.log.info(out)
                else:
                    self.log.debug(out)

            return error_code

    def _parse_logs(self, stdout):
        self.log.error(stdout)
        output = [""]

        # linux error example:
        # .../graphbuilder.h:19:9: error: ‘class YAML::GraphBuilderInterface’ has virtual ...
        # windows error example:
        # ...decode.cpp(92): error C2220: warning treated as error - no 'executable' file ...
        # LINK : fatal error LNK1257: code generation failed ...

        if platform.system() == 'Windows':
            error_substrings = [' error ']
        elif platform.system() == 'Linux':
            error_substrings = [': error', 'error:']
        else:
            error_substrings = None
            self.log.warning(f'Unsupported OS for parsing errors: {platform.system()}')

        if error_substrings:
            for line in stdout.splitlines():
                if any(error_substring in line for error_substring in error_substrings):
                    output.append(line)
            if len(output) > 1:
                output.append("The errors above were found in the output. "
                              "See full log for details.")
                self.log.error('\n'.join(output))


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

        super().__init__(name, Stage.BUILD, None, None, env, None, verbose)

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


class BuildGenerator(object):
    """
    Main class.
    Contains commands for building product.
    """

    def __init__(self, build_config_path, root_dir, build_type, product_type, build_event,
                 commit_time=None, changed_repo=None, repo_states_file_path=None, repo_url=None, custom_cli_args=None):
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

        :param commit_time: Time for getting slice of commits of repositories
        :type commit_time: datetime

        :param changed_repo: Information about changed source repository
        :type changed_repo: String

        :param repo_states_file_path: Path to sources file with revisions
                                      of repositories to reproduce the same build
        :type repo_states_file_path: String

        :param repo_url: Link to the external repository
                         (repository which is not in mediasdk_directories)
        :type repo_url: String

        :param custom_cli_args: Dict of custom command line arguments (ex. 'arg': 'value')
        :type custom_cli_args: Dict
        """

        self.build_config_path = build_config_path
        self.actions = defaultdict(list)
        self.product_repos = {}
        self.product_type = product_type
        self.build_event = build_event
        self.commit_time = commit_time
        self.changed_repo = changed_repo
        self.repo_states = None
        self.repo_url = repo_url
        self.build_state_file = root_dir / "build_state"
        self.options = {
            "ROOT_DIR": root_dir,
            "REPOS_DIR": root_dir / "repos",
            "REPOS_FORKED_DIR": root_dir / "repos_forked",
            "BUILD_DIR": root_dir / "build",
            "INSTALL_DIR": root_dir / "install",
            "PACK_DIR": root_dir / "pack",
            "LOGS_DIR": root_dir / "logs",
            "BUILD_TYPE": build_type,  # sets from command line argument ('release' by default)
            "CPU_CORES": multiprocessing.cpu_count(),  # count of logical CPU cores
            "VARS": {},  # Dictionary of dynamical variables for action() steps
            "ENV": {},  # Dictionary of dynamical environment variables
            "STRIP_BINARIES": False  # Flag for stripping binaries of build
        }
        self.dev_pkg_data_to_archive = None
        self.install_pkg_data_to_archive = None
        self.config_variables = {}
        self.custom_cli_args = custom_cli_args

        self.log = logging.getLogger()


        # Build and extract in directory for forked repositories
        # in case of commit from forked repository
        if changed_repo:
            changed_repo_name = changed_repo.split(':')[0]
            changed_repo_url = f"{MediaSdkDirectories.get_repo_url_by_name(changed_repo_name)}.git"
            if self.repo_url and self.repo_url != changed_repo_url:
                self.options["REPOS_DIR"] = self.options["REPOS_FORKED_DIR"]
        elif repo_states_file_path:
            repo_states_file = pathlib.Path(repo_states_file_path)
            if repo_states_file.exists():
                with repo_states_file.open() as repo_states_json:
                    self.repo_states = json.load(repo_states_json)
            else:
                raise Exception(f'{repo_states_file} does not exist')

    def generate_build_config(self):
        """
        Build configuration file parser

        :return: None | Exception
        """

        global_vars = {
            'action': self._action,
            'vs_component': self._vs_component,
            'options': self.options,
            'stage': Stage,
            'copy_win_files': copy_win_files,
            'args': self.custom_cli_args,
            'log': self.log,
            'product_type': self.product_type
        }

        exec(open(self.build_config_path).read(), global_vars, self.config_variables)

        if 'PRODUCT_REPOS' in self.config_variables:
            for repo in self.config_variables['PRODUCT_REPOS']:
                self.product_repos[repo['name']] = {
                    'branch': repo.get('branch', 'master'),
                    'commit_id': repo.get('commit_id'),
                    'url': MediaSdkDirectories.get_repo_url_by_name(repo['name'])
                }

        self.dev_pkg_data_to_archive = self.config_variables.get('DEV_PKG_DATA_TO_ARCHIVE', [])
        self.install_pkg_data_to_archive = self.config_variables.get(
            'INSTALL_PKG_DATA_TO_ARCHIVE', [])

        return True

    def run_stage(self, stage):
        """
        Run method "_<stage>" of the class

        :param stage: Stage of build
        :type stage: Stage
        """

        stage_value = f'_{stage.value}'

        if hasattr(self, stage_value):
            return self.__getattribute__(stage_value)()

        self.log.error(f'Stage {stage.value} does not support')
        return False

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
            stage = Stage.BUILD

        if not work_dir:
            work_dir = self.options["ROOT_DIR"]
            if stage in [Stage.BUILD, Stage.INSTALL]:
                work_dir = self.options["BUILD_DIR"]
        self.actions[stage].append(Action(name, stage, cmd, work_dir, env, callfunc, verbose))

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

        ms_arguments = deepcopy(self.config_variables.get('MSBUILD_ARGUMENTS', {}))
        if msbuild_args:
            for key, value in msbuild_args.items():
                if isinstance(value, dict):
                    ms_arguments[key] = {**ms_arguments.get(key, {}), **msbuild_args[key]}
                else:
                    ms_arguments[key] = msbuild_args[key]

        self.actions[Stage.BUILD].append(VsComponent(name, solution_path, ms_arguments, vs_version,
                                                     dependencies, env, verbose))

    def _run_build_config_actions(self, stage):
        for action in self.actions[stage]:
            error_code = action.run(self.options)
            if error_code:
                return False

        return True

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=30))
    def _clean(self):
        """
        Clean build directories

        :return: None | Exception
        """

        remove_dirs = {'BUILD_DIR', 'INSTALL_DIR', 'LOGS_DIR', 'PACK_DIR', 'REPOS_FORKED_DIR'}

        for directory in remove_dirs:
            dir_path = self.options.get(directory)
            if dir_path.exists():
                shutil.rmtree(dir_path)

        self.options["LOGS_DIR"].mkdir(parents=True, exist_ok=True)

        self.log.info('-' * 50)
        self.log.info('CLEANING')

        if self.build_state_file.exists():
            self.log.info('remove build state file %s', self.build_state_file)
            self.build_state_file.unlink()

        for dir_path in remove_dirs:
            self.log.info('remove directory %s', self.options.get(dir_path))

        if not self._run_build_config_actions(Stage.CLEAN):
            return False

        return True

    def _extract(self):
        """
        Get and prepare build repositories
        Uses git_worker.py module

        :return: None | Exception
        """

        set_log_file(self.options["LOGS_DIR"] / 'extract.log')

        print('-' * 50)
        self.log.info("EXTRACTING")

        self.options['REPOS_DIR'].mkdir(parents=True, exist_ok=True)
        self.options['REPOS_FORKED_DIR'].mkdir(parents=True, exist_ok=True)
        self.options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        triggered_repo = 'unknown'

        if self.changed_repo:
            repo_name, branch, commit_id = self.changed_repo.split(':')
            triggered_repo = repo_name
            if repo_name in self.product_repos:
                self.product_repos[repo_name]['branch'] = branch
                self.product_repos[repo_name]['commit_id'] = commit_id
                if self.repo_url:
                    self.product_repos[repo_name]['url'] = self.repo_url
            else:
                self.log.critical(f'{repo_name} repository is not defined in the product '
                                  'configuration PRODUCT_REPOS')
                return False

        elif self.repo_states:
            for repo_name, values in self.repo_states.items():
                if repo_name in self.product_repos:
                    if values['trigger']:
                        triggered_repo = repo_name
                    self.product_repos[repo_name]['branch'] = values['branch']
                    self.product_repos[repo_name]['commit_id'] = values['commit_id']
                    self.product_repos[repo_name]['url'] = values['url']

        product_state = ProductState(self.product_repos,
                                     self.options["REPOS_DIR"],
                                     self.commit_time)

        product_state.extract_all_repos()

        product_state.save_repo_states(self.options["PACK_DIR"] / 'repo_states.json',
                                       trigger=triggered_repo)
        shutil.copyfile(self.build_config_path,
                        self.options["PACK_DIR"] / self.build_config_path.name)

        if not self._run_build_config_actions(Stage.EXTRACT):
            return False

        return True

    def _build(self):
        """
        Execute 'build' stage

        :return: None | Exception
        """

        set_log_file(self.options["LOGS_DIR"] / 'build.log')

        print('-' * 50)
        self.log.info("BUILDING")

        self.options['BUILD_DIR'].mkdir(parents=True, exist_ok=True)

        if not self._run_build_config_actions(Stage.BUILD):
            return False

        if self.options['STRIP_BINARIES']:
            if not self._strip_bins():
                return False

        return True

    def _install(self):
        """
        Execute 'install' stage

        :return: None | Exception
        """

        set_log_file(self.options["LOGS_DIR"] / 'install.log')

        print('-' * 50)
        self.log.info("INSTALLING")

        self.options['INSTALL_DIR'].mkdir(parents=True, exist_ok=True)

        if not self._run_build_config_actions(Stage.INSTALL):
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

        set_log_file(self.options["LOGS_DIR"] / 'pack.log')

        print('-' * 50)
        self.log.info("PACKING")

        self.options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        if not self._run_build_config_actions(Stage.PACK):
            return False

        if platform.system() == 'Windows':
            extension = "zip"
        elif platform.system() == 'Linux':
            extension = "tar"
        else:
            self.log.critical(f'Can not pack data on this OS: {platform.system()}')
            return False

        no_errors = True

        # creating install package
        if self.install_pkg_data_to_archive:
            if not make_archive(self.options["PACK_DIR"] / f"install_pkg.{extension}",
                                self.install_pkg_data_to_archive):
                no_errors = False
        else:
            self.log.info('Install package empty. Skip packing.')

        # creating developer package
        if self.dev_pkg_data_to_archive:
            if not make_archive(self.options["PACK_DIR"] / f"developer_pkg.{extension}",
                                self.dev_pkg_data_to_archive):
                no_errors = False
        else:
            self.log.info('Developer package empty. Skip packing.')

        # creating logs package
        logs_data = [
            {
                'from_path': self.options['ROOT_DIR'],
                'relative': [
                    {
                        'path': 'logs'
                    },
                ]
            },
        ]
        if not make_archive(self.options["PACK_DIR"] / f"logs.{extension}",
                            logs_data):
            no_errors = False

        if not no_errors:
            self.log.error('Not all data was packed')
            return False

        return True

    def _copy(self):
        """
        Copy 'pack' stage results to share folder

        :return: None | Exception
        """

        print('-' * 50)
        self.log.info("COPYING")

        set_log_file(self.options["LOGS_DIR"] / 'copy.log')

        branch = 'unknown'
        commit_id = 'unknown'

        if self.changed_repo:
            _, branch, commit_id = self.changed_repo.split(':')
        elif self.repo_states:
            for repo in self.repo_states:
                if repo['trigger']:
                    branch = repo['branch']
                    commit_id = repo['commit_id']

        build_dir = MediaSdkDirectories.get_build_dir(
            branch, self.build_event, commit_id,
            self.product_type, self.options["BUILD_TYPE"])

        build_root_dir = MediaSdkDirectories.get_root_builds_dir()
        rotate_dir(build_dir)

        self.log.info('Copy to %s', build_dir)

        # Workaround for copying to samba share on Linux
        # to avoid exceptions while setting Linux permissions.
        _orig_copystat = shutil.copystat
        shutil.copystat = lambda x, y, follow_symlinks=True: x
        shutil.copytree(self.options['PACK_DIR'], build_dir)
        shutil.copystat = _orig_copystat

        if not self._run_build_config_actions(Stage.COPY):
            return False

        if self.build_state_file.exists():
            with self.build_state_file.open() as state:
                build_state = json.load(state)

                if build_state['status'] == "PASS":
                    last_build_path = build_dir.relative_to(build_root_dir)
                    last_build_file = build_dir.parent.parent / f'last_build_{self.product_type}'
                    last_build_file.write_text(str(last_build_path))

        return True

    def _strip_bins(self):
        """
        Strip binaries and save debug information

        :return: Boolean
        """

        self.log.info('-' * 80)
        self.log.info(f'Stripping binaries')

        system_os = platform.system()

        if system_os == 'Linux':
            bins_to_strip = []
            binaries_with_error = []
            executable_bin_filter = ['', '.so']
            search_results = self.options['BUILD_DIR'].rglob('*')

            for path in search_results:
                if path.is_file():
                    if os.access(path, os.X_OK) and path.suffix in executable_bin_filter:
                        bins_to_strip.append(path)

            for result in bins_to_strip:
                orig_file = str(result.absolute())
                debug_file = str((result.parent / f'{result.stem}.sym').absolute())
                self.log.debug('-' * 80)
                self.log.debug(f'Stripping {orig_file}')

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

                for command in strip_commands.values():
                    err, out = cmd_exec(command, shell=False, log=self.log, verbose=False)
                    if err:
                        if orig_file not in binaries_with_error:
                            binaries_with_error.append(orig_file)
                        self.log.error(out)
                        continue

            if binaries_with_error:
                self.log.error('Stripping for next binaries was failed. See full log for details:\n%s',
                               '\n'.join(binaries_with_error))
                return False
        elif system_os == 'Windows':
            pass
        else:
            self.log.error(f'Can not strip binaries on {system_os}')
            return False

        return True


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
    parser.add_argument('-f', "--repo-url", metavar="URL", help='''Link to the repository.
In most cases used to specify link to the forked repositories.
Use this argument if you want to specify repository
which is not present in mediasdk_directories.''')
    parser.add_argument('-b', "--build-type", default='release',
                        choices=['release', 'debug'],
                        help='Type of build')
    parser.add_argument('-p', "--product-type", default='linux',
                        choices=['linux', 'embedded', 'open_source', 'windows',
                                 'windows_uwp', 'api_latest', 'embedded_private', 'android',
                                 'linux_gcc_latest', 'linux_clang_latest'],
                        help='Type of product')
    parser.add_argument('-e', "--build-event", default='commit',
                        choices=['pre_commit', 'commit', 'nightly', 'weekly'],
                        help='Event of build')
    parser.add_argument("--stage", type=Stage, choices=Stage, default='build',
                        help="Current executable stage")
    parser.add_argument('-t', "--commit-time", metavar='datetime',
                        help="Time of commits (ex. 2017-11-02 07:36:40)")

    parsed_args, unknown_args = parser.parse_known_args()

    log = logging.getLogger()
    dictConfig(LOG_CONFIG)

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

    build_config = BuildGenerator(
        build_config_path=pathlib.Path(parsed_args.build_config).absolute(),
        root_dir=pathlib.Path(parsed_args.root_dir).absolute(),
        build_type=parsed_args.build_type,
        product_type=parsed_args.product_type,
        build_event=parsed_args.build_event,
        commit_time=commit_time,
        changed_repo=parsed_args.changed_repo,
        repo_states_file_path=parsed_args.repo_states,
        repo_url=parsed_args.repo_url,
        custom_cli_args=custom_cli_args
    )

    # We must create BuildGenerator anyway.
    # If generate_build_config will be inside constructor
    # and fails, class will not be created.
    try:
        if not parsed_args.changed_repo and not parsed_args.repo_states:
            log.error('"--changed-repo" or "--repo-states" argument bust be added')
            exit(ErrorCode.CRITICAL.value)
        elif parsed_args.changed_repo and parsed_args.repo_states:
            log.warning('The --repo-states argument is ignored because the --changed-repo is set')

        # prepare build configuration
        if build_config.generate_build_config():
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
        log.info("%sING COMPLETED", parsed_args.stage.name)
    else:
        build_state_file.write_text(json.dumps({'status': "FAIL"}))
        log.error('-' * 50)
        log.error("%sING FAILED", parsed_args.stage.name)
        exit(ErrorCode.CRITICAL.value)

if __name__ == '__main__':
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from common.helper import ErrorCode

    if platform.python_version_tuple() < ('3', '6'):
        print('\nERROR: Python 3.6 or higher is required')
        exit(ErrorCode.CRITICAL)
    else:
        from common.helper import Stage, make_archive, set_log_file, \
            copy_win_files, rotate_dir, cmd_exec
        from common.logger_conf import LOG_CONFIG
        from common.git_worker import ProductState
        from common.mediasdk_directories import MediaSdkDirectories

        main()
