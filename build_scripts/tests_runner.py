import os
import sys
import logging
import pathlib
import argparse

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from build_scripts.common_runner import ConfigGenerator
from common.helper import TestStage, ErrorCode
from common.logger_conf import configure_logger
from common.manifest_manager import Manifest


class TestsRunnerException(Exception):
    pass


class ArtifactsNotFoundException(TestsRunnerException):
    pass


class TestScenarioNotFoundException(TestsRunnerException):
    pass


class TestRunner(ConfigGenerator):
    def __init__(self, artifacts, root_dir, current_stage):
        self._artifacts_dir = None
        self._manifest = None

        if artifacts.exists():
            if artifacts.is_file():
                self._artifacts_dir = artifacts.parent
                self._manifest = Manifest(artifacts)
            else:
                self._artifacts_dir = artifacts
                self._manifest = Manifest(artifacts / 'manifest.yml')

            try:
                config_path = list(self._artifacts_dir.glob('conf_*_test.py'))[0]
            except Exception:
                raise TestScenarioNotFoundException('Test scenario does not exist')
        else:
            raise ArtifactsNotFoundException(f'{artifacts} does not exist')

        self._default_stage = TestStage.TEST.value
        super().__init__(root_dir, config_path, current_stage)

    def _update_global_vars(self):
        self._global_vars.update({
            'stage': TestStage
        })

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


def main():
    parser = argparse.ArgumentParser(prog="tests_runner.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-ar', "--artifacts", metavar="PATH", required=True,
                        help="Path to a manifest file or directory with the file")
    parser.add_argument('-d', "--root-dir", metavar="PATH", required=True,
                        help="Path to worker directory")
    parser.add_argument("--stage", default=TestStage.TEST.value,
                        choices=[stage.value for stage in TestStage],
                        help="Current executable stage")
    args = parser.parse_args()

    configure_logger()
    if args.stage != TestStage.CLEAN.value:
        configure_logger(logs_path=pathlib.Path(args.root_dir) / 'logs' / f'{args.stage}.log')
    log = logging.getLogger('tests_runner.main')

    try:
        tests_runner = TestRunner(artifacts=pathlib.Path(args.artifacts),
                                  root_dir=pathlib.Path(args.root_dir),
                                  current_stage=args.stage)

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
