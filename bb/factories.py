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

"""
This module contain all code for preparing factories for builders.
"""

import time

from twisted.internet import defer
from buildbot.plugins import util, steps
from buildbot.process import buildstep, logobserver

import bb.utils
import bb.buildbot_utils as buildbot_utils
from common.helper import Stage, TestStage
from common.mediasdk_directories import MediaSdkDirectories


@util.renderer
def is_build_dependency_needed(props):
    if props.hasProperty(bb.utils.SKIP_BUILDING_DEPENDENCY_PROPERTY):
        props.build.currentStep.descriptionDone = 'Already built'
        return False
    return True


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
                        self.builder_spec[parent_builder]['next_builders'][builder_name].append(
                            trigger)
                    elif next_builders and not next_builders.get(builder_name):
                        self.builder_spec[parent_builder]['next_builders'][builder_name] = [trigger]
                    else:
                        self.builder_spec[parent_builder]['next_builders'] = {
                            builder_name: [trigger]}

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


class DependencyChecker(buildstep.ShellMixin, steps.BuildStep):
    def __init__(self, **kwargs):
        kwargs = self.setupShellMixin(kwargs)
        steps.BuildStep.__init__(self, **kwargs)
        self.observer = logobserver.BufferLogObserver()
        self.addLogObserver('stdio', self.observer)

    @defer.inlineCallbacks
    def run(self):
        cmd = yield self.makeRemoteShellCommand()
        yield self.runCommand(cmd)

        stdout = self.observer.getStdout()
        if bb.utils.SKIP_BUILDING_DEPENDENCY_PHRASE in stdout:
            self.build.setProperty(bb.utils.SKIP_BUILDING_DEPENDENCY_PROPERTY, True, 'Build')
        defer.returnValue(util.SUCCESS)


class StepsGenerator(steps.BuildStep):
    """
    Add steps in run-time [dynamically] based on the builder properties and commit information
    """

    def __init__(self, default_factory, build_specification, **kwargs):
        steps.BuildStep.__init__(self, **kwargs)
        self.name = 'Generate steps'
        self.default_factory = default_factory
        self.build_specification = build_specification

    def _is_last_build(self, current_builder, all_builders):
        """
        Checks status of builds for all_buildrers; Return True if build of current_builder
        is last build.

        :param current_builder: str
        :param all_builders: dict
        :return: True or False
        """

        #  All builders must have build request (dict with status of build)
        if not all(all_builders.values()):
            return False

        number_of_passed_builds = len([build for build in all_builders.values() if
                                       build['result'] == buildbot_utils.BuildStatus.PASSED])

        running_builds = {builder: build for builder, build in all_builders.items() if
                          build['result'] == buildbot_utils.BuildStatus.RUNNING}

        # All builds must be passed or running, builds with other statuses can not run anything
        if number_of_passed_builds + len(running_builds) != len(all_builders):
            return False

        builds_executed_trigger = {builder: build for builder, build in running_builds.items() if
                                   build.get('step_name') == 'trigger'}

        # Current build is not last if any other build execute not trigger stage, because trigger is
        # last stage in all builds
        if len(running_builds) != len(builds_executed_trigger):
            return False

        if len(builds_executed_trigger) == 1:
            if number_of_passed_builds == len(all_builders) - 1:
                return True
        else:
            last_builder_name = None
            # Can not use None, because it is key parameter for selection
            last_trigger_creation_time = True
            for builder, build in builds_executed_trigger.items():
                # In this case the step is just started in not current build (current build always
                # has this parameter), so current build is not last; return False
                if build['step_started_at'] is None:
                    last_builder_name = None
                    break
                # This block will be executed one time for first element only
                elif last_trigger_creation_time == True:
                    last_trigger_creation_time = build['step_started_at']
                    last_builder_name = builder
                elif build['step_started_at'] > last_trigger_creation_time:
                    last_trigger_creation_time = build['step_started_at']
                    last_builder_name = builder

            if last_builder_name == current_builder:
                return True

        return False

    @defer.inlineCallbacks
    def is_trigger_needed(self, step):
        """
        Check dependencies for builders that this builder can trigger

        :param step: BuildStep object from buildbot.process.buildstep
        :return: True or False
            WARNING: Also redefine step.schedulerNames parameter
        """
        if step.build.results != buildbot_utils.BuildStatus.PASSED.value:
            defer.returnValue(False)
        build_id = step.build.buildid

        builder_names_for_triggering = []

        # Filtration next builders by branch and project
        builder_names_for_triggering_after_check = {}
        for builder, triggers in self.build_specification['next_builders'].items():
            for trigger in triggers:
                if trigger['filter'].check_commit(step):
                    builder_names_for_triggering_after_check[builder] = trigger
                    break

        if step.build.builder.name == 'trigger':
            # These builders haven't dependencies, because it is root builders
            # All builders that can be triggered from these builders must be triggered without any checks
            builder_names_for_triggering += list(builder_names_for_triggering_after_check.keys())

        else:
            # Get all builds triggered by parent of this build
            parent_build_id = yield bb.utils.get_root_build_id(build_id, step.build.master)
            triggered_builds_from_parent_build = yield buildbot_utils.get_triggered_builds(
                parent_build_id,
                step.build.master)

            # Check dependencies for builders from builder_names_for_triggering_after_check
            for next_builder, dependency in builder_names_for_triggering_after_check.items():
                dependent_builders = {k: triggered_builds_from_parent_build.get(k, None) for k
                                      in dependency.get('builders', [])}
                if self._is_last_build(step.build.builder.name, dependent_builders):
                    builder_names_for_triggering.append(next_builder)

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

    def __init__(self, mode, deploying_infrastructure, run_command, ci_service):
        self.mode = mode
        self.deploying_infrastructure = deploying_infrastructure
        self.run_command = run_command
        self.ci_service = ci_service

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
                                       hideStepIf=self.mode == bb.utils.Mode.PRODUCTION_MODE))
        return factory

    def get_manifest_path(self, props):
        """
        Return path to main manifest on share as string for target worker.
        get_path and util.Interpolate wrappers are not needed.
        """
        return str(MediaSdkDirectories.get_commit_dir(
            props.getProperty('target_branch') or props.getProperty('branch'),
            props.getProperty('event_type'),
            props.getProperty("revision"),
            os_type=props.getProperty('os'),
            # TODO: import the const from common
            product='manifest') / 'manifest.yml')

    def factory_with_deploying_infrastructure_step(self, props):
        factory = list()
        # return empty factory if deploying infrastructure is disabled
        # otherwise return factory with deploying infrastructure step
        if not self.deploying_infrastructure:
            return factory

        @util.renderer
        @defer.inlineCallbacks
        def get_infrastructure_deploying_cmd(props):

            infra_deploying_cmd = [
                self.run_command[props['os']], 'extract_repo.py',
                '--infra-type', 'OPEN_SOURCE_INFRA',
                '--root-dir', props.getProperty("builddir")]

            # TODO: create file with const
            # TODO: Calculate manifest path in one place (now it implemented in deploy and build)
            if props.getProperty('buildername') != 'trigger':
                infra_deploying_cmd.extend(['--manifest-path', self.get_manifest_path(props)])

            # Changes from product-configs\fork of product configs repositories will be deployed as is.
            # Infrastructure for changes from other repos will be extracted from master\release branch of
            # Intel-Media-SDK/product-configs repository.
            if bb.utils.get_repository_name_by_url(
                    props.getProperty('repository')) == "product-configs":
                infra_deploying_cmd += ['--commit-id', props.getProperty("revision"),
                                        '--branch', props.getProperty("branch")]

            else:
                build_id = props.build.buildid
                sourcestamps = yield props.build.master.db.sourcestamps.getSourceStampsForBuild(
                    build_id)
                sourcestamps_created_time = sourcestamps[0]['created_at'].timestamp()
                formatted_sourcestamp_created_time = time.strftime('%Y-%m-%d %H:%M:%S',
                                                                   time.localtime(
                                                                       sourcestamps_created_time))
                infra_deploying_cmd += ['--commit-time',
                                        formatted_sourcestamp_created_time,
                                        # Set 'branch' value if 'target_branch' property not set.
                                        '--branch',
                                        util.Interpolate(
                                            '%(prop:target_branch:-%(prop:branch)s)s')]

            defer.returnValue(infra_deploying_cmd)

        get_path = bb.utils.get_path_on_os(props['os'])
        factory.append(steps.ShellCommand(name='deploying infrastructure',
                                          command=get_infrastructure_deploying_cmd,
                                          workdir=get_path(r'../common')))
        return factory

    def init_trigger_factory(self, build_specification, props):
        trigger_factory = self.factory_with_deploying_infrastructure_step(props)
        worker_os = props['os']
        get_path = bb.utils.get_path_on_os(worker_os)

        repository_name = bb.utils.get_repository_name_by_url(props['repository'])

        trigger_factory.extend([
            steps.ShellCommand(
                name='create manifest',
                command=[self.run_command[worker_os], 'manifest_runner.py',
                         '--root-dir',
                         util.Interpolate(get_path(r'%(prop:builddir)s/repositories')),
                         '--repo', repository_name,
                         '--branch', util.Interpolate('%(prop:branch)s'),
                         '--revision', util.Interpolate('%(prop:revision)s'),
                         '--build-event', props['event_type'],
                         '--commit-time', buildbot_utils.get_event_creation_time] +
                        (['--target-branch', props['target_branch']] if props.hasProperty('target_branch') else []),
                workdir=get_path(r'infrastructure/build_scripts'))])

        # TODO: List of repos should be imported from config
        if props['event_type'] == 'pre_commit' and repository_name in ['MediaSDK', 'infrastructure',
                                                                       'product-configs']:
            trigger_factory.extend([
                steps.ShellCommand(
                    name='check author name and email',
                    command=[self.run_command[worker_os], 'check_author.py',
                             '--repo-path',
                             util.Interpolate(
                                 get_path(rf'%(prop:builddir)s/repositories/{repository_name}')),
                             '--revision', util.Interpolate('%(prop:revision)s')],
                    workdir=get_path(r'infrastructure/pre_commit_checks')),

                steps.ShellCommand(
                    name='check copyright',
                    command=[self.run_command[worker_os], 'check_copyright.py',
                             '--repo-path',
                             util.Interpolate(
                                 get_path(f'%(prop:builddir)s/repositories/{repository_name}')),
                             '--commit-id', util.Interpolate(r'%(prop:revision)s'),
                             '--report-path',
                             util.Interpolate(
                                 get_path(r'%(prop:builddir)s/checks/pre_commit_checks.json'))],
                    workdir=get_path(r'infrastructure/pre_commit_checks/check_copyright'))])

        files = props.build.allFiles()
        for file_name in files:
            if file_name.endswith('.py'):
                # Length of step name must not be longer 50 symbols
                step_name = ('..' + file_name[-35:]) if len(file_name) > 35 else file_name
                trigger_factory.append(
                    steps.ShellCommand(name=f'pylint: {step_name}',
                                       # pylint checks always passed
                                       command=['pylint', file_name, '--exit-zero'],
                                       workdir=get_path(f'repositories/{repository_name}')))
        return trigger_factory

    def auto_update_manifest_factory(self, build_specification, props):
        updater_factory = self.factory_with_deploying_infrastructure_step(props)
        worker_os = props['os']
        get_path = bb.utils.get_path_on_os(worker_os)

        repository_name = bb.utils.get_repository_name_by_url(props['repository'])

        # Additional checks for for auto-uptdated repositories are not needed.
        updater_factory.append(steps.ShellCommand(
            name=f'update manifest',
            command=[self.run_command[worker_os], 'update_version.py',
                     '--branch', util.Interpolate('%(prop:branch)s'),
                     '--revision', util.Interpolate('%(prop:revision)s'),
                     '--component-name', repository_name],
            workdir=get_path(r'infrastructure/common')))
        return updater_factory

    def init_build_factory(self, build_specification, props):
        conf_file = build_specification["product_conf_file"]
        product_type = build_specification["product_type"]
        build_type = build_specification["build_type"]
        api_latest = build_specification.get("api_latest")
        fastboot = build_specification.get("fastboot")
        compiler = build_specification.get("compiler")
        compiler_version = build_specification.get("compiler_version")
        build_factory = self.factory_with_deploying_infrastructure_step(props)

        worker_os = props['os']
        get_path = bb.utils.get_path_on_os(worker_os)

        # TODO: rename to component
        dependency_name = build_specification.get('dependency_name')

        build_factory.append(
            DependencyChecker(
                name=f"check {dependency_name} on share",
                command=[self.run_command[worker_os], 'component_checker.py',
                         '--path-to-manifest', self.get_manifest_path(props),
                         '--component-name', dependency_name,
                         '--product-type', product_type,
                         '--build-type', build_type],
                workdir=get_path(r'infrastructure/common')))

        shell_commands = [self.run_command[worker_os],
                          "build_runner.py",
                          "--build-config",
                          util.Interpolate(
                              get_path(rf"%(prop:builddir)s/product-configs/{conf_file}")),
                          "--root-dir", util.Interpolate(get_path(r"%(prop:builddir)s/build_dir")),
                          "--manifest", self.get_manifest_path(props),
                          "--component", dependency_name,
                          "--build-type", build_type,
                          "--product-type", product_type]

        if api_latest:
            shell_commands.append("api_latest=True")
        if fastboot:
            shell_commands.append("fastboot=True")
        if compiler and compiler_version:
            shell_commands.extend([f"compiler={compiler}", f"compiler_version={compiler_version}"])

        # Build by stages: clean, extract, build, install, pack, copy
        for stage in Stage:
            build_factory.append(
                steps.ShellCommand(command=shell_commands + ["--stage", stage.value],
                                   workdir=get_path(r"infrastructure/build_scripts"),
                                   name=stage.value,
                                   doStepIf=is_build_dependency_needed,
                                   timeout=60 * 60)) # 1 hour for igc
        return build_factory

    def init_test_factory(self, test_specification, props):
        product_type = test_specification['product_type']
        build_type = test_specification['build_type']
        conf_file = test_specification["product_conf_file"]
        custom_types = test_specification["custom_types"]

        test_factory = self.factory_with_deploying_infrastructure_step(props)

        worker_os = props['os']
        get_path = bb.utils.get_path_on_os(worker_os)

        repository_name = bb.utils.get_repository_name_by_url(props['repository'])
        # TODO: define component mapper in config
        component_by_repository = {'product-configs': 'mediasdk',
                                   'MediaSDK': 'mediasdk',
                                   'media-driver': 'media-driver'}

        command = [self.run_command[worker_os], "tests_runner.py",
                   '--manifest', self.get_manifest_path(props),
                   '--component', component_by_repository[repository_name],
                   '--test-config', util.Interpolate(
                              get_path(rf"%(prop:builddir)s/product-configs/{conf_file}")),
                   '--root-dir', util.Interpolate('%(prop:builddir)s/test_dir'),
                   '--product-type', product_type,
                   '--build-type', build_type,
                   '--custom-types', custom_types,
                   '--stage']

        for test_stage in TestStage:
            test_factory.append(
                steps.ShellCommand(name=test_stage.value,
                                   command=command + [test_stage.value],
                                   workdir=get_path(r"infrastructure/build_scripts")))
        return test_factory

    def init_package_factory(self, factory_params, props):
        """Displays links to common package for each component"""

        package_factory = self.factory_with_deploying_infrastructure_step(props)

        worker_os = props['os']
        get_path = bb.utils.get_path_on_os(worker_os)

        package_factory.append(
            steps.ShellCommand(name=bb.utils.PACKAGES,
                               command=[self.run_command[worker_os], 'build_links_summary.py',
                                        '--manifest', self.get_manifest_path(props)],
                               workdir=get_path(r"infrastructure/bb")))
        return package_factory
