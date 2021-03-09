#!/usr/bin/env python3
#
# Copyright (c) 2019-2021 LG Electronics, Inc.
#
# This software contains code licensed as described in LICENSE.
#

# See PLC_SN_15.py for a commented script

import time
import logging
from environs import Env
import lgsvl
FORMAT = "[%(levelname)6s] [%(name)s] %(message)s"
logging.basicConfig(level=logging.WARNING, format=FORMAT)
log = logging.getLogger(__name__)

env = Env()

MAX_SPEED = 15.556  # (56 km/h, 35mph)
SPEED_VARIANCE = 4
MAX_POV_SEPARATION = 19
SEPARATION_VARIANCE = 2
TIME_LIMIT = 30  # seconds

LGSVL__SIMULATOR_HOST = env.str("LGSVL__SIMULATOR_HOST", "127.0.0.1")
LGSVL__SIMULATOR_PORT = env.int("LGSVL__SIMULATOR_PORT", 8181)
LGSVL__AUTOPILOT_0_HOST = env.str("LGSVL__AUTOPILOT_0_HOST", "127.0.0.1")
LGSVL__AUTOPILOT_0_PORT = env.int("LGSVL__AUTOPILOT_0_PORT", 9090)

print("PLC_SN_35 - ", end='')

sim = lgsvl.Simulator(LGSVL__SIMULATOR_HOST, LGSVL__SIMULATOR_PORT)
if sim.current_scene == "Straight2LaneSame":
    sim.reset()
else:
    sim.load("Straight2LaneSame")

# spawn EGO in the 2nd to right lane
egoState = lgsvl.AgentState()
# A point close to the desired lane was found in Editor.
# This method returns the position and orientation of the closest lane to the point.
egoState.transform = sim.map_point_on_lane(lgsvl.Vector(3.68, 0, -50))
# Default vehicle for this test case is Lincoln2017MKZ - Apollo 5.0
# https://wise.svlsimulator.com/vehicles/profile/73805704-1e46-4eb6-b5f9-ec2244d5951e/edit/configuration/47b529db-0593-4908-b3e7-4b24a32a0f70
DEFAULT_VEHICLE_CONFIG = "47b529db-0593-4908-b3e7-4b24a32a0f70"
ego = sim.add_agent(env.str("LGSVL__VEHICLE_0", DEFAULT_VEHICLE_CONFIG), lgsvl.AgentType.EGO, egoState)
forward = lgsvl.utils.transform_to_forward(egoState.transform)
right = lgsvl.utils.transform_to_right(egoState.transform)

ego.connect_bridge(LGSVL__AUTOPILOT_0_HOST, LGSVL__AUTOPILOT_0_PORT)

dv = lgsvl.dreamview.Connection(sim, ego, LGSVL__AUTOPILOT_0_HOST)
dv.set_hd_map(env.str("LGSVL__AUTOPILOT_HD_MAP", 'Straight2LaneSame'))
dv.set_vehicle(env.str("LGSVL__AUTOPILOT_0_VEHICLE_CONFIG", 'Lincoln2017MKZ'))
try:
    modules = env.list("LGSVL__AUTOPILOT_0_VEHICLE_MODULES", subcast=str)
    if len(modules) == 0:
        log.warning("LGSVL__AUTOPILOT_0_VEHICLE_MODULES is empty, using default list: {0}".format(modules))
        modules = [
            'Recorder',
            'Localization',
            'Perception',
            'Transform',
            'Routing',
            'Prediction',
            'Planning',
            'Traffic Light',
            'Control'
        ]
except Exception:
    modules = [
        'Recorder',
        'Localization',
        'Perception',
        'Transform',
        'Routing',
        'Prediction',
        'Planning',
        'Traffic Light',
        'Control'
    ]
    log.warning("LGSVL__AUTOPILOT_0_VEHICLE_MODULES is not set, using default list: {0}".format(modules))

destination = egoState.position + 120 * forward + 3.6 * right
dv.setup_apollo(destination.x, destination.z, modules)

POV1State = lgsvl.AgentState()
POV1State.transform = sim.map_point_on_lane(egoState.position + 13 * forward + 3.6 * right)
POV1 = sim.add_agent("Sedan", lgsvl.AgentType.NPC, POV1State)
POV1.follow_closest_lane(True, MAX_SPEED, False)

POV2State = lgsvl.AgentState()
POV2State.transform = sim.map_point_on_lane(egoState.position + 3.6 * right)
POV2 = sim.add_agent("Sedan", lgsvl.AgentType.NPC, POV2State)
POV2.follow_closest_lane(True, MAX_SPEED, False)

POV3State = lgsvl.AgentState()
POV3State.transform = sim.map_point_on_lane(egoState.position - 13 * forward + 3.6 * right)
POV3 = sim.add_agent("Sedan", lgsvl.AgentType.NPC, POV3State)
POV3.follow_closest_lane(True, MAX_SPEED, False)


def on_collision(agent1, agent2, contact):
    raise lgsvl.evaluator.TestException("{} collided with {}".format(agent1, agent2))


ego.on_collision(on_collision)
POV1.on_collision(on_collision)
POV2.on_collision(on_collision)
POV3.on_collision(on_collision)

endOfRoad = egoState.position + 120 * forward + 3.6 * right

try:
    t0 = time.time()
    while True:
        egoCurrentState = ego.state
        if egoCurrentState.speed > MAX_SPEED + SPEED_VARIANCE:
            raise lgsvl.evaluator.TestException(
                "Ego speed exceeded limit, {} > {} m/s".format(egoCurrentState.speed, MAX_SPEED + SPEED_VARIANCE)
            )
        POV1CurrentState = POV1.state
        POV2CurrentState = POV2.state
        POV3CurrentState = POV3.state
        POVSeparation = lgsvl.evaluator.separation(POV1CurrentState.position, POV2CurrentState.position)
        if POVSeparation > MAX_POV_SEPARATION + SEPARATION_VARIANCE:
            raise lgsvl.evaluator.TestException(
                "POV1 and POV2 are too far apart: {} > {}".format(POVSeparation, MAX_POV_SEPARATION + SEPARATION_VARIANCE)
            )
        if POV1CurrentState.speed > MAX_SPEED + SPEED_VARIANCE:
            raise lgsvl.evaluator.TestException(
                "POV1 speed exceeded limit, {} > {} m/s".format(POV1CurrentState.speed, MAX_SPEED + SPEED_VARIANCE)
            )
        if POV2CurrentState.speed > MAX_SPEED + SPEED_VARIANCE:
            raise lgsvl.evaluator.TestException(
                "POV2 speed exceeded limit, {} > {} m/s".format(POV2CurrentState.speed, MAX_SPEED + SPEED_VARIANCE)
            )
        if POV3CurrentState.speed > MAX_SPEED + SPEED_VARIANCE:
            raise lgsvl.evaluator.TestException(
                "POV3 speed exceeded limit, {} > {} m/s".format(POV3CurrentState.speed, MAX_SPEED + SPEED_VARIANCE)
            )
        if lgsvl.evaluator.separation(POV1CurrentState.position, endOfRoad) < 5:
            break
        sim.run(0.5)
        if time.time() - t0 > TIME_LIMIT:
            break
except lgsvl.evaluator.TestException as e:
    exit("FAILED: {}".format(e))

finalEgoState = ego.state
try:
    if lgsvl.evaluator.right_lane_check(sim, finalEgoState.transform):
        print("PASSED")
    else:
        raise lgsvl.evaluator.TestException("Ego did not change lanes")
except lgsvl.evaluator.TestException as e:
    exit("FAILED: {}".format(e))