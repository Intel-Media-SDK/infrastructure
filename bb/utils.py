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
"""

import ssl
import json
import urllib.request

from common import MediaSdkDirectories


def is_comitter_the_org_member(pull_request, token):
    """
    Checks if commit owner is a member the organization
    """

    commit_owner = pull_request['user']['login']
    organization = pull_request['base']['repo']['owner']['login']
    github_member_url = f"https://api.github.com/orgs/{organization}/members/" \
                        f"{commit_owner}?access_token={token}"

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


def get_pull_request_info(organization, repository, pull_id=None, token=None, proxy=None):
    """
    Gets list of open pull requests. Get one pull request json if pull_id number specified
    Token must be specified for private repositories

    :return None or pull request dict or list of pull request dicts
    """

    pull_request_url = f'https://api.github.com/repos/{organization}/{repository}/pulls'
    if pull_id:
        pull_request_url += f'/{pull_id}'

    request = {'url': pull_request_url, 'method': 'GET',
               'headers': {'Content-type': 'application/json; charset=UTF-8'}}
    if token:
        request['headers']['access_token'] = token
    req = urllib.request.Request(**request)
    if proxy:
        req.set_proxy(proxy, 'http')

    try:
        response = urllib.request.urlopen(req, context=ssl._create_unverified_context())
    except Exception as error:
        print(f'Can not get pull info by {pull_request_url}')
        print(f'Error: {error}')
        return None

    pull_request = json.loads(response.read().decode('utf8'))
    return pull_request


def is_change_needed(token=None):
    """
    This is a change filter for Buildbot masters
    Implemented as closure for specifying Github access token from buildbot configuration

    :return None if change is not needed or dict with properties otherwise
    """

    def checker(repository, branch, revision, files, category):
        # No filter for common branches
        if not branch.startswith('refs/pull/'):
            return {}

        # Checks membership of commit author in organization for pull requests
        _, organization, repository = repository[:-4].rsplit('/', maxsplit=2)
        _, pull_id, _ = branch.rsplit('/', maxsplit=2)
        print(f'Processing {pull_id} pull request from {repository}')
        pull_request = get_pull_request_info(organization, repository, pull_id, token)
        if pull_request:
            is_request_needed = is_comitter_the_org_member(pull_request, token)
            if is_request_needed:
                return {'target_branch': pull_request['base']['ref']}

        return None

    return checker


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
