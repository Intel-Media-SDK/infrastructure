# Copyright (c) 2017 Intel Corporation
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

import json
import logging
from datetime import datetime

import git
from tenacity import retry, stop_after_attempt, wait_exponential

from common.helper import remove_directory


class GitRepo(object):
    """
        Class for work with repositories
    """

    def __init__(self, root_repo_dir, repo_name, branch, url, commit_id=None):
        """
        :param root_repo_dir: Directory where repositories will clone
        :param repo_name: Name of repository
        :param branch: Branch of repository
        :param commit_id: Commit ID
        """

        self.name = repo_name
        self.branch = branch
        self.url = url
        self.commit_id = commit_id
        self.local_repo_dir = root_repo_dir / repo_name
        self.repo = None

        self.log = logging.getLogger()

    def prepare_repo(self):
        """
        Preparing repository for build
        Include cloning and updating repo to remote state

        :return: None
        """
        self.log.info('-' * 50)
        self.log.info("Getting repo " + self.name)

        self.clone()
        self.repo = git.Repo(str(self.local_repo_dir))
        self.hard_reset()
        self.clean()
        self.checkout("master", silent=True)
        self.fetch()
        self.hard_reset('FETCH_HEAD')

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
            self.log.info("Clone repo " + self.name)
            git.Git().clone(self.url, str(self.local_repo_dir))

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def fetch(self):
        """
        Fetch repo

        :return: None
        """

        self.log.info("Fetch repo %s to %s", self.name, self.branch)
        self.repo.remotes.origin.fetch(self.branch)

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def hard_reset(self, reset_to=None):
        """
        Hard reset repo

        :param reset_to: Commit ID or branch. If None - hard reset to HEAD
        :return: None
        """

        self.log.info("Hard reset repo " + self.name)
        if reset_to:
            self.repo.git.reset('--hard', reset_to)
        else:
            self.repo.git.reset('--hard')

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def checkout(self, branch=None, silent=False):
        """
        Checkout to certain state

        :param branch: Branch of repo. If None - checkout to commit ID from class variable commit_id

        :param silent: Flag for getting time of commit
               (set to True only if commit_id does not exist)
        :type silent: Boolean

        :return: None
        """

        checkout_to = branch if branch else self.commit_id
        self.log.info("Checkout repo %s to %s", self.name, checkout_to)
        self.repo.git.checkout(checkout_to, force=True)

        if not silent:
            # error raises after checkout to master if we try
            # to get time of triggered commit_id before fetching repo
            # (commit does not exist in local repository yet)
            committed_date = self.repo.commit(self.commit_id).committed_date
            self.log.info("Committed date: %s", datetime.fromtimestamp(committed_date))

        # if self.commit_id == 'HEAD' set SHA to variable self.commit_id
        self.commit_id = str(self.repo.commit())

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def clean(self):
        """
        Clean repo

        :return: None
        """

        self.log.info("Clean repo " + self.name)
        self.repo.git.clean('-xdf')

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=60))
    def pull(self):
        """
        Pull repo
        :return: None
        """

        self.log.info("Pull repo " + self.name)
        self.repo.git.pull()

    def revert_commit_by_time(self, commit_time):
        """
        Sets commit by time.
        If commit date <= certain time,
        commit sets to class variable commit_id.

        :param commit_time: datetime
        :return: None
        """

        self.commit_id = str(next(self.repo.iter_commits(rev='master', until=commit_time, max_count=1)))

    def get_time(self, commit_id=None):
        """
        Get datetime of commit

        :param commit_id: Commit ID
        :return: datetime
        """

        commit = commit_id if commit_id else self.commit_id
        return self.repo.commit(commit).committed_date


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
            branch = data.get('branch', 'master')
            commit_id = data.get('commit_id')

            self.repo_states.append(
                GitRepo(root_repo_dir, repo_name, branch, data['url'], commit_id))

    def extract_all_repos(self):
        """
        Get repositories and checkout them to the right state

        :return: None
        """

        git_commit_date = None
        for repo in self.repo_states:
            if repo.commit_id:
                repo.prepare_repo()
                git_commit_date = repo.get_time()
                repo.checkout()

        commit_timestamp = self.commit_time.timestamp() \
            if self.commit_time \
            else git_commit_date

        for repo in self.repo_states:
            if not repo.commit_id:
                repo.prepare_repo()
                repo.revert_commit_by_time(commit_timestamp)
                repo.checkout()

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
                states[state.name] = {
                    'branch': state.branch,
                    'commit_id': state.commit_id,
                    'url': state.url
                }

                if trigger == state.name:
                    states[state.name]['trigger'] = True

            sources_state.write(json.dumps(states, indent=4))
