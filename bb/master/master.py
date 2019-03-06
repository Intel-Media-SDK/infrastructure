# Copyright (c) 2018 Intel Corporation
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

import time
import sys
import pathlib
from enum import Enum

from buildbot.changes.gitpoller import GitPoller
from buildbot.changes.github import GitHubPullrequestPoller
from buildbot.plugins import schedulers, util, steps, worker, reporters
from twisted.internet import defer

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
import config

from common import mediasdk_directories


class Stage(Enum):
    CLEAN = "clean"
    EXTRACT = "extract"
    BUILD = "build"
    INSTALL = "install"
    PACK = "pack"
    COPY = "copy"


def get_repository_name_by_url(repo_url):
    # Some magic for getting repository name from GitHub url, by example
    #  https://github.com/Intel-Media-SDK/product-configs.git -> product-configs
    return repo_url.split('/')[-1][:-4]


@util.renderer
@defer.inlineCallbacks
def get_infrastructure_deploying_cmd(props):
    infrastructure_deploying_cmd = [
        config.RUN_COMMAND, 'extract_repo.py',
        '--repo-name', 'OPEN_SOURCE_INFRA',
        '--root-dir', props.getProperty("builddir")]

    # Changes from product-configs\fork of product configs repositories will be deployed as is.
    # Infrastructure for changes from other repos will be extracted from master\release branch of
    # Intel-Media-SDK/product-configs repository.
    if get_repository_name_by_url(props.getProperty('repository')) == config.PRODUCT_CONFIGS_REPO:
        infrastructure_deploying_cmd += ['--commit-id', props.getProperty("revision"),
                                         '--branch', props.getProperty("branch")]

    else:
        build_id = props.build.buildid
        sourcestamps = yield props.build.master.db.sourcestamps.getSourceStampsForBuild(build_id)
        sourcestamps_created_time = sourcestamps[0]['created_at'].timestamp()
        formatted_sourcestamp_created_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                                           time.localtime(
                                                               sourcestamps_created_time))
        infrastructure_deploying_cmd += ['--commit-time', formatted_sourcestamp_created_time,
                                         # Set 'branch' value if 'target_branch' property not set.
                                         '--branch',
                                         util.Interpolate(
                                             '%(prop:target_branch:-%(prop:branch)s)s')]

    defer.returnValue(infrastructure_deploying_cmd)


@util.renderer
def get_changed_repo(props):
    repo_url = props.getProperty('repository')
    branch = props.getProperty('branch')
    revision = props.getProperty('revision')
    # Some magic for getting repository name from url
    # https://github.com/Intel-Media-SDK/product-configs.git -> product-configs
    repo_name = repo_url.split('/')[-1][:-4]
    return f"{repo_name}:{branch}:{revision}"


@util.renderer
@defer.inlineCallbacks
def get_event_creation_time(props):
    build_id = props.build.buildid
    sourcestamps = yield props.build.master.db.sourcestamps.getSourceStampsForBuild(build_id)
    sourcestamp_created_time = sourcestamps[0]['created_at'].timestamp()
    defer.returnValue(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(sourcestamp_created_time)))


def are_next_builds_needed(step):
    if step.build.results != util.SUCCESS:
        return False
    branch = step.getProperty('target_branch') or step.getProperty('branch')
    builder_names_for_triggering = []
    for builder in config.BUILDERS:
        if callable(builder['branch']) and builder['branch'](branch):
            builder_names_for_triggering.append(builder['name'])
    # Update builder names for trigger step
    # NOTE: scheduler names are the same as builder names
    step.schedulerNames = builder_names_for_triggering
    return bool(builder_names_for_triggering)


class StepsGenerator(steps.BuildStep):
    """
    Add steps in run-time [dynamically] based on the builder properties and commit information
    """

    def __init__(self, default_factory, build_specification, **kwargs):
        steps.BuildStep.__init__(self, **kwargs)
        self.name = 'Generate steps'
        self.default_factory = default_factory
        self.build_specification = build_specification

    @defer.inlineCallbacks
    def run(self):
        builder_steps = self.default_factory(self.build_specification, self.build.properties)
        self.build.addStepsAfterCurrentStep(builder_steps)

        # generator is used, because logs adding may take long time
        yield self.addCompleteLog('list of steps',
                                  str('\n'.join([str(step) for step in builder_steps])))
        defer.returnValue(util.SUCCESS)


def dynamic_factory(default_factory, build_specification):
    factory = util.BuildFactory()
    # Hide debug information about build steps for production mode
    factory.addStep(StepsGenerator(default_factory=default_factory,
                                   build_specification=build_specification,
                                   hideStepIf=config.CURRENT_MODE == config.Mode.PRODUCTION_MODE))
    return factory


def init_trigger_factory(trigger_specification, props):
    trigger_factory = factory_with_deploying_infrastructure_step() if config.DEPLOYING_INFRASTRUCTURE \
        else []

    repository_name = get_repository_name_by_url(props['repository'])
    trigger_factory.extend([

        steps.ShellCommand(
            name='extract repository',
            command=[config.RUN_COMMAND, 'extract_repo.py',
                     '--root-dir', util.Interpolate('%(prop:builddir)s/repositories'),
                     '--repo-name', repository_name,
                     '--branch', util.Interpolate('%(prop:branch)s'),
                     '--commit-id', util.Interpolate('%(prop:revision)s')],
            workdir=r'infrastructure/common'),

        steps.ShellCommand(
            name='check author name and email',
            command=[config.RUN_COMMAND, 'check_author.py',
                     '--repo-path',
                     util.Interpolate(f'%(prop:builddir)s/repositories/{repository_name}'),
                     '--revision', util.Interpolate('%(prop:revision)s')],
            workdir=r'infrastructure/pre_commit_checks'),

        steps.Trigger(schedulerNames=list([builder['name'] for builder in config.BUILDERS]),
                      waitForFinish=False,
                      doStepIf=are_next_builds_needed,
                      updateSourceStamp=True)])

    return trigger_factory


def factory_with_deploying_infrastructure_step():
    factory = [steps.ShellCommand(name='deploying infrastructure',
                                  command=get_infrastructure_deploying_cmd,
                                  workdir=r'../common')]
    return factory


def init_build_factory(build_specification, props):
    conf_file = build_specification["product_conf_file"]
    product_type = build_specification["product_type"]
    build_type = build_specification["build_type"]
    api_latest = build_specification["api_latest"]
    fastboot = build_specification["fastboot"]
    compiler = build_specification["compiler"]
    compiler_version = build_specification["compiler_version"]
    build_factory = factory_with_deploying_infrastructure_step() if config.DEPLOYING_INFRASTRUCTURE \
        else []

    shell_commands = [config.RUN_COMMAND,
                      "build_runner.py",
                      "--build-config",
                      util.Interpolate(r"%(prop:builddir)s/product-configs/%(kw:conf_file)s",
                                       conf_file=conf_file),
                      "--root-dir", util.Interpolate(r"%(prop:builddir)s/build_dir"),
                      "--changed-repo", get_changed_repo,
                      "--build-type", build_type,
                      "--build-event", "commit",
                      "--product-type", product_type,
                      "--commit-time", get_event_creation_time,
                      f"compiler={compiler}",
                      f"compiler_version={compiler_version}",
                      ]
    if api_latest:
        shell_commands.append("api_latest=True")
    if fastboot:
        shell_commands.append("fastboot=True")
    if props.hasProperty('target_branch'):
        shell_commands += ['--target-branch', props['target_branch']]

    # Build by stages: clean, extract, build, install, pack, copy
    for stage in Stage:
        build_factory.append(
            steps.ShellCommand(command=shell_commands + ["--stage", stage.value],
                               workdir=r"infrastructure/build_scripts",
                               name=stage.value))

    # Trigger tests
    # Tests will be triggered only if product types are similar
    # Currently they will be triggered only for `build-master-branch`, `build`, `build-api-next`
    for test_specification in config.TESTERS:
        if product_type == test_specification["product_type"]:
            build_factory.append(steps.Trigger(schedulerNames=[test_specification["name"]],
                                               waitForFinish=False,
                                               updateSourceStamp=True))
    return build_factory


def init_test_factory(test_specification, props):
    product_type = test_specification["product_type"]
    build_type = test_specification["build_type"]
    test_factory = factory_with_deploying_infrastructure_step() if config.DEPLOYING_INFRASTRUCTURE \
        else []

    test_factory.append(
        steps.ShellCommand(command=[config.RUN_COMMAND,
                                    "test_adapter.py",
                                    "--branch", util.Interpolate(r"%(prop:branch)s"),
                                    "--build-event", "commit",
                                    "--product-type", product_type,
                                    "--commit-id", util.Interpolate(r"%(prop:revision)s"),
                                    "--build-type", build_type,
                                    "--root-dir", util.Interpolate(r"%(prop:builddir)s/build_dir")],
                           workdir=r"infrastructure/ted_adapter"))
    return test_factory


c = BuildmasterConfig = {}

# Add workers
c["workers"] = []
ALL_WORKERS_NAMES = []
for worker_ in config.WORKERS.values():
    for w_name, prop in worker_.items():
        ALL_WORKERS_NAMES.append(w_name)
        c["workers"].append(worker.Worker(w_name, config.WORKER_PASS,
                                          properties=prop,
                                          max_builds=prop.get(
                                              'max_builds') or 1))  # To disable parallel builds on one worker

# Basic config
c["protocols"] = {"pb": {"port": config.WORKER_PORT}}
c["buildbotNetUsageData"] = config.BUILDBOT_NET_USAGE_DATA
c["title"] = config.BUILDBOT_TITLE
c["titleURL"] = config.REPO_URL
c["buildbotURL"] = config.BUILDBOT_URL


def get_workers(worker_pool):
    return list(config.WORKERS[worker_pool].keys())


# Create schedulers and builders for builds
c["schedulers"] = [
    schedulers.SingleBranchScheduler(name=config.TRIGGER,
                                     change_filter=util.ChangeFilter(category="mediasdk"),
                                     treeStableTimer=config.BUILDBOT_TREE_STABLE_TIMER,
                                     builderNames=[config.TRIGGER])]
c["builders"] = [util.BuilderConfig(name=config.TRIGGER,
                                    workernames=ALL_WORKERS_NAMES,
                                    factory=dynamic_factory(init_trigger_factory, None))]

for build_specification in config.BUILDERS:
    c["schedulers"].append(schedulers.Triggerable(name=build_specification["name"],
                                                  builderNames=[build_specification["name"]]))
    c["builders"].append(util.BuilderConfig(name=build_specification["name"],
                                            workernames=get_workers(build_specification["worker"]),
                                            factory=dynamic_factory(init_build_factory,
                                                                    build_specification)))

# Create schedulers and builders for tests
for test_specification in config.TESTERS:
    c["schedulers"].append(schedulers.Triggerable(name=test_specification["name"],
                                                  builderNames=[test_specification["name"]]))
    c["builders"].append(util.BuilderConfig(name=test_specification["name"],
                                            workernames=get_workers(test_specification["worker"]),
                                            factory=dynamic_factory(init_test_factory,
                                                                    test_specification)))

# Push status of build to the Github
c["services"] = [
    reporters.GitHubStatusPush(token=config.GITHUB_TOKEN,
                               context=util.Interpolate("buildbot/%(prop:buildername)s"),
                               startDescription="Started",
                               endDescription="Done",
                               verbose=True)]
# Will be useful for implementing build notifications in the future
#    reporters.GitHubCommentPush(token=config.GITHUB_TOKEN,
#                                 startDescription="Started (comment)",
#                                 endDescription="Done (comment)",
#                                 verbose=True,
#                                 debug=True)]

# Get changes
c["change_source"] = []

REPOSITORIES = [
    {'name': config.GITHUB_OWNERS_REPO,
     # All pull request
     'pull_request_filter': lambda x: True},
    {'name': config.PRODUCT_CONFIGS_REPO,
     # Only for members of Intel-Media-SDK organization
     # This filter is needed for security, because via product configs can do everything
     'pull_request_filter': mediasdk_directories.is_comitter_the_org_member(
         organization=config.GITHUB_OWNER,
         token=config.GITHUB_TOKEN)}
]

for repo in REPOSITORIES:
    repo_url = f"https://github.com/{config.GITHUB_OWNER}/{repo['name']}.git"

    c["change_source"].append(GitPoller(
        repourl=repo_url,
        workdir=f"gitpoller-{repo['name']}",  # Dir for the output of git remote-ls command
        # Poll master and release branches only
        branches=mediasdk_directories.is_release_branch,
        category="mediasdk",
        pollInterval=config.POLL_INTERVAL,
        pollAtLaunch=True))

    c["change_source"].append(GitHubPullrequestPoller(
        owner=config.GITHUB_OWNER,
        repo=repo['name'],
        token=config.GITHUB_TOKEN,
        pullrequest_filter=repo['pull_request_filter'],
        category="mediasdk",
        # Change branch property from '{branch_name}' to 'refs/pull/{pull_request_id}/merge'
        # See more: https://docs.buildbot.net/current/manual/configuration/changesources.html#githubpullrequestpoller
        magic_link=True,
        pollInterval=config.POLL_INTERVAL,  # Interval of PR`s checking
        pollAtLaunch=True))

# Web Interface
c["www"] = dict(port=int(config.PORT),
                plugins={"console_view": True})

# Database
c["db"] = {"db_url": config.DATABASE_URL}

# It disables automatic merging of requests (to build EACH commit)
c["collapseRequests"] = False
