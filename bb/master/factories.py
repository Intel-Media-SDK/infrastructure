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
This module contain all code for preparing factories for builders.
"""

import time

from collections import defaultdict
from twisted.internet import defer
from buildbot.plugins import util, steps
from bb.utils import get_repository_name_by_url, BuildStatus, Mode

from common.helper import Stage


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


@defer.inlineCallbacks
def get_triggered_builds(build_id, master):
    """
    Recursively gets all triggered builds to identify current status of pipeline

    :param build_id: int
    :param master: BuildMaster object from buildbot.master
    :return: defaultdict
        Example: {'builder_name': {'buildrequest_id': str,
                                   'result': BuildStatus,
                                   'build_id': None or int},
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

            triggered_builds[builder_name]['result'] = BuildStatus(last_build['results'])
            triggered_builds[builder_name]['build_id'] = last_build['id']

            new_builds = yield get_triggered_builds(last_build['id'], master)
            triggered_builds.update(new_builds)

        else:
            triggered_builds[builder_name]['result'] = BuildStatus.NOT_STARTED
            triggered_builds[builder_name]['build_id'] = None

    defer.returnValue(triggered_builds)


class Flow:
    """
    Class for preparing builders.
    """

    def __init__(self, builder_spec, factories):
        self.builder_spec = builder_spec
        self.factories = factories

    def _prepare_flow(self):
        """
        Add 'next_builders' dict to builder if others builders in triggers property has name of this builder.

        Later this dict will be used for checking statuses of dependent builders in
        StepsGenerator.is_trigger_needed function

        :return: None
        """
        for builder_name, props in self.builder_spec.items():
            triggers = props.get('triggers', [])
            for trigger in triggers:
                parent_builders = trigger.get('builders', ['trigger'])
                for parent_builder in parent_builders:
                    next_builders = self.builder_spec[parent_builder].get('next_builders')
                    if next_builders and next_builders.get(builder_name):
                        self.builder_spec[parent_builder]['next_builders'][builder_name].append(trigger)
                    elif next_builders and not next_builders.get(builder_name):
                        self.builder_spec[parent_builder]['next_builders'][builder_name] = [trigger]
                    else:
                        self.builder_spec[parent_builder]['next_builders'] = {builder_name: [trigger]}

    def get_prepared_builders(self):
        """
        Create factories for builders.

        :return: dict
        """
        self._prepare_flow()

        for builder_name, props in self.builder_spec.items():
            self.builder_spec[builder_name]['factory'] = self.factories.dynamic_factory(
                props['factory'], props)

        return self.builder_spec


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
    def is_trigger_needed(self, step):
        """
        Check dependencies for builders that this builder can trigger

        :param step: BuildStep object from buildbot.process.buildstep
        :return: True or False
            WARNING: Also redefine step.schedulerNames parameter
        """
        if step.build.results != BuildStatus.PASSED.value:
            defer.returnValue(False)
        build_id = step.build.buildid
        project = get_repository_name_by_url(step.build.properties.getProperty('repository'))
        branch = step.build.properties.getProperty('branch')

        builder_names_for_triggering = []

        # Filtration next builders by branch and project
        builder_names_for_triggering_after_check = []
        for builder, triggers in self.build_specification['next_builders'].items():
            for trigger in triggers:
                if project in trigger.get('projects', []) and trigger.get('branches')(branch):
                    builder_names_for_triggering_after_check.append(builder)
                    break

        if step.build.builder.name == 'trigger':
            # These builders haven't dependencies, because it is root builders
            # All builders that can be triggered from these builders must be triggered without any checks
            builder_names_for_triggering += builder_names_for_triggering_after_check

        else:
            # Get all builds triggered by parent of this build
            parent_build_id = yield get_root_build_id(build_id, step.build.master)
            triggered_builds_from_parent_build = yield get_triggered_builds(parent_build_id,
                                                                            step.build.master)

            # Check dependencies for builders from builder_names_for_triggering_after_check
            for next_builder in builder_names_for_triggering_after_check:
                for dependency in self.build_specification['next_builders'][next_builder]:
                    for dependent_builder in dependency.get('builders', []):
                        build = triggered_builds_from_parent_build.get(dependent_builder)
                        if build is None or build_id != build['build_id'] and build[
                            'result'] != BuildStatus.PASSED:
                            break
                    else:
                        builder_names_for_triggering.append(next_builder)
                        break

        # Update builder names for trigger step
        # NOTE: scheduler names are the same as builder names
        step.schedulerNames = builder_names_for_triggering
        defer.returnValue(bool(builder_names_for_triggering))

    @defer.inlineCallbacks
    def run(self):
        """
        Create factory for this build.

        :return: util.SUCCESS or Exception
        """
        builder_steps = self.default_factory(self.build_specification, self.build.properties)
        if self.build_specification.get('next_builders'):
            builder_steps.append(
                steps.Trigger(schedulerNames=['trigger'],
                              waitForFinish=False,
                              updateSourceStamp=False,
                              doStepIf=self.is_trigger_needed))

        self.build.addStepsAfterCurrentStep(builder_steps)

        # generator is used, because logs adding may take long time
        yield self.addCompleteLog('list of steps',
                                  str('\n'.join([str(step) for step in builder_steps])))
        defer.returnValue(util.SUCCESS)


class Factories:
    """
    Contain all factories code.
    Implemented as class for sharing common parameters between all factories.
    """

    def __init__(self, mode, deploying_infrastructure, run_command):
        self.mode = mode
        self.deploying_infrastructure = deploying_infrastructure
        self.run_command = run_command

    def dynamic_factory(self, default_factory, build_specification):
        """
        Create buildbot factory with one dynamic step.
        All factories will be created by this method.

        :param default_factory: other method of this class
        :param build_specification: dict
        :return: BuildFactory
        """
        factory = util.BuildFactory()
        # Hide debug information about build steps for production mode
        factory.addStep(StepsGenerator(default_factory=default_factory,
                                       build_specification=build_specification,
                                       hideStepIf=self.mode == Mode.PRODUCTION_MODE))
        return factory

    def factory_with_deploying_infrastructure_step(self):
        factory = list()
        # return empty factory if deploying infrastructure is disabled
        # otherwise return factory with deploying infrastructure step
        if not self.deploying_infrastructure:
            return factory

        @util.renderer
        @defer.inlineCallbacks
        def get_infrastructure_deploying_cmd(props):
            infrastructure_deploying_cmd = [
                self.run_command, 'extract_repo.py',
                '--repo-name', 'OPEN_SOURCE_INFRA',
                '--root-dir', props.getProperty("builddir")]

            # Changes from product-configs\fork of product configs repositories will be deployed as is.
            # Infrastructure for changes from other repos will be extracted from master\release branch of
            # Intel-Media-SDK/product-configs repository.
            if get_repository_name_by_url(
                    props.getProperty('repository')) == "product-configs":
                infrastructure_deploying_cmd += ['--commit-id', props.getProperty("revision"),
                                                 '--branch', props.getProperty("branch")]

            else:
                build_id = props.build.buildid
                sourcestamps = yield props.build.master.db.sourcestamps.getSourceStampsForBuild(
                    build_id)
                sourcestamps_created_time = sourcestamps[0]['created_at'].timestamp()
                formatted_sourcestamp_created_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                   time.localtime(
                                                                       sourcestamps_created_time))
                infrastructure_deploying_cmd += ['--commit-time',
                                                 formatted_sourcestamp_created_time,
                                                 # Set 'branch' value if 'target_branch' property not set.
                                                 '--branch',
                                                 util.Interpolate(
                                                     '%(prop:target_branch:-%(prop:branch)s)s')]

            defer.returnValue(infrastructure_deploying_cmd)

        factory.append(steps.ShellCommand(name='deploying infrastructure',
                                          command=get_infrastructure_deploying_cmd,
                                          workdir=r'../common'))
        return factory

    def init_trigger_factory(self, build_specification, props):
        trigger_factory = self.factory_with_deploying_infrastructure_step()

        repository_name = get_repository_name_by_url(props['repository'])
        trigger_factory.extend([
            steps.ShellCommand(
                name='extract repository',
                command=[self.run_command, 'extract_repo.py',
                         '--root-dir', util.Interpolate('%(prop:builddir)s/repositories'),
                         '--repo-name', repository_name,
                         '--branch', util.Interpolate('%(prop:branch)s'),
                         '--commit-id', util.Interpolate('%(prop:revision)s')],
                workdir=r'infrastructure/common'),

            steps.ShellCommand(
                name='check author name and email',
                command=[self.run_command, 'check_author.py',
                         '--repo-path',
                         util.Interpolate(f'%(prop:builddir)s/repositories/{repository_name}'),
                         '--revision', util.Interpolate('%(prop:revision)s')],
                workdir=r'infrastructure/pre_commit_checks'),

            steps.ShellCommand(
                name='check copyright',
                command=[self.run_command, 'check_copyright.py',
                         '--repo-path',
                         util.Interpolate(f'%(prop:builddir)s/repositories/{repository_name}'),
                         '--commit-id', util.Interpolate(r'%(prop:revision)s'),
                         '--report-path',
                         util.Interpolate(r'%(prop:builddir)s/checks/pre_commit_checks.json')],
                workdir=r'infrastructure/pre_commit_checks/check_copyright')])

        return trigger_factory

    def init_build_factory(self, build_specification, props):
        conf_file = build_specification["product_conf_file"]
        product_type = build_specification["product_type"]
        build_type = build_specification["build_type"]
        api_latest = build_specification["api_latest"]
        fastboot = build_specification["fastboot"]
        compiler = build_specification["compiler"]
        compiler_version = build_specification["compiler_version"]
        build_factory = self.factory_with_deploying_infrastructure_step()

        shell_commands = [self.run_command,
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
        return build_factory

    def init_test_factory(self, test_specification, props):
        product_type = test_specification["product_type"]
        build_type = test_specification["build_type"]
        test_factory = self.factory_with_deploying_infrastructure_step()

        test_factory.append(
            steps.ShellCommand(command=[self.run_command,
                                        "test_adapter.py",
                                        "--branch", util.Interpolate(r"%(prop:branch)s"),
                                        "--build-event", "commit",
                                        "--product-type", product_type,
                                        "--commit-id", util.Interpolate(r"%(prop:revision)s"),
                                        "--build-type", build_type,
                                        "--root-dir",
                                        util.Interpolate(r"%(prop:builddir)s/build_dir")],
                               workdir=r"infrastructure/ted_adapter"))
        return test_factory