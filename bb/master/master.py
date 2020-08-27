# Copyright (c) 2020 Intel Corporation
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

import sys
import pathlib

from buildbot.www.hooks.github import GitHubEventHandler, _HEADER_EVENT, bytes2unicode, log, logging
from twisted.internet import defer
from buildbot.plugins import schedulers, util, worker, reporters

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
import bb.master.config as config

import bb.utils

c = BuildmasterConfig = {}

# Add workers
c["workers"] = []
ALL_WORKERS_NAMES = []
for worker_ in config.WORKERS.values():
    for w_name, prop in worker_.items():
        ALL_WORKERS_NAMES.append(w_name)
        c["workers"].append(worker.Worker(w_name, config.WORKER_PASS,
                                          properties=prop,
                                          # To disable parallel builds on one worker
                                          max_builds=prop.get('max_builds') or 1))

# Basic config
c["protocols"] = {"pb": {"port": config.WORKER_PORT}}
c["buildbotNetUsageData"] = config.BUILDBOT_NET_USAGE_DATA
c["title"] = config.BUILDBOT_TITLE
c["titleURL"] = config.REPO_URL
c["buildbotURL"] = config.BUILDBOT_URL


def get_workers(worker_pool):
    if worker_pool is None:
        return ALL_WORKERS_NAMES
    return list(config.WORKERS[worker_pool].keys())


# Create schedulers and builders for builds
c["builders"] = []
c["schedulers"] = [
    schedulers.SingleBranchScheduler(name=config.TRIGGER,
                                     change_filter=util.ChangeFilter(),
                                     treeStableTimer=config.BUILDBOT_TREE_STABLE_TIMER,
                                     builderNames=[config.TRIGGER])]

for builder_name, properties in config.FLOW.get_prepared_builders().items():
    if properties.get('add_triggerable_sheduler', True):
        c["schedulers"].append(schedulers.Triggerable(name=builder_name,
                                                      builderNames=[builder_name]))
    c["builders"].append(util.BuilderConfig(name=builder_name,
                                            workernames=get_workers(properties.get("worker")),
                                            factory=properties['factory']))


class MockedGitHubEventHandler(GitHubEventHandler):
    @defer.inlineCallbacks
    def process(self, request):
        payload = self._get_payload(request)

        event_type = request.getHeader(_HEADER_EVENT)
        event_type = bytes2unicode(event_type)
        log.msg("X-GitHub-Event: {}".format(
            event_type), logLevel=logging.DEBUG)

        handler = getattr(self, 'handle_{}'.format(event_type), None)

        if handler is None:
            raise ValueError('Unknown event: {}'.format(event_type))

        result = yield defer.maybeDeferred(lambda: handler(payload, event_type))
        for i in result:
            print(i)
        defer.returnValue(([], 'git'))


class GitHubStatusPushFilter(reporters.GitHubStatusPush):
    """
    This class extend filtering options for reporters.GitHubStatusPush
    """
    def filterBuilds(self, build):
        # All builds have basic 'repository' property
        repository = bb.utils.get_repository_name_by_url(build['properties']['repository'][0])
        # Status for AUTO_UPDATED_REPOSITORIES will not sent to not affect review requests
        # in these repositories
        # TODO: remove workaround for libva notifications
        if repository not in config.AUTO_UPDATED_REPOSITORIES and repository != config.LIBVA_REPO:
            if self.builders is not None:
                return build['builder']['name'] in self.builders
            return True
        # Enabled libva builder notifications for libva repository only
        if repository == config.LIBVA_REPO and build['builder']['name'] == config.LIBVA_REPO:
            return True
        return False


# Push status of build to the Github
c["services"] = [
    GitHubStatusPushFilter(token=config.GITHUB_TOKEN,
                           context=util.Interpolate("buildbot/%(prop:buildername)s"),
                           startDescription="Started",
                           endDescription="Done",
                           verbose=True)]


# Web Interface
c["www"] = dict(port=int(config.PORT),
                plugins={"console_view": True,
                         "grid_view": True},
                change_hook_dialects={'github': {'class': MockedGitHubEventHandler}})

# Database
c["db"] = {"db_url": config.DATABASE_URL}

# It disables automatic merging of requests (to build EACH commit)
c["collapseRequests"] = False
