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
    Module contains base class for build and test runners
"""

import logging
import os
import pathlib
import platform
import multiprocessing
from collections import defaultdict

from common.helper import cmd_exec, ErrorCode
from common.mediasdk_directories import Proxy


class RunnerException(Exception):
    pass


class DefaultStageException(RunnerException):
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
        :type work_dir: pathlib.Path | None

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
        self.env = env if env else {}
        self.callfunc = callfunc
        self.verbose = verbose

        self.log = logging.getLogger(name)

    def run(self, options=None):
        """
        Script runner

        :return: None | subprocess.CalledProcessError
        """

        self.log.info('-' * 50)

        if self.callfunc:
            #TODO: Modify and restore ENV for callfunc too

            func, args, kwargs = self.callfunc

            self.log.info('function: %s', func)
            if args:
                self.log.info('args: %s', args)
            if kwargs:
                self.log.info('kwargs: %s', kwargs)

            try:
                return_value = func(*args, **kwargs)
                return_msg = f'The function returned: {return_value}'
                if isinstance(return_value, bool) and return_value == False:
                    self.log.error(return_msg)
                    error_code = ErrorCode.CRITICAL.value
                else:
                    self.log.info(return_msg)
                    error_code = ErrorCode.SUCCESS.value
            except Exception:
                error_code = ErrorCode.CRITICAL.value
                self.log.exception('Failed to call the function:')
        elif self.cmd:
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
                    self.log.info('completed')
                else:
                    self.log.debug(out)
                    self.log.debug('completed')
        else:
            error_code = ErrorCode.CRITICAL.value
            self.log.critical(f'The action "{self.name}" has not cmd or callfunc parameters')

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


class ConfigGenerator:
    _default_stage = None

    def __init__(self, root_dir, config_path, current_stage):
        self._config_path = config_path
        self._current_stage = current_stage
        self._actions = defaultdict(list)
        self._options = {
            "ROOT_DIR": pathlib.Path(root_dir).absolute(),
            "LOGS_DIR": root_dir / 'logs',
            "CPU_CORES": multiprocessing.cpu_count(),  # count of logical CPU cores
            "VARS": {},  # Dictionary of dynamical variables for action() steps
            "ENV": {},  # Dictionary of dynamical environment variables
        }

        self._log = logging.getLogger(self.__class__.__name__)

        self._config_variables = {}
        self._global_vars = {
            'action': self._action,
            'options': self._options,
            'log': self._log
        }

        if not self._default_stage:
            raise DefaultStageException('_default_stage is not declared.')

    def _update_global_vars(self):
        """
        Set additional variables while executing configuration file;
        It can be used in child classes

        Ex.:
        self._global_vars.update({
            'stage': TestStage
        })
        """

        pass

    def _get_config_vars(self):
        """
        Define variables from configuration file as fields of a runner class;
        It can be used in child classes

        Ex:
        self.product = self._config_variables.get('PRODUCT_NAME', None)
        """

        pass

    def generate_config(self):
        """
        Read configuration file

        :return: Boolean
        """

        try:
            self._update_global_vars()
            exec(open(self._config_path).read(), self._global_vars, self._config_variables)
            self._get_config_vars()
        except Exception:
            self._log.exception(f'Failed to process the product configuration: {self._config_path}')
            return False

        return True

    def run_stage(self, stage):
        """
        Run method "_<stage>" of the class

        :param stage: Stage of build
        :type stage: Stage
        """

        stage_value = f'_{stage}'

        if hasattr(self, stage_value):
            return self.__getattribute__(stage_value)()

        self._log.error(f'Stage {stage} is not supported')
        return False

    def _run_build_config_actions(self, stage):
        """
        Run actions of selected stage

        :param stage: Stage name
        :type stage: String

        :return: Boolean
        """

        for action in self._actions[stage]:
            error_code = action.run(self._options)
            if error_code:
                return False

        return True

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
            stage = self._default_stage
        else:
            stage = stage.value

        if not work_dir:
            work_dir = self._options['ROOT_DIR']

        self._actions[stage].append(Action(name, stage, cmd, work_dir, env, callfunc, verbose))
