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
Module contains shared functions for buildbot configurations
This module doesn't require buildbot installed
"""

import ssl
import json
import pathlib
import urllib.request

from enum import Enum
from twisted.internet import defer

from common.mediasdk_directories import MediaSdkDirectories, OsType


class CIService(Enum):
    MEDIASDK = "mediasdk"
    DRIVER = "driver"

# This is stop phrase for buildbot to skip all build stages
SKIP_BUILDING_DEPENDENCY_PHRASE = 'REBUILD IS NOT NEEDED'
SKIP_BUILDING_DEPENDENCY_PROPERTY = 'skip_building_dependency'

# This variable is used as step\builder name for displaying links to artifacts
# Also is used in other buildbot services
PACKAGES = 'packages'


class Mode(Enum):
    PRODUCTION_MODE = "production_mode"
    TEST_MODE = "test_mode"


def get_path_on_os(os):
    """
    Convert path for specified os
    Implemented as closure to improve usability
    """

    def get_path(path):
        if os == OsType.windows:
            return str(pathlib.PureWindowsPath(path))
        elif os == OsType.linux:
            return str(pathlib.PurePosixPath(path))
        raise OSError(f'Unknown os type {os}')

    return get_path


@defer.inlineCallbacks
def get_root_build_id(build_id, master):
    """
    Recursively gets ids of parent builds to find root builder (trigger) id

    :param build_id: int
    :param master: BuildMaster object from buildbot.master
    :return: int
    """
    build = yield master.data.get(('builds', build_id))
    buildrequest_id = build['buildrequestid']
    buildrequest = yield master.data.get(('buildrequests', buildrequest_id))
    buildset_id = buildrequest['buildsetid']
    buildset = yield master.data.get(('buildsets', buildset_id))
    parent_build_id = buildset['parent_buildid']
    if parent_build_id is not None:
        build_id = yield get_root_build_id(parent_build_id, master)
    defer.returnValue(build_id)


def is_comitter_the_org_member(pull_request, token=None):
    """
    Checks if commit owner is a member the organization
    """

    commit_owner = pull_request['user']['login']
    organization = pull_request['base']['repo']['owner']['login']
    github_member_url = f"https://api.github.com/orgs/{organization}/members/{commit_owner}"
    if token:
        github_member_url += f"?access_token={token}"

    try:
        response = urllib.request.urlopen(github_member_url,
                                          context=ssl._create_unverified_context())
    except Exception as error:
        print(f"Check organization member: Exception occurred "
              f"while checking user {commit_owner} in {organization} organization: {error}")
        return False

    if response.code == 204:
        print(f'Check organization member: user {commit_owner} was found in {organization}')
        return True
    print(f"Check organization member: user {commit_owner} was "
          f"not found in {organization} organization. Code: {response.code}")
    return False


def get_data(url, proxy=None, additional_headers=None):
    """
    Wrapper for GET request
    """
    request = {'url': url, 'method': 'GET',
               'headers': {'Content-type': 'application/json; charset=UTF-8'}}
    if additional_headers:
        request['headers'].update(additional_headers)
    req = urllib.request.Request(**request)
    if proxy:
        req.set_proxy(proxy, 'http')
    try:
        response = urllib.request.urlopen(req, context=ssl._create_unverified_context())
        data = json.loads(response.read().decode('utf8'))
    except Exception as error:
        print(f'Can not get info from {url}')
        print(f'Request json: {request}')
        print(f'Http proxy: {proxy}')
        print(f'ERROR: {error}')
        return None
    return data


def get_pull_request_info(organization, repository, pull_id=None, token=None, proxy=None):
    """
    Gets list of open pull requests. Get one pull request json if pull_id number specified
    Token must be specified for private repositories

    :return None or pull request dict or list of pull request dicts
    """

    pull_request_url = f'https://api.github.com/repos/{organization}/{repository}/pulls'
    if pull_id:
        pull_request_url += f'/{pull_id}'

    return get_data(pull_request_url, proxy=proxy,
                    additional_headers={'Authorization': f'token {token}'} if token else None)


class ChangeChecker:
    """
    This is a change filter for Buildbot masters
    """

    def __init__(self, token=None):
        self.token = token

    def set_pull_request_default_properties(self, pull_request, files):
        """
        Set these pull request properties as default properties.
        """
        self.default_properties = {'target_branch': pull_request['base']['ref'],
                                   'event_type': 'pre_commit'}

    def set_commit_default_properties(self, repository, branch, revision, files, category):
        """
        Set these commit properties as default properties.
        """
        self.default_properties = {'event_type': 'commit'}

    def get_pull_request(self, repository, branch):
        """
        Get pull request json by refs/pull/* branch
        """
        _, organization, repository = repository[:-4].rsplit('/', maxsplit=2)
        _, pull_id, _ = branch.rsplit('/', maxsplit=2)
        print(f'Processing {pull_id} pull request from {repository}')
        pull_request = get_pull_request_info(organization, repository, pull_id, self.token)
        return pull_request

    def pull_request_filter(self, pull_request, files):
        """
        Special entry point for filtration pull requests.
        By default checks membership of committer in organization.
        :return None if change is not needed or dict with properties otherwise
        """

        is_request_needed = is_comitter_the_org_member(pull_request, self.token)
        if is_request_needed:
            return self.default_properties
        return None

    def commit_filter(self, repository, branch, revision, files, category):
        """
        Special entry point for filtration commits. No filtering by default.
        :return None if change is not needed or dict with properties otherwise
        """
        return self.default_properties

    def __call__(self, repository, branch, revision, files, category):
        """
        Redefine __call__ to implement closure api
        First step is getting default properties for change. This needed to avoid specifying default
        properties in filters - just return self.default_properties

        :return None if change is not needed or dict with properties otherwise
        """
        if branch.startswith('refs/pull/'):
            pull_request = self.get_pull_request(repository, branch)
            self.set_pull_request_default_properties(pull_request, files)
            if pull_request:
                return self.pull_request_filter(pull_request, files)
            return None
        self.set_commit_default_properties(repository, branch, revision, files, category)
        return self.commit_filter(repository, branch, revision, files, category)


def get_open_pull_request_branches(organization, repository, token):
    """
    Create list of Github branches for open pull request
    Used to extend branches list for fetching in GitPoller
    Implemented as closure for specifying information about repository from buildbot configuration
    """

    def checker():
        all_pull_requests = get_pull_request_info(organization, repository, token=token)
        branches_for_pull_requests = [f'refs/pull/{pr["number"]}/head' for pr in all_pull_requests]
        return branches_for_pull_requests

    return checker


def is_release_branch(raw_branch):
    # TODO: need to unify with MediaSdkDirectories.is_release_branch method
    """
    Checks if branch is release branch
    Used as branch filter for pollers
    """
    # Ignore pull request branches like 'refs/pull/*'
    if raw_branch.startswith('refs/heads/'):
        branch = raw_branch[11:]
        if MediaSdkDirectories.is_release_branch(branch) or branch == 'master':
            return True

    return False


def get_repository_name_by_url(repo_url):
    """
    Gets repository name from GitHub url, by example
    https://github.com/Intel-Media-SDK/product-configs.git -> product-configs
    """

    return repo_url.split('/')[-1][:-4]


class GithubCommitFilter:
    """
    Class for encapsulating behavior of builder triggers
    """
    def __init__(self, repositories, branches):
        self.repositories = repositories
        self.branches = branches

    def check_commit(self, step):
        """
        Function for checking commit information before running build

        :param step: BuildStep instance
        :return: True or False
        """
        repository = get_repository_name_by_url(step.build.properties.getProperty('repository'))
        branch = step.build.properties.getProperty('branch')
        target_branch = step.build.properties.getProperty('target_branch')

        try:
            if self.branches(branch, target_branch) and repository in self.repositories:
                return True
        except Exception as exc:
            print(f'Exception occurred while filtering commits: {exc}')
        return False
