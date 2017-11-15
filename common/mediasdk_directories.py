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
Module contains static directories and links
which uses in build runner
"""
import os
import pathlib
import platform


class MediaSdkDirectories(object):
    """
    Container for static links
    """
    _tests_root_path = r'/media/tests'
    _builds_root_path = r'/media/builds'

    _repositories = {
        # TODO split this part
        # linux_open_source
        'MediaSDK': 'https://github.com/Intel-Media-SDK/MediaSDK',
        # test_repositories
        'flow_test': 'git@github.com:Intel-Media-SDK/flow_test.git',
        'MediaSDKTEST': 'https://github.com/adydychk/MediaSDK'
    }

    @classmethod
    def get_root_test_results_dir(cls):
        """
        Get root path to test results

        :return: root path to test results
        :rtype: String
        """

        return cls._tests_root_path

    @classmethod
    def get_root_builds_dir(cls):
        """
        Get root path to artifacts of build

        :return: root path to artifacts of build
        :rtype: String
        """

        return cls._builds_root_path

    @classmethod
    def get_build_dir(cls, branch, build_event, commit_id, product_type, build_type):
        """
        Get path to artifacts of build 
        
        :param branch: Branch of repo
        :type branch: String

        :param build_event: Event of build (pre_commit|commit|nightly|weekly)
        :type build_event: String

        :param commit_id: SHA sum of commit
        :type commit_id: String

        :param product_type: Type of product (linux|windows|embedded|pre_si)
        :type product_type: String

        :param build_type: Type of build (release|debug)
        :type build_type: String

        :return: Path to artifacts of build
        :rtype: String
        """

        # only for Gerrit
        if branch.startswith('refs/changes/'):
            branch = branch.replace('refs/changes/', '')

        return pathlib.Path(cls._builds_root_path) / branch / build_event / commit_id / \
               f'{product_type}_{build_type}'

    @classmethod
    def get_repo_url_by_name(cls, name='MediaSDK'):
        """
        Get url of certain repository

        :param name: Repository name
        :type name: String

        :return: Url of repository if found
        :rtype: String|None
        """

        return cls._repositories.get(name, None)
