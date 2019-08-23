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
Module updating libva/gmmlib versions in the manifest file
"""

import logging
import argparse
import pathlib
import requests
import json
import git

from datetime import datetime
from common.logger_conf import configure_logger
from common.helper import ErrorCode, remove_directory, cmd_exec
from common.extract_repo import extract_repo
from common.manifest_manager import Manifest, Repository
from common.msdk_secrets import GITHUB_TOKEN


class ComponentUpdater(object):

    def __init__(self, tmp_dir, repo_name, component_name, manifest_file, branch, revision,
                 commit_time, log):
        """
        :param tmp_dir: Temporary directory for repository extracting
        :param repo_name: Repository name
        :param component_name: Name of the component to be updated
        :param manifest_file: Name of the manifest file
        :param branch: Branch name
        :param revision: Commit ID
        :param log: Log file
        """
        self._tmp_dir = tmp_dir
        self._repo_name = repo_name
        self._work_branch = f'auto_update_{component_name}_to_{revision[:7]}'
        self._component_name = component_name
        self._commit_message = f'Auto update {component_name} to {revision[:7]}'
        self._manifest_path = tmp_dir / repo_name / manifest_file
        self._branch = branch
        self._revision = revision
        self._commit_time = datetime.strptime(commit_time, '%Y-%m-%d %H:%M:%S') \
            if commit_time else None
        self._log = log

    def _clean(self):
        """ Clean temporary directory """
        self._log.info(f'Cleaning {self._tmp_dir}')

        try:
            if self._tmp_dir.exists():
                remove_directory(str(self._tmp_dir))
                self._log.info(f"Removed old repository in {self._tmp_dir}")
            self._tmp_dir.mkdir(exist_ok=True)
        except Exception as e:
            self._log.exception(f'Failed to clean {self._tmp_dir}: %s', e)
            return False

        return True

    def _extract_repo(self):
        """ Extract remove repository """
        self._log.info(f'Extracting repository')

        try:
            extract_repo(root_repo_dir=self._tmp_dir, repo_name=self._repo_name, branch='master',
                         commit_id='HEAD')
        except Exception as e:
            self._log.exception('Extract repository failed: %s', e)
            return False

        return True

    def _change_manifest_file(self):
        """ Change revision and branch for the selected component """
        self._log.info(f'Changing manifest file')

        try:
            manifest = Manifest(self._manifest_path)
            component = manifest.get_component(self._component_name)

            tmp_repo = component.get_repository(self._component_name)
            repository = Repository(tmp_repo.name, tmp_repo.url, self._branch,
                                    tmp_repo.target_branch, self._revision, self._commit_time,
                                    tmp_repo.source_type)
            component.add_repository(repository, replace=True)
            manifest.save_manifest(self._manifest_path)

            self._log.info('Manifest file was changed')
        except Exception as e:
            self._log.exception('Changing manifest file failed: %s', e)
            return False

        return True

    def _git_commit(self):
        self._log.info('Pushing changes to remote')

        push_change_commands = [f'git checkout -b {self._work_branch}', 'git add manifest.yml',
                                f'git commit -m "{self._commit_message}"',
                                f'git push origin HEAD:{self._work_branch}']
        try:
            for command in push_change_commands:
                repo_path = self._tmp_dir / self._repo_name
                return_code, output = cmd_exec(command, cwd=repo_path, log=self._log)
                if return_code:
                    self._log.error(output)
                    return False
        except Exception as e:
            self._log.exception('Pushing was failed: %s', e)
            return False

        return True

    def _check_commit(self):
        try:
            self._log.info('Started checking for commit existence')
            g = git.Git(self._tmp_dir / self._repo_name)
            log_info = g.log('--pretty=format:%s')
            if self._commit_message in log_info:
                self._log.warning(f'Pull request was failed because commit with branch '
                                  f'{self._branch} and revision {self._revision} already exists')
                return False
        except:
            self._log.exception("Check was failed")
            return False

        return True

    def _git_pull_request(self):
        self._log.info('Started creating a pull request')

        url = 'https://api.github.com/repos/Intel-Media-SDK/product-configs/pulls'
        data = {
            "title": f'Auto update version of component {self._component_name} to '
            f'{self._revision[:7]}',
            "head": f"{self._work_branch}",
            "base": "master"}
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}

        try:
            r = requests.post(url, data=json.dumps(data), headers=headers)
            self._log.info(f'POST: {r}')
        except Exception as e:
            self._log.exception('Creating pull request failed: %s', e)
            return False

        return True

    def update(self):
        actions = [
            self._clean,
            self._extract_repo,
            self._check_commit,
            self._change_manifest_file,
            self._git_commit,
            self._git_pull_request
        ]

        for action in actions:
            if not action():
                return False

        return True


def main():
    parser = argparse.ArgumentParser(prog="update_version.py",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('-b', '--branch', metavar='String', default='master',
                        help='Branch name that will be replaced in the manifest file')
    parser.add_argument('-r', '--revision', metavar='String', required=True,
                        help='SHA sum of commit that will be replaced in the manifest file')
    parser.add_argument('-t', "--commit-time", metavar="String",
                        help='Will switch to the commit before specified time')
    parser.add_argument('-n', '--component-name', required=True,
                        help='Component name which will be updated information')
    args = parser.parse_args()

    configure_logger()
    log = logging.getLogger('update_version')
    log.info(f'Started version update')

    tmp_dir = (pathlib.Path(__file__).parent / 'tmp').resolve()
    repo_name = 'product-configs'
    manifest_file = 'manifest.yml'

    component_updater = ComponentUpdater(
        tmp_dir=tmp_dir,
        repo_name=repo_name,
        component_name=args.component_name,
        manifest_file=manifest_file,
        branch=args.branch,
        revision=args.revision,
        commit_time=args.commit_time,
        log=log
    )

    if not component_updater.update():
        log.error('Update failed')
        exit(ErrorCode.CRITICAL.value)

    log.info(f'Version updated')


if __name__ == '__main__':
    main()
