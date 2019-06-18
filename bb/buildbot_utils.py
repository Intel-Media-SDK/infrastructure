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
Module contains buildbot specific functions
"""

from enum import Enum
from collections import defaultdict

from buildbot.plugins import util
from twisted.internet import defer

from bb.utils import get_repository_name_by_url


class BuildStatus(Enum):
    """
     Wrapper for buildbot statuses
     buildbot status have value [0, .. ,6] (see buildbot.process.result) if this build finished
     or None otherwise
    """
    PASSED = util.SUCCESS
    FAILED = util.FAILURE
    HAVE_WARNINGS = util.WARNINGS
    SKIPPED = util.SKIPPED
    RETRIED = util.RETRY
    CANCELLED = util.CANCELLED
    HAVE_EXEPTION = util.EXCEPTION
    RUNNING = None
    # Custom status for builds, that is not created yet
    # In this case buildbot return empty list instead dict with 'result' key
    NOT_STARTED = 99


@defer.inlineCallbacks
def get_triggered_builds(build_id, master):
    """
    Recursively gets all triggered builds to identify current status of pipeline

    :param build_id: int
    :param master: BuildMaster object from buildbot.master
    :return: defaultdict
        Example: {'builder_name': {'buildrequest_id': str,
                                   'result': BuildStatus,
                                   'build_id': None or int,

                                   # These parameters will be return if build ongoing
                                   'step_name': str or None,
                                   'step_started_at': Datetime or None},
                  ....}
    """
    triggered_builds = defaultdict(dict)
    parent_build_trigger_step = yield master.db.steps.getStep(
        buildid=build_id,
        name='trigger')
    if parent_build_trigger_step is None:
        return triggered_builds

    requests = parent_build_trigger_step.get('urls')
    for request in requests:
        builder_name, request_id = request['name'].split(' #')
        triggered_builds[builder_name]['buildrequest_id'] = request_id
        builds_for_request = yield master.db.builds.getBuilds(buildrequestid=request_id)
        if builds_for_request:
            # It is sorted to get the latest started build, because Buildbot's list of builds is not ordered
            last_build = max(builds_for_request, key=lambda r: r['started_at'])

            last_build_status = BuildStatus(last_build['results'])
            triggered_builds[builder_name]['result'] = last_build_status
            triggered_builds[builder_name]['build_id'] = last_build['id']

            # Add current step information if build ongoing
            if last_build_status == BuildStatus.RUNNING:
                last_build_steps = yield master.db.steps.getSteps(buildid=last_build['id'])
                if last_build_steps:
                    current_step_of_last_build = last_build_steps[-1]
                    triggered_builds[builder_name]['step_name'] = current_step_of_last_build['name']
                    triggered_builds[builder_name]['step_started_at'] = current_step_of_last_build['started_at']
                else:
                    triggered_builds[builder_name]['step_name'] = None
                    triggered_builds[builder_name]['step_started_at'] = None

            new_builds = yield get_triggered_builds(last_build['id'], master)
            triggered_builds.update(new_builds)

        else:
            triggered_builds[builder_name]['result'] = BuildStatus.NOT_STARTED
            triggered_builds[builder_name]['build_id'] = None

    defer.returnValue(triggered_builds)


@util.renderer
def get_changed_repo(props):
    """
    Create string that describes commit information.

    :param props: Properties object from buildbot.process.properties
    :return: str
        Example: MediaSDK:refs/pull/1303/head:ef64b58af5988ed7762661e9591d10f593b55bcb
    """
    repo_url = props.getProperty('repository')
    branch = props.getProperty('branch')
    revision = props.getProperty('revision')
    return f"{get_repository_name_by_url(repo_url)}:{branch}:{revision}"
