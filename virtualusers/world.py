#!/usr/bin/env python
# coding: utf-8

import simpy
import datetime
import pandas as pd
import logging
from enum import Enum
import random
from itertools import repeat
from ruamel.yaml import YAML

log_filename = "logs-10.log"
mainLogger = logging.getLogger()
fhandler = logging.FileHandler(filename=log_filename, mode='w')
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fhandler.setFormatter(formatter)
mainLogger.addHandler(fhandler)
mainLogger.setLevel(logging.DEBUG)
mainLogger.debug("test")


class Metric(Enum):
    RW = "Requests Waiting"
    BS = "Busy Slots"
    AU = "Active Users"


class User:
    def __init__(self, id, scenario, world):
        self.id = id
        self.scenario = scenario
        self._world = world
        self.taskid = 0
        self.create()
        # Start the run process everytime an instance is created.
        # create itself as a processs
        self.action = self._world.env.process(self.run())

    def create(self):
        self.enteringAt = self._world.env.now
        self.name = "User-%03d" % self.id
        mainLogger.info(f"user created {self.name}")
        self._world.user_monitor.report_new_user(self)

    def run_old(self):
        while True:
            self.taskid += 1
            for task in self.scenario.tasks:
                taskname = task['Name']
                task_duration = task['Duration']
                mark = self._world.env.now
                mainLogger.debug(f"{self.name} starts task {taskname} at %d" % mark)

                if 'Res' in task:
                    self._world.user_monitor.report_start(
                            self.name,
                            self.scenario,
                            taskname,
                            self.taskid)
                    # We yield the process that process() returns
                    # to wait for it to finish
                    amount = task['Res']
                    yield self._world.env.process(self.process_task(task_duration, amount))
                    self._world.user_monitor.report_stop(
                            self.name,
                            self.scenario,
                            taskname,
                            self.taskid)
                else:
                    # wait some time even if no tracked
                    yield self._world.env.timeout(task_duration)

                mainLogger.debug(f"{self.name} ends task {taskname} at %d" % mark)

    def run(self):
        scenario = self.scenario
        mainLogger.debug(f"entering scenario: {scenario['name']}")
        mainLogger.debug(f"steps: {scenario['steps']}")
        if 'init' in scenario['steps']:
            mainLogger.debug("has init")
            mainLogger.debug("run_step_tasks init")
            process = self.run_step_tasks(scenario['steps']['init']['tasks'])
            yield self._world.env.process(process)

        if 'loop' in scenario['steps']:
            mainLogger.debug("has loop")
            step_loop = scenario['steps']['loop']
            if 'repeat' in step_loop:
                counter = 0
                while counter < step_loop['repeat']:
                    mainLogger.debug("run_step_tasks loop")
                    process = self.run_step_tasks(scenario['steps']['loop']['tasks'])
                    yield self._world.env.process(process)
                    counter += 1
            else:
                mainLogger.debug("run_step_tasks loop infinite")
                process = self.run_step_tasks(scenario['steps']['loop']['tasks'])
                yield self._world.env.process(process)

        if 'finally' in scenario['steps']:
            mainLogger.debug("has finally")
            mainLogger.debug("run_step_tasks finally")
            process = self.run_step_tasks(scenario['steps']['finally']['tasks'])
            yield self._world.env.process(process)

    def run_step_tasks(self, tasks):
        mainLogger.debug(f"entering run_step_tasks {tasks}")
        for task in tasks:
            mainLogger.debug(f"run_step_tasks::task: {task}")
            yield self._world.env.process(self.run_task(task))

    def run_task(self, task):
        mainLogger.debug(f"entering run_task {task} id:{self.taskid}")
        max_count = 1
        if 'repeat' in task:
            max_count = task['repeat']
        counter = 0
        while counter < max_count:
            self.taskid += 1
            mainLogger.debug(f"run task {task['name']} for {task['duration']}")
            if 'resources' in task:
                res_amount = task['resources']
                if 'parallel' in task:
                    mainLogger.debug("run_task in parallel")
                    res_amount = res_amount * task['parallel']
                mainLogger.debug(f"task resources amount {res_amount}")
                self._world.user_monitor.report_start(
                        self.name,
                        self.scenario['name'],
                        task['name'],
                        self.taskid)
                process = self.process_task(task['duration'], res_amount)
                yield self._world.env.process(process)
                self._world.user_monitor.report_stop(
                        self.name,
                        self.scenario['name'],
                        task['name'],
                        self.taskid)
                mainLogger.debug("task processing completed")
            else:
                mainLogger.debug(f"wait after task for {task['duration']}")
                yield self._world.env.timeout(task['duration'])
                mainLogger.debug("wait after task completed")

            if 'wait' in task:
                mainLogger.debug(f"manual task for {task['wait']}")
                yield self._world.env.timeout(task['wait'])
                mainLogger.debug("manual task completed")

            # increment counter
            counter += 1

    def process_task(self, duration, amount):
        mainLogger.debug("entering process task at %d" % self._world.env.now)
        with Job(self._world.res, amount) as req:
            yield req
            yield self._world.env.timeout(duration)
        mainLogger.debug("exiting process task at %d" % self._world.env.now)


class Clock:
    def __init__(self):
        self.base_epoch = datetime.datetime.now().timestamp()
        mainLogger.info(f"Clock created - base {self.base_epoch}")

    def to_date(self, tick):
        epoch_time = self.base_epoch + tick*60  # mn
        datetime_time = datetime.datetime.fromtimestamp(epoch_time)
        return datetime_time


class UsersMonitor:
    def __init__(self, world):
        self._world = world
        # init parameters are self reported
        # start and stop events
        self.start_data = []
        self.stop_data = []
        # list of users
        self.users = []

    def report_new_user(self, user):
        self.users.append(user)

    def report_start(self, username, scenarioname, taskname, taskid):
        mark = self._world.env.now
        self.start_data.append(
            dict(
                StartMark=mark,
                Start=self._world.clock.to_date(mark),
                Username=username,
                Scenario=scenarioname,
                Task=taskname,
                TaskId=taskid
            )
        )

    def report_stop(self, username, scenarioname, taskname, taskid):
        mark = self._world.env.now
        self.stop_data.append(
            dict(
                FinishMark=mark,
                Finish=self._world.clock.to_date(mark),
                Username=username,
                Scenario=scenarioname,
                Task=taskname,
                TaskId=taskid
            )
        )

    def collect(self):
        df_start = pd.DataFrame(self.start_data)
        df_stop = pd.DataFrame(self.stop_data)
        df = pd.merge(df_start, df_stop, how='left',
                      on=['Username', 'Scenario', 'Task', 'TaskId'])
        df['Duration'] = df['FinishMark'] - df['StartMark']
        return df


# wake up every tick and collect
class UsersGenerator:
    def __init__(self, world, max_nb_users=10, rampup_batch_size=1):
        self._world = world
        self._max_nb_users = max_nb_users
        self._rampup_batch_size = rampup_batch_size
        mainLogger.info("creating user generator for %s users", self._max_nb_users)
        self.data = []
        self.active_users = []
        self.user_count = 0
        # this will be used as a process
        self.action = world.env.process(self.run())

    def run(self):
        while True:

            if self.user_count < self._max_nb_users:
                for counter in range(1, self._rampup_batch_size):  # batch size
                    self.create_user()

                self.create_user()

            self.report()

            tick_duration = 1
            yield self._world.env.timeout(tick_duration)

    def create_user(self):

        i_scenario_index = self.user_count % len(self._world.scenarios_index)
        i_scenario = self._world.scenarios_index[i_scenario_index]
        scenario = self._world.scenarios[i_scenario]

        # first user is labelled -001
        self.user_count += 1
        user = User(self.user_count,
                    scenario,
                    self._world)
        self.active_users.append(user)
        mark = self._world.env.now
        mainLogger.debug(f"{len(self.active_users)} active users at %d" % mark)

    def report(self):
        mark = self._world.env.now
        active_users_count = len(self.active_users)

        self.data.append(
            dict(
                Mark=mark,
                Timestamp=self._world.clock.to_date(mark),
                Metric=Metric.AU.value,
                Value=active_users_count
            )
        )

    def collect(self):
        return pd.DataFrame(self.data)


# In[13]:


class Job:
    def __init__(self, res, items=1):
        self.res = res
        self.items = items
        mainLogger.debug(f"creating job with amount {self.items}")

    def __enter__(self):
        mainLogger.debug("__enter__")
        return self.res.get(self.items).__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        mainLogger.debug("__exit__")
        mainLogger.debug("exc_type {exc_type} exc_val {exc_val} exc_tb {exc_tb}")
        self.res.put(self.items).__exit__(exc_type, exc_val, exc_tb)


class SystemResource(simpy.resources.container.Container):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mainLogger.info(f"create resource with capacity {self.capacity}")
        self.processing_data = []
        self.waiting_data = []
        mainLogger.info(f"initial level {self.level}")

    def get(self, *args, **kwargs):
        amount = args[0]
        mainLogger.debug(f"received request resource - amount {amount} at %d" % self._env.now)
        mainLogger.debug(f"level (available) {self.level} at %d" % self._env.now)
        mainLogger.debug(f"{len(self.get_queue)} waiting at %d" % self._env.now)
        mainLogger.debug(f"{self.used()} processing at %d" % self._env.now)
        self.processing_data.append((self._env.now, self.used()))
        self.waiting_data.append((self._env.now, len(self.get_queue)))
        return super().get(*args, **kwargs)

    def put(self, *args, **kwargs):
        amount = args[0]
        mainLogger.debug(f"received release resource - amount {amount} at %d" % self._env.now)
        mainLogger.debug(f"level (available) {self.level} at %d" % self._env.now)
        mainLogger.debug(f"{len(self.get_queue)} waiting at %d" % self._env.now)
        mainLogger.debug(f"{self.used()} processing at %d" % self._env.now)
        self.processing_data.append((self._env.now, self.used()))
        self.waiting_data.append((self._env.now, len(self.get_queue)))
        return super().put(*args, **kwargs)

    def used(self):
        return self.capacity - self.level


class SystemResource_old(simpy.Resource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mainLogger.info(f"create resource with capacity {self.capacity}")

    def request(self, *args, **kwargs):
        mainLogger.debug("request resource at %d" % self._env.now)
        return super().request(*args, **kwargs)

    def release(self, *args, **kwargs):
        mainLogger.debug("release resource at %d" % self._env.now)
        return super().release(*args, **kwargs)


# wake up every tick and collect
class SystemMonitoringAgent:
    def __init__(self, world):
        self._world = world
        mainLogger.info("creating agent")
        self.data = []
        # this will be used as a process
        self.action = world.env.process(self.run())

    def run(self):
        while True:

            mark = self._world.env.now
            occupied_slots = self._world.res.used()
            requests_waiting = len(self._world.res.get_queue)

            mainLogger.debug(f"level {self._world.res.level} at %d" % mark)
            mainLogger.debug(f"{occupied_slots} occupied slots at %d" % mark)
            mainLogger.debug(f"{requests_waiting} requests waiting at %d" % mark)

            self.data.append(
                dict(
                    Mark=mark,
                    Timestamp=self._world.clock.to_date(mark),
                    Metric=Metric.BS.value,
                    Value=occupied_slots
                )
            )
            self.data.append(
                dict(
                    Mark=mark,
                    Timestamp=self._world.clock.to_date(mark),
                    Metric=Metric.RW.value,
                    Value=requests_waiting
                )
            )

            tick_duration = 1
            yield self._world.env.timeout(tick_duration)

    def collect(self):
        return pd.DataFrame(self.data)


class World:
    def __init__(self,
                 session_configuration,
                 nb_users=20,
                 resource_capacity=5,
                 rampup_batch_size=1):
        mainLogger.info("creating simulation")
        self.load_scenarios(session_configuration)

        self.env = simpy.Environment()
        self.clock = Clock()
        self.res = SystemResource(self.env,
                                  init=resource_capacity,
                                  capacity=resource_capacity)
        self.user_monitor = UsersMonitor(self)
        self.user_gen = UsersGenerator(self,
                                       max_nb_users=nb_users,
                                       rampup_batch_size=rampup_batch_size)
        self.res_agent = SystemMonitoringAgent(self)

    # new
    def load_scenarios(self, session_configuration):
        yaml = YAML(typ='safe')   # default, if not specfied, is 'rt' (round-trip)
        session = yaml.load(session_configuration)
        self.session_name = session['session']['name']
        mainLogger.info(f"session name: {self.session_name}")

        self.scenarios = session['session']['scenarios']
        self.scenarios_index = []
        for i in range(len(self.scenarios)):
            weight = self.scenarios[i]['weight']
            self.scenarios_index.extend(repeat(i, weight))
        # randomize index
        random.shuffle(self.scenarios_index)
        mainLogger.info(f"scenarios_index: {self.scenarios_index}")

    def start(self, sim_duration=20):
        mainLogger.info("starting simulation")
        self.env.run(until=sim_duration)
