# Copyright (c) 2017-2019 Intel Corporation
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
Module for working with Git
"""
import collections
import json
import logging
import concurrent.futures
import multiprocessing
from datetime import datetime

import git
from tenacity import retry, stop_after_attempt, wait_exponential, \
    retry_if_exception_type, retry_if_result

from common.helper import remove_directory
from common.mediasdk_directories import MediaSdkDirectories, THIRD_PARTY


def check_exception(value):
    if isinstance(value, git.exc.GitCommandError) and (value.status == 128 or value.status == 1):
        # 1: branch does not exist
        # 128: revision does not exist
        raise value


class BranchDoesNotExistException(Exception):
    """
    Exception for branch does not exist
    """

    pass


class GitRepo(object):
    """
        Class for work with repositories
    """

    def __init__(self, root_repo_dir, repo_name, branch, url, commit_id=None, is_trigger=False, target_branch=None):
        """
        :param root_repo_dir: Directory where repositories will clone
        :param repo_name: Name of repository
        :param branch: Branch of repository
        :param commit_id: Commit ID
        """

        self.repo_name = repo_name
        self.branch_name = branch
        self.url = url
        self.commit_id = commit_id
        self.local_repo_dir = root_repo_dir / repo_name
        self.repo = None
        self.is_trigger = is_trigger
        self.target_branch = target_branch

        self.log = logging.getLogger(self.__class__.__name__)

    def prepare_repo(self):
        """
        Preparing repository for build
        Include cloning and updating repo to remote state

        :return: None
        """
        self.log.info('-' * 50)
        self.log.info("Getting repo " + self.repo_name)

        self.clone()
        self.repo = git.Repo(str(self.local_repo_dir))
        self.hard_reset()
        self.clean()
        self.checkout(branch_name="master", silent=True)
        self.hard_reset('origin/master')
        self.pull()

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def clone(self):
        """
        Clone repo

        :return: None
        """

        # checking correctness of git repository
        # if dir is not repository, it will be removed
        if self.local_repo_dir.exists():
            try:
                git.Repo(str(self.local_repo_dir))
            except git.InvalidGitRepositoryError:
                self.log.info('Remove broken repo %s', self.local_repo_dir)
                remove_directory(self.local_repo_dir)

        if not self.local_repo_dir.exists():
            self.log.info("Clone repo " + self.repo_name)
            git.Git().clone(self.url, str(self.local_repo_dir))

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def fetch(self, branch_name=None):
        """
        Fetch repo

        :return: None
        """

        refname = branch_name or self.branch_name
        self.log.info("Fetch repo %s to %s", self.repo_name, refname)
        self.repo.remotes.origin.fetch(refname)
        self.hard_reset('FETCH_HEAD')

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def hard_reset(self, reset_to="HEAD"):
        """
        Hard reset repo

        :param reset_to: Commit ID or branch. If None - hard reset to HEAD
        :return: None
        """

        self.log.info(f"Hard reset repo {self.repo_name} to {reset_to}")
        if reset_to:
            self.repo.git.reset('--hard', reset_to)
        else:
            self.repo.git.reset('--hard')

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60),
           retry=(retry_if_exception_type() | retry_if_result(check_exception)))
    def checkout(self, branch_name=None, silent=False):
        """
        Checkout to certain state

        :param branch_name: Branch of repo.
               If None - checkout to commit ID from class variable commit_id

        :param silent: Flag for getting time of commit
               (set to True only if commit_id does not exist)
        :type silent: Boolean

        :return: None
        """

        checkout_dest = branch_name or self.commit_id
        self.log.info("Checkout repo %s to %s", self.repo_name, checkout_dest)
        try:
            self.repo.git.checkout(checkout_dest, force=True)
        except git.exc.GitCommandError as err:
            self.log.exception("Remote branch %s does not exist", checkout_dest)
            return err

        if str(self.commit_id).lower() == 'head':
            self.commit_id = str(self.repo.head.commit)

        if not silent:
            # error raises after checkout to master if we try
            # to get time of triggered commit_id before fetching repo
            # (commit does not exist in local repository yet)
            committed_date = self.repo.commit(checkout_dest).committed_date
            self.log.info("Committed date: %s", datetime.fromtimestamp(committed_date))

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def clean(self):
        """
        Clean repo

        :return: None
        """

        self.log.info("Clean repo " + self.repo_name)
        self.repo.git.clean('-xdf')

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def pull(self):
        """
        Pull repo
        :return: None
        """

        self.log.info("Pull repo " + self.repo_name)
        self.repo.git.pull()

    def change_repo_state(self, branch_name=None, commit_time=None):
        """
        Change the repo state

        :param branch_name: name of branch to checkout
        :param commit_time: time of commit
        :return: None
        """

        self.branch_name = branch_name or self.branch_name

        if self.branch_name and self.branch_name != 'master':
            # for Gerrit patches and Github pull requests
            if 'refs/changes' in self.branch_name or 'refs/pull' in self.branch_name:
                self.fetch(self.branch_name)
            else:
                self.checkout(branch_name=self.branch_name)
                self.hard_reset(f'origin/{self.branch_name}')
                self.pull()

        if commit_time:
            self.revert_commit_by_time(commit_time)
        # Checkout to commit id
        self.checkout()

    def revert_commit_by_time(self, commit_time):
        """
        Sets commit by time.
        If commit date <= certain time,
        commit sets to class variable commit_id.

        :param commit_time: timestamp
        :return: None
        """

        self.commit_id = str(next(self.repo.iter_commits(
            until=commit_time, max_count=1)))
        self.log.info(f"Revert commit by time to: {datetime.fromtimestamp(commit_time)}")

    def get_time(self, commit_id=None):
        """
        Get datetime of commit

        :param commit_id: Commit ID
        :return: datetime
        """

        commit = commit_id if commit_id else self.commit_id
        return self.repo.commit(commit).committed_date

    def is_branch_exist(self, branch_name):
        """
        Check if branch exists in repo

        :param branch_name: branch name
        :return: True if branch exists else false
        """

        if self.repo.git.branch('--list', f'*/{branch_name}', '--all'):
            return True
        return False


class ProductState(object):
    """
        Class for work with list of repositories
    """

    repo_states = []

    def __init__(self, sources_list, root_repo_dir, commit_time):
        """
        :param sources_list: dictionary of repositories
        :param root_repo_dir: path to repositories directory
        :param commit_time: Time for getting slice of commits of repositories
        """

        self.commit_time = commit_time

        for repo_name, data in sources_list.items():
            branch = data.get('branch') or 'master'
            target_branch = data.get('target_branch') or None
            commit_id = data.get('commit_id') or 'HEAD'
            is_trigger = data.get('trigger') or False

            self.repo_states.append(
                GitRepo(root_repo_dir, repo_name, branch, data['url'], commit_id, is_trigger, target_branch))

    def extract_all_repos(self):
        """
        Get repositories and checkout them to the right state

        :return: None
        """

        git_commit_date = None
        for repo in self.repo_states:
            if repo.commit_id != 'HEAD':
                repo.prepare_repo()
                if MediaSdkDirectories.is_release_branch(repo.branch_name):
                    if not repo.is_branch_exist(repo.branch_name):
                        raise BranchDoesNotExistException(
                            f'Release branch {repo.branch_name} does not exist in the repo {repo.repo_name}')
                    repo.change_repo_state(branch_name=repo.branch_name)
                else:
                    repo.change_repo_state()
                if repo.is_trigger:
                    git_commit_date = repo.get_time()

        commit_timestamp = self.commit_time.timestamp() \
            if self.commit_time \
            else git_commit_date

        for repo in self.repo_states:
            if repo.commit_id == 'HEAD':
                repo.prepare_repo()
                if MediaSdkDirectories.is_release_branch(repo.branch_name):
                    if not repo.is_branch_exist(repo.branch_name):
                        raise BranchDoesNotExistException(
                            f'Release branch {repo.branch_name} does not exist in the repo {repo.repo_name}')
                    repo.change_repo_state(branch_name=repo.branch_name, commit_time=commit_timestamp)
                # if parameters '--commit-time', '--changed-repo' and '--repo-states' didn't set
                # then variable 'commit_timestamp' is 'None' and 'HEAD' revisions be used
                elif repo.repo_name not in THIRD_PARTY:
                    repo.change_repo_state(commit_time=commit_timestamp)

    def save_repo_states(self, sources_file, trigger):
        """
        Write repositories states to json file

        :param sources_file: path to json file
        :type sources_file: pathlib.Path

        :param trigger: Triggered repository
        :type trigger: String
        """

        with sources_file.open('a') as sources_state:
            states = {}
            for state in self.repo_states:
                states[state.repo_name] = {
                    'branch': state.branch_name,
                    'commit_id': state.commit_id,
                    'url': state.url,
                    'commit_time': str(state.repo.commit().committed_datetime.astimezone()),
                    'trigger': True if trigger == state.repo_name else False
                }
                if state.target_branch:
                    states[state.repo_name]['target_branch'] = state.target_branch

            sources_state.write(json.dumps(states, indent=4, sort_keys=True))

    @staticmethod
    def get_head_revision(repo_dir):
        """
        Get head revision of repository

        :param repo_dir: path to repository
        :type repo_dir: pathlib.Path
        """

        return str(git.Repo(str(repo_dir)).head.commit)

    @staticmethod
    def get_last_committer_of_file(repo, file_path):
        """
            Get e-mail of last committer in chosen file

            :param repo: path to a repository
            :type repo: git.Git
            :param file_path: path to a file from repo
            :return file_path: pathlib.Path

            :return file path, email of last committer
            :rtype Tuple | None
        """

        if not file_path.is_dir():
            rel_file_path = str(file_path.relative_to(repo.working_dir))
            committer_email = repo.log('--format=%ae', '-1', rel_file_path)
            return rel_file_path, committer_email
        return None

    @staticmethod
    def get_files_owners(repos_dir, repo_states):
        """
            Get last committer e-mail of each file
            of repositories from repo_states.json file

            :param repos_dir: Root path to repositories
            :type repos_dir: pathlib.Path
            :param repo_states: List of repositories' names
            :type repo_states: List

            :return: ex: {<last_committer_email>: [<file_path>}, [...]}
            :rtype: Dict
        """

        repo_files = collections.defaultdict(list)
        max_workers = multiprocessing.cpu_count() * 2
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            for repo_name in repo_states:
                repo_path = repos_dir / repo_name
                repo = git.Git(str(repo_path))
                future_appends = {
                    executor.submit(ProductState.get_last_committer_of_file, repo, file_path):
                    file_path for file_path in repo_path.rglob('*')
                    if '.git' not in str(file_path) and file_path.is_file()
                }

                for future in concurrent.futures.as_completed(future_appends):
                    result = future.result()
                    if result:
                        rel_file_path, author_email = result
                        file_path = repo_path / rel_file_path
                        repo_files[author_email].append(str(file_path))

        return repo_files

    @staticmethod
    def get_last_committer_of_file_line(repo, file_path, line):
        """
            Get e-mail of last committer in chosen file by line

            :param repo: path to a repository
            :type repo: pathlib.Path

            :param file_path: path to a file from repo
            :return file_path: pathlib.Path

            :param line: Line number
            :return line: String

            :return email of last committer
            :rtype None
        """

        if file_path.exists() and not file_path.is_dir():
            repo = git.Repo(str(repo))
            rel_file_path = str(file_path.relative_to(repo.working_dir))
            try:
                blame = repo.blame("HEAD", rel_file_path, L=f'{line},+1', e=True)
                return blame[0][0].author.email
            except Exception:
                pass

        return None

    @staticmethod
    def get_commits(repo_path, commit_from, commit_to=None):
        """
            Get commit or slice of commits

            :param repo_path: Path to a repository
            :type repo_path: String | pathlib.Path

            :param commit_from: Revision of commit
            :type commit_from: String

            :param commit_to: Revision of commit to
            :type commit_to: String

            :return: git.Commit object or List of git.Commit objects
            :rtype: git.Commit | List
        """

        r = git.Repo(str(repo_path))

        if commit_to:
            commits = list(r.iter_commits(f'{commit_from}..{commit_to}'))
            commits.append(r.commit(commit_from))
            return commits

        return r.commit(commit_from)

    @staticmethod
    def get_commit_number(repo_path):
        """
            Get count of commits

            :param repo_path: Path to a repository
            :type repo_path: pathlib.Path | String

            :return: Count of commits
            :rtype: String
        """

        if not repo_path.exists():
            return '0'

        git_repo = git.Git(str(repo_path))
        return str(git_repo.rev_list('--count', 'HEAD'))
