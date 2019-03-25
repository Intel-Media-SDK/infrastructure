import os
import sys
import logging
import pathlib
import argparse

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.helper import cmd_exec
from common.logger_conf import configure_logger
from common.manifest_manager import Manifest


class TestsRunnerException(Exception):
    pass


class ArtifactsNotFoundException(TestsRunnerException):
    pass


class TestScenarioNotFoundException(TestsRunnerException):
    pass


class Action(object):
    """
    Command line script runner
    """

    def __init__(self, name, cmd, work_dir, env, verbose):
        """
        :param name: Name of action
        :type name: String

        :param cmd: command line script
        :type cmd: String

        :param work_dir: Path where script will execute
        :type work_dir: pathlib.Path

        :param env: Environment variables for script
        :type env: Dict

        :param verbose: Flag for output all logs
        :type verbose: Boolean
        """

        self.cmd = cmd
        self.work_dir = work_dir
        self.env = env
        self.verbose = verbose

        self.log = logging.getLogger(name)

    def run(self):
        """
        Script runner

        :return: None | subprocess.CalledProcessError
        """

        self.log.info('-' * 50)

        if self.cmd:
            if isinstance(self.cmd, list):
                self.cmd = ' && '.join(self.cmd)

            env = os.environ.copy()

            if self.env:
                env.update(self.env)

            if self.work_dir:
                self.work_dir.mkdir(parents=True, exist_ok=True)

            error_code, out = cmd_exec(self.cmd, env=env, cwd=self.work_dir, log=self.log)

            if error_code:
                self.log.error(out)
                self.log.error('failed')
            else:
                if self.verbose:
                    self.log.info(out)
                    self.log.info('completed')
                else:
                    self.log.debug(out)
                    self.log.debug('completed')

            return error_code


class TestRunner:
    def __init__(self, artifacts_dir, root_dir):
        self._artifacts_dir = pathlib.Path(artifacts_dir)
        self._root_dir = pathlib.Path(root_dir)
        self._actions = []
        self._config_variables = {}

        if self._artifacts_dir.exists():
            self._manifest = Manifest(self._artifacts_dir / 'manifest.yml')
            try:
                self._scenario = list(self._artifacts_dir.glob('conf_*_test.py'))[0]
            except Exception:
                raise TestScenarioNotFoundException('Test scenario does not exist')
        else:
            raise ArtifactsNotFoundException(f'{self._artifacts_dir} does not exist')

        self._log = logging.getLogger(self.__class__.__name__)

    def _clean(self):
        self._log.info('Cleaning')
        pass

    def _read_scenario(self):
        pass

    def _install_components(self):
        pass

    def _run_tests(self):
        pass

    def _action(self, name, cmd=None, work_dir=None, env=None, verbose=False):
        """
        Handler for 'action' from build config file

        :param name: Name of action
        :type name: String

        :param cmd: command line script
        :type cmd: None | String

        :param work_dir: Path where script will execute
        :type work_dir: None | pathlib.Path

        :param env: Environment variables for script
        :type env: None | Dict

        :return: None | Exception
        """

        if not work_dir:
            work_dir = self._root_dir
            configure_logger(name, self._root_dir / 'logs' / f'{name}.log')
        self._actions.append(Action(name, cmd, work_dir, env, verbose))

    def run(self):
        self._clean()
        self._read_scenario()
        self._install_components()
        self._run_tests()


def main():
    parser = argparse.ArgumentParser(prog="tests_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-ad', "--artifacts-dir", metavar="PATH", required=True,
                        help="Path to a build configuration")
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")

    args = parser.parse_args()

    configure_logger(logs_path=pathlib.Path(args.root_dir) / 'logs' / 'tests_runner.log')

    log = logging.getLogger('tests_runner.main')
    try:
        tests_runner = TestRunner(artifacts_dir=args.artifacts_dir,
                                  root_dir=args.root_dir)
        if not tests_runner.run():
            log.error('TESTS FAILED')
    except Exception:
        log.exception('Exception occurred:')
        log.error('TESTS FAILED')
        exit(1)

    log.info('TESTS PASSED')


if __name__ == '__main__':
    main()