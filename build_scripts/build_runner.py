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
import logging
import multiprocessing
import os
import pathlib
import platform
import shutil
import subprocess
import sys
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from enum import Enum
from logging.config import dictConfig


class PartialPackError(Exception):
    """
    Error, which need to be raised
    if stage "pack" have some troubles
    """

    pass


class WrongTriggeredRepo(Exception):
    """
    Error, which need to be raised
    if triggered repo name does not exist
    in PRODUCT_REPOS list of config file
    """

    pass


class UnsupportedVSError(Exception):
    """
    Error, which need to be raised
    if Visual Studio version not supported
    """

    pass


class Error(Enum):
    """
    Container for custom error codes
    """

    CRITICAL = 1


class Stage(Enum):
    """
    Constants for defining stage of build
    """

    CLEAN = "clean"
    EXTRACT = "extract"
    BUILD = "build"
    INSTALL = "install"
    PACK = "pack"
    COPY = "copy"


class Action(object):
    """
    Command line script runner
    """

    def __init__(self, name, stage, cmd, work_dir, env, callfunc):
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
        """

        self.name = name
        self.stage = stage
        self.cmd = cmd
        self.work_dir = work_dir
        self.env = env
        self.callfunc = callfunc

        self.log = logging.getLogger()

    def run(self):
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
            if self.env:
                env.update(self.env)

            self.log.info('cmd: %s', self.cmd)
            self.log.info('work dir: %s', self.work_dir)
            self.log.info('environment: %s', self.env)

            if self.work_dir:
                self.work_dir.mkdir(parents=True, exist_ok=True)

            try:
                completed_process = subprocess.run(self.cmd,
                                                   shell=True,
                                                   env=env,
                                                   cwd=self.work_dir,
                                                   check=True,
                                                   stdout=subprocess.PIPE,
                                                   stderr=subprocess.STDOUT,
                                                   encoding='utf-8',
                                                   errors='backslashreplace')

                self.log.debug(completed_process.stdout)
            except subprocess.CalledProcessError as process_error:
                self.log.error(process_error.stdout)
                raise


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
        }
    }

    def __init__(self, name, solution_path, msbuild_args, vs_version,
                 dependencies, env):
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

        :return: None | Exception
        """

        if vs_version not in self._vs_paths:
            raise UnsupportedVSError(f"{vs_version} is not supported")

        super().__init__(name, Stage.BUILD, None, None, env, None)
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

        self.cmd = ['call vcvarsall.bat', ms_build]

    # TODO check setting property using msbuild
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

    def run(self):
        """
        Script runner

        :return: None | subprocess.CalledProcessError
        """

        self._generate_cmd()
        self._enable_vs_multi_processor_compilation()
        super().run()


class BuildGenerator(object):
    """
    Main class.
    Contains commands for building product.
    """

    def __init__(self, build_config_path, root_dir, build_type, product_type, build_event,
                 commit_time=None, changed_repo=None, fork_url=None):
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
        
        :param fork_url: Link to forked repository
        :type fork_url: String
        """

        self.build_config_path = build_config_path
        self.actions = defaultdict(list)
        self.product_repos = {}
        self.product_type = product_type
        self.build_event = build_event
        self.commit_time = commit_time
        self.changed_repo = changed_repo
        self.fork_url = fork_url
        self.build_state_file = root_dir / "build_state"
        self.default_options = {
            "ROOT_DIR": root_dir,
            "REPOS_DIR": root_dir / "repos",
            "REPOS_FORKED_DIR": root_dir / "repos_forked",
            "BUILD_DIR": root_dir / "build",
            "INSTALL_DIR": root_dir / "install",
            "PACK_DIR": root_dir / "pack",
            "LOGS_DIR": root_dir / "logs",
            "BUILD_TYPE": build_type,  # sets from command line argument ('release' by default)
            "CPU_CORES": multiprocessing.cpu_count(),  # count of logical CPU cores
            "COMMIT_ID": changed_repo.split(':')[-1],
            "REPO_NAME": changed_repo.split(':')[0],
        }
        self.data_to_archive = None
        self.config_variables = {}

        self.log = logging.getLogger()

        # Build and extract in directory for forked repositories in case of commit from forked repository
        if fork_url != f"{MediaSdkDirectories.get_repo_url_by_name(self.default_options['REPO_NAME'])}.git":
            self.default_options["REPOS_DIR"] = self.default_options["REPOS_FORKED_DIR"]

    def generate_build_config(self):
        """
        Build configuration file parser

        :return: None | Exception
        """

        global_vars = {
            'action': self._action,
            'vs_component': self._vs_component,
            'DEFAULT_OPTIONS': self.default_options,
            'Stage': Stage,
            'copy_win_files': copy_win_files
        }

        exec(open(self.build_config_path).read(), global_vars, self.config_variables)

        if 'PRODUCT_REPOS' in self.config_variables:
            for repo in self.config_variables['PRODUCT_REPOS']:
                self.product_repos[repo['name']] = {
                    'branch': repo.get('branch', 'master'),
                    'commit_id': repo.get('commit_id'),
                    'url': MediaSdkDirectories.get_repo_url_by_name(repo['name'])
                }

        self.data_to_archive = self.config_variables.get('DATA_TO_ARCHIVE', [])

    def clean(self):
        """
        Clean build directories

        :return: None | Exception
        """

        remove_dirs = {'BUILD_DIR', 'INSTALL_DIR', 'LOGS_DIR', 'PACK_DIR', 'REPOS_FORKED_DIR'}

        for directory in remove_dirs:
            dir_path = self.default_options.get(directory)
            if dir_path.exists():
                shutil.rmtree(dir_path)

        self.default_options["LOGS_DIR"].mkdir(parents=True, exist_ok=True)

        self.log.info('CLEANING')
        self.log.info('-' * 50)

        if self.build_state_file.exists():
            self.log.info('remove build state file %s', self.build_state_file)
            self.build_state_file.unlink()

        for dir_path in remove_dirs:
            self.log.info('remove directory %s', self.default_options.get(dir_path))

        for action in self.actions[Stage.CLEAN]:
            action.run()

    def extract(self):
        """
        Get and prepare build repositories
        Uses git_worker.py module

        :return: None | Exception
        """

        self.default_options['REPOS_DIR'].mkdir(parents=True, exist_ok=True)
        self.default_options['REPOS_FORKED_DIR'].mkdir(parents=True, exist_ok=True)
        self.default_options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        repo_name, branch, commit_id = self.changed_repo.split(':')

        if repo_name in self.product_repos:
            self.product_repos[repo_name]['branch'] = branch
            self.product_repos[repo_name]['commit_id'] = commit_id
            if self.fork_url:
                self.product_repos[repo_name]['url'] = self.fork_url
        else:
            raise WrongTriggeredRepo('%s repository is not defined in the product '
                                     'configuration PRODUCT_REPOS', repo_name)

        product_state = ProductState(self.product_repos, self.default_options["REPOS_DIR"], self.commit_time)

        product_state.extract_all_repos()

        product_state.save_repo_states(self.default_options["PACK_DIR"] / 'sources.json')

        for action in self.actions[Stage.EXTRACT]:
            action.run()

    def build(self):
        """
        Execute 'build' stage

        :return: None | Exception
        """

        self.default_options['BUILD_DIR'].mkdir(parents=True, exist_ok=True)

        for action in self.actions[Stage.BUILD]:
            action.run()

    def install(self):
        """
        Execute 'install' stage

        :return: None | Exception
        """

        self.default_options['INSTALL_DIR'].mkdir(parents=True, exist_ok=True)

        for action in self.actions[Stage.INSTALL]:
            action.run()

    def pack(self):
        """
        Pack build results
        creates *.tar.gz archives

        Layout:
            pack_root_dir
                install_pkg.tar.gz (store 'install' stage results)
                developer_pkg.tar.gz (store 'build' stage results)
                logs.tar.gz
                sources.json

        :return: None | Exception
        """

        self.default_options['PACK_DIR'].mkdir(parents=True, exist_ok=True)

        for action in self.actions[Stage.PACK]:
            action.run()

        if platform.system() == 'Windows':
            extension = "zip"
        else:
            extension = "tar"

        no_errors = True

        # creating install package
        install_data = [
            {
                'from_path': self.default_options['INSTALL_DIR'],
                'relative': [
                    {
                        'path': 'opt'
                    }
                ]
            }
        ]

        if self.default_options['INSTALL_DIR'].exists() \
                and os.listdir(self.default_options['INSTALL_DIR']):
            if not make_archive(self.default_options["PACK_DIR"] / f"install_pkg.{extension}",
                                install_data):
                no_errors = False
        else:
            self.log.info('%s empty. Skip packing.', self.default_options['INSTALL_DIR'])

        # creating developer package
        if not make_archive(self.default_options["PACK_DIR"] / f"developer_pkg.{extension}",
                            self.data_to_archive):
            no_errors = False

        # creating logs package
        logs_data = [
            {
                'from_path': self.default_options['ROOT_DIR'],
                'relative': [
                    {
                        'path': 'logs'
                    },
                ]
            },
        ]
        if not make_archive(self.default_options["PACK_DIR"] / f"logs.{extension}",
                            logs_data):
            no_errors = False

        if not no_errors:
            raise PartialPackError('Not all data was packed')

    def copy(self):
        """
        Copy 'pack' stage results to share folder

        :return: None | Exception
        """

        _, branch, commit_id = self.changed_repo.split(':')

        build_dir = MediaSdkDirectories.get_build_dir(
            branch, self.build_event, commit_id,
            self.product_type, self.default_options["BUILD_TYPE"])

        build_root_dir = MediaSdkDirectories.get_root_builds_dir()
        rotate_dir(build_dir)

        self.log.info('Copy to %s', build_dir)

        # Workaround for copying to samba share on Linux to avoid exceptions while setting Linux permissions.
        _orig_copystat = shutil.copystat
        shutil.copystat = lambda x, y, follow_symlinks=True: x
        shutil.copytree(self.default_options['PACK_DIR'], build_dir)
        shutil.copystat = _orig_copystat

        for action in self.actions[Stage.COPY]:
            action.run()

        if self.build_state_file.exists():
            with self.build_state_file.open() as state:
                build_state = json.load(state)

                with (build_dir.parent / f'{self.product_type}_status.json').open('w') as build_status:
                    json.dump(build_state, build_status)

                if build_state['status'] == "PASS":
                    last_build_path = build_dir.relative_to(build_root_dir)
                    with (build_dir.parent.parent / f'last_build_{self.product_type}').open('w') as last_build:
                        last_build.write(str(last_build_path))

    def run_stage(self, stage):
        """
        Run certain stage

        :param stage: Stage of build
        :type stage: Stage

        :return: None | Exception
        """

        self.default_options["LOGS_DIR"].mkdir(parents=True, exist_ok=True)

        set_log_file(self.default_options["LOGS_DIR"] / (stage.value + '.log'))
        print('-' * 50)

        # CLEAN stage has it's own log strings inside.
        # This stage remove all log files at first,
        # and then writes results of it's own execution
        if stage != Stage.CLEAN:
            self.log.info("%sING", stage.name)

        if stage == Stage.CLEAN:
            self.clean()
        elif stage == Stage.EXTRACT:
            self.extract()
        elif stage == Stage.BUILD:
            self.build()
        elif stage == Stage.INSTALL:
            self.install()
        elif stage == Stage.PACK:
            self.pack()
        elif stage == Stage.COPY:
            self.copy()

        self.log.info('-' * 50)
        self.log.info("%sING COMPLETED", stage.name)

        if not self.build_state_file.exists():
            with self.build_state_file.open('w') as state:
                state.write(json.dumps({'status': "PASS"}))

    def _action(self, name, stage=Stage.BUILD, cmd=None, work_dir=None, env=None, callfunc=None):
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

        if not work_dir:
            work_dir = self.default_options["ROOT_DIR"]
            if stage in [Stage.BUILD, Stage.INSTALL]:
                work_dir = self.default_options["BUILD_DIR"]
        self.actions[stage].append(Action(name, stage, cmd, work_dir, env, callfunc))

    def _vs_component(self, name, solution_path, msbuild_args=None, vs_version="vs2015",
                      dependencies=None, env=None):
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
                                                     dependencies, env))


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
    parser.add_argument('-f', "--fork-url", metavar="URL", help='Link to forked repository')
    parser.add_argument('-b', "--build-type", default='release',
                        choices=['release', 'debug'],
                        help='Type of build')
    parser.add_argument('-p', "--product-type", default='linux',
                        choices=['linux', 'embedded', 'open_source', 'windows', 'api_latest', 'embedded_private'],
                        help='Type of product')
    parser.add_argument('-e', "--build-event", default='commit',
                        choices=['pre_commit', 'commit', 'nightly', 'weekly'],
                        help='Event of build')
    parser.add_argument("--stage", type=Stage, choices=Stage, default='build',
                        help="Current executable stage")
    parser.add_argument('-t', "--commit-time", metavar='datetime',
                        help="Time of commits (ex. 2017-11-02 07:36:40)")
    args = parser.parse_args()

    if args.commit_time:
        commit_time = datetime.strptime(args.commit_time, '%Y-%m-%d %H:%M:%S')
    else:
        commit_time = None

    build_config = BuildGenerator(
        pathlib.Path(args.build_config).absolute(),
        pathlib.Path(args.root_dir).absolute(),
        args.build_type,
        args.product_type,
        args.build_event,
        commit_time,
        args.changed_repo,
        args.fork_url
    )

    # We must create BuildGenerator anyway.
    # If generate_build_config will be inside constructor
    # and fails, class will not be created.
    log = logging.getLogger()
    dictConfig(LOG_CONFIG)

    try:
        build_config.generate_build_config()
        build_config.run_stage(args.stage)
    except Exception:
        set_output_stream('err')
        log.exception("Exception occurred")
        log.error("%sING FAILED", args.stage.name)
        with open(pathlib.Path(args.root_dir) / 'build_state', 'w') as status:
            status.write(json.dumps({'status': "FAIL"}))
        exit(Error.CRITICAL.value)


if __name__ == '__main__':
    if platform.python_version_tuple() < ('3', '6'):
        print('\nERROR: Python 3.6 or higher required')
        exit(Error.CRITICAL.value)
    else:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from common import LOG_CONFIG
        from common import ProductState, MediaSdkDirectories
        from common import make_archive, set_output_stream, set_log_file, copy_win_files
        from common.helper import rotate_dir

        main()
