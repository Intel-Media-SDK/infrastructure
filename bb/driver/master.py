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

import time
import sys
import pathlib

from buildbot.changes.gitpoller import GitPoller
from buildbot.changes.github import GitHubPullrequestPoller
from buildbot.plugins import schedulers, util, steps, worker, reporters
from twisted.internet import defer

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))
import config
from common.mediasdk_directories import MediaSdkDirectories

from common.helper import Stage, TestStage
from bb.utils import is_release_branch, is_comitter_the_org_member, get_repository_name_by_url,\
    get_open_pull_request_branches, ChangeChecker


@util.renderer
def get_changed_repo(props):
    repo_url = props.getProperty('repository')
    branch = props.getProperty('branch')
    revision = props.getProperty('revision')

    return f"{get_repository_name_by_url(repo_url)}:{branch}:{revision}"


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
                      f"compiler={compiler}",
                      f"compiler_version={compiler_version}",
                      ]

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
    # Currently they will be triggered only for `build`
    for test_specification in config.TESTERS:
        if product_type == test_specification["product_type"]:
            build_factory.append(steps.Trigger(schedulerNames=[test_specification["name"]],
                                               waitForFinish=False,
                                               updateSourceStamp=True))
    return build_factory


def init_test_factory(test_specification, props):
    test_factory = factory_with_deploying_infrastructure_step() if config.DEPLOYING_INFRASTRUCTURE \
        else []

    driver_manifest_path = MediaSdkDirectories.get_build_dir(props['branch'], 'commit',
                                                             props['revision'],
                                                             test_specification['product_type'],
                                                             test_specification['build_type'],
                                                             product='driver')
    command = [config.RUN_COMMAND, "test_adapter.py",
               '--artifacts', str(driver_manifest_path),
               '--root-dir', util.Interpolate('%(prop:builddir)s'),
               '--stage']

    for test_stage in TestStage:
        test_factory.append(
            steps.ShellCommand(command=command+[test_stage],
                               workdir=r"infrastructure/build_scripts"))
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
                                     change_filter=util.ChangeFilter(category='driver'),
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
                               context=util.Interpolate("media-driver/%(prop:buildername)s"),
                               startDescription="Started",
                               endDescription="Done",
                               verbose=True,
                               builders=['build'])]

# Get changes
c["change_source"] = []

class DriverChecker(ChangeChecker):
    # No filtration
    def pull_request_filter(self, pull_request, files):
        return {'target_branch': pull_request['base']['ref']}


class ProductConfigsChecker(ChangeChecker):
    # Run builds for product configs repo only if files in driver
    # or infrastructure_version.py were modified.
    def commit_filter(self, repository, branch, revision, files, category):
        if any([file for file in files if file.startswith('driver/') or file == 'infrastructure_version.py']):
            return {}
        return None

    def pull_request_filter(self, pull_request, files):
        if any([file for file in files if file.startswith('driver/') or file == 'infrastructure_version.py']):
            return {'target_branch': pull_request['base']['ref']}
        return None


REPOSITORIES = [
    {'name': config.DRIVER_REPO,
     'organization': config.DRIVER_ORGANIZATION,
     'branches': True,
     'token': config.GITHUB_TOKEN,
     'change_filter': DriverChecker(config.GITHUB_TOKEN)},

    {'name': config.PRODUCT_CONFIGS_REPO,
     'organization': config.MEDIASDK_ORGANIZATION,
     'branches': is_release_branch,
     'token': config.GITHUB_TOKEN,
     'change_filter': ProductConfigsChecker(config.GITHUB_TOKEN)}
]

for repo in REPOSITORIES:
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
        branches=repo['branches'],
        pull_request_branches=get_open_pull_request_branches(repo['organization'], repo['name'],
                                                             repo.get('token')),
        change_filter=repo['change_filter'],
        category="driver",
        pollInterval=config.POLL_INTERVAL,
        pollAtLaunch=True))


# Web Interface
c["www"] = dict(port=int(config.PORT),
                plugins={"console_view": True})

# Database
c["db"] = {"db_url": config.DATABASE_URL}

# It disables automatic merging of requests (to build EACH commit)
c["collapseRequests"] = False
