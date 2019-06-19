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
Module for preparing main manifest
api:
--root-dir, --repo, --branch, --revision, --target-branch, --build-event, --commit-time
steps:
check branch (is_release)
convert branch if release
prepare reposiotories
update manifest
save manifest to builds/manifests/target_branch(branch)/build_event/revision/manifest.yml
"""


import argparse
import logging
import pathlib
import sys
from datetime import datetime

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
from common.logger_conf import configure_logger
from common.helper import Build_event, ErrorCode
from common.mediasdk_directories import MediaSdkDirectories
from common.branch_converter import convert_branch
from common.manifest_manager import Manifest, Repository
from common.git_worker import ProductState


class ManifestRunner:
    """
    Prepare manifest
    """

    def __init__(self, root_dir, repo, branch, revision, target_branch, build_event, commit_time):
        """

        :param root_dir: Directory where repositories will be extracted
        :type root_dir: String

        :param repo: Repository name
        :type repo: Repository name

        :param branch: Branch name
        :type branch: Branch name

        :param revision: Revision of a commit
        :type revision: Revision of a commit

        :param target_branch: Target branch name
        :type target_branch: Target branch name

        :param build_event: Event of a build
        :type build_event: Event of a build

        :param commit_time: Time to slice revisions
        :type commit_time: Time to slice revisions
        """

        self._repo_to_extract = [
            'product-configs',
            'MediaSDK',
            'media-driver'
        ]

        self._root_dir = pathlib.Path(root_dir)
        self._repo = repo
        self._branch = branch
        self._revision = revision
        self._target_branch = target_branch
        self._build_event = build_event
        self._commit_time = datetime.strptime(commit_time, '%Y-%m-%d %H:%M:%S') \
            if commit_time else None

        self._manifest = Manifest(pathlib.Path(__file__).resolve().parents[2] /
                                  'product-configs' / 'manifest.yml')

        self._release_branch = {}
        self._updated_repos = None

        self._log = logging.getLogger(self.__class__.__name__)

    def _check_branch(self):
        """
        Check release branch
        """
        self._log.info('Checking release branch')

        if self._target_branch:
            branch_to_check = self._target_branch
        else:
            branch_to_check = self._branch

        if MediaSdkDirectories.is_release_branch(branch_to_check):
            sdk_br, driver_br = convert_branch(branch_to_check)

            for repo_name in self._repo_to_extract:
                if repo_name == 'media-driver':
                    self._release_branch[repo_name] = driver_br
                else:
                    self._release_branch[repo_name] = sdk_br

    def _extract_repos(self):
        """
        Extract and slice repositories
        """

        self._log.info('Extracting repositories')

        sources_list = {}
        for component in self._manifest.components:
            for repo in component.repositories:
                if repo.name == self._repo:
                    sources_list[repo.name] = {
                        'branch': self._branch,
                        'target_branch': self._target_branch,
                        'commit_id': self._revision,
                        'is_trigger': True,
                        'url': repo.url
                    }
                else:
                    if repo.name not in self._repo_to_extract:
                        continue

                    sources_list[repo.name] = {
                        'branch': self._release_branch.get(repo.name, repo.branch),
                        'target_branch': repo.target_branch,
                        'commit_id': None,
                        'is_trigger': False,
                        'url': repo.url
                    }

        states = ProductState(sources_list, self._root_dir, self._commit_time)
        states.extract_all_repos()
        self._updated_repos = {state.repo_name: state for state in states.repo_states}

    def _update_manifest(self):
        """
        Update manifest from extracted product-configs repo
        """

        self._log.info('Updating manifest')

        for component in self._manifest.components:
            for repo in component.repositories:
                if repo.name == self._repo:
                    component.build_info.set_build_event(self._build_event)
                    component.build_info.set_trigger(repo.name)

                if repo.name in self._updated_repos:
                    upd_repo = Repository(
                        self._updated_repos[repo.name].repo_name,
                        self._updated_repos[repo.name].url,
                        self._updated_repos[repo.name].branch_name,
                        self._updated_repos[repo.name].target_branch,
                        self._updated_repos[repo.name].commit_id
                    )
                    component.add_repository(upd_repo, replace=True)

    def _save_manifest(self):
        """
        Save updated manifest
        """

        self._log.info('Saving manifest')

        path_to_manifest = MediaSdkDirectories.get_commit_dir(
            self._target_branch or self._branch,
            self._build_event,
            self._revision,
            product='manifest'
        ) / 'manifest.yml'

        self._manifest.save_manifest(path_to_manifest)

        self._log.info(f'Manifest was saved to: %s', path_to_manifest)

    def run(self):
        """
        Execute manifest creating process
        """

        self._check_branch()
        self._extract_repos()
        self._update_manifest()
        self._save_manifest()


def main():
    """
    Arguments parser and manifest creator
    """

    argparse.ArgumentParser()
    parser = argparse.ArgumentParser(prog=pathlib.Path(__file__).name,
                                     formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument("--root-dir", metavar="PATH", default='.',
                        help=f"Path where repository will be stored, "
                             f"by default it is current directory")
    parser.add_argument("--repo", metavar="String", required=True,
                        help=f"Repository name")
    parser.add_argument("--branch", metavar="String", default='master',
                        help='Branch name, by default "master" branch')
    parser.add_argument("--revision", metavar="String",
                        default='HEAD', help='SHA of commit')
    parser.add_argument("--target-branch", metavar="String",
                        help='Target branch name')
    parser.add_argument("--build-event", default=Build_event.PRE_COMMIT.value,
                        choices=[build_event.value for build_event in Build_event],
                        help='Event of build')
    parser.add_argument("--commit-time", metavar="String",
                        help='Will switch to the commit before specified time')

    args = parser.parse_args()

    configure_logger()

    log = logging.getLogger('manifest_runner')

    log.info('Manifest preparing started')
    try:
        manifest_runner = ManifestRunner(**vars(args))
        manifest_runner.run()
        log.info('Manifest preparing completed')
    except Exception:
        log.exception('Exception occurred:')
        log.info('Manifest preparing failed')
        exit(ErrorCode.CRITICAL.value)


if __name__ == '__main__':
    main()
