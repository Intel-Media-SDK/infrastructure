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

from buildbot.changes.gitpoller import GitPoller
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

# Get changes
c["change_source"] = []


class MediasdkChangeChecker(bb.utils.ChangeChecker):
    def pull_request_filter(self, pull_request, files):
        is_request_needed = bb.utils.is_limited_number_of_commits(pull_request, self.token)
        if is_request_needed:
            return self.default_properties
        return None


CI_REPOSITORIES = [
    {'name': config.MEDIASDK_REPO,
     'organization': config.MEDIASDK_ORGANIZATION},
    {'name': config.DRIVER_REPO,
     'organization': config.INTEL_ORGANIZATION},
    {'name': config.LIBVA_REPO,
     'organization': config.INTEL_ORGANIZATION},
    {'name': config.PRODUCT_CONFIGS_REPO,
     'organization': config.MEDIASDK_ORGANIZATION},
    {'name': config.INFRASTRUCTURE_REPO,
     'organization': config.MEDIASDK_ORGANIZATION}
]

for repo in CI_REPOSITORIES:
    repo_url = f"https://github.com/{repo['organization']}/{repo['name']}.git"

    c["change_source"].append(GitPoller(
        repourl=repo_url,
        # Dir for the output of git remote-ls command
        workdir=f"gitpoller-{repo['name']}",
        # Poll master, release branches and open pull request branches
        # Filters performs in following order:
        # branches (discard all not release branches)
        # pull_request (add branches of open pull request)
        # *fetch branches*
        # change_filter (checking changes)
        branches=lambda branch: bb.utils.is_release_branch(branch),
        pull_request_branches=bb.utils.get_open_pull_request_branches(repo['organization'],
                                                                      repo['name'],
                                                                      token=config.GITHUB_TOKEN),
        change_filter=MediasdkChangeChecker(config.GITHUB_TOKEN),
        category="media",
        pollInterval=config.POLL_INTERVAL,
        pollAtLaunch=True))


# TODO: All repos should be declared in cycle above, but need to improve filtration changes
#        to avoid affecting efficiency
for repo in config.AUTO_UPDATED_REPOSITORIES:
    repo_url = f"https://github.com/{config.INTEL_ORGANIZATION}/{repo}.git"

    c["change_source"].append(GitPoller(
        repourl=repo_url,
        workdir=f"gitpoller-{repo}",
        branches=['master'],
        category="auto_update",
        change_filter=MediasdkChangeChecker(),
        pollInterval=config.POLL_INTERVAL,
        pollAtLaunch=True))

# Web Interface
c["www"] = dict(port=int(config.PORT),
                plugins={"console_view": True,
                         "grid_view": True})

# Database
c["db"] = {"db_url": config.DATABASE_URL}

# It disables automatic merging of requests (to build EACH commit)
c["collapseRequests"] = False
