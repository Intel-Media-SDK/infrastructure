import os
import sys
import logging
import pathlib
import argparse

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.helper import Stage, ErrorCode
from common.logger_conf import configure_logger
from common.manifest_manager import Manifest
from build_scripts.build_runner import Action


class TestsRunnerException(Exception):
    pass


class ArtifactsNotFoundException(TestsRunnerException):
    pass


class TestScenarioNotFoundException(TestsRunnerException):
    pass


class TestRunner:
    def __init__(self, artifacts_dir, root_dir):
        self._artifacts_dir = pathlib.Path(artifacts_dir)
        self._root_dir = pathlib.Path(root_dir)
        self._actions = {}
        self._config_variables = {}
        self._config_path = None

        if self._artifacts_dir.exists():
            self._manifest = Manifest(self._artifacts_dir / 'manifest.yml')
            try:
                self._config_path = list(self._artifacts_dir.glob('conf_*_test.py'))[0]
            except Exception:
                raise TestScenarioNotFoundException('Test scenario does not exist')
        else:
            raise ArtifactsNotFoundException(f'{self._artifacts_dir} does not exist')

        self._log = logging.getLogger(self.__class__.__name__)

    def _clean(self):
        self._log.info('-' * 50)
        self._log.info("CLEANING")

        return True

    def _install(self):
        self._log.info('-' * 50)
        self._log.info("INSTALLING")

        return True

    def _test(self):
        self._log.info('-' * 50)
        self._log.info("TESTING")

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
            stage = Stage.TEST.value
        else:
            stage = stage.value

        if not work_dir:
            work_dir = self._root_dir

        self._actions[stage].append(Action(name, stage, cmd, work_dir, env, callfunc, verbose))

    def generate_config(self):

        global_vars = {
            'action': self._action,
            'stage': Stage,
            'log': self._log
        }

        exec(open(self._config_path).read(), global_vars, self._config_variables)

        # TODO get variables from test scenario

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

        self._log.error(f'Stage {stage} does not support')
        return False


def main():
    parser = argparse.ArgumentParser(prog="tests_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-ad', "--artifacts-dir", metavar="PATH", required=True,
                        help="Path to a build configuration")
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    parser.add_argument("--stage", default=Stage.BUILD.value,
                        choices=[stage.value for stage in Stage],
                        help="Current executable stage")
    args = parser.parse_args()

    configure_logger()
    if args.stage != Stage.CLEAN.value:
        configure_logger(logs_path=pathlib.Path(args.root_dir) / 'logs' / f'{args.stage}.log')
    log = logging.getLogger('tests_runner.main')

    try:
        tests_runner = TestRunner(artifacts_dir=args.artifacts_dir,
                                  root_dir=args.root_dir)

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
        log.info("%sING COMPLETED", args.stage.upper())
    else:
        log.error('-' * 50)
        log.error("%sING FAILED", args.stage.upper())
        exit(ErrorCode.CRITICAL.value)


if __name__ == '__main__':
    main()
