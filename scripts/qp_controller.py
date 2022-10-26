import math

import numpy as np
import matplotlib.pyplot as plt
import cvxopt as cvx
from visualize_mobile_robot import sim_mobile_robot


# Constants and Settings
Ts = 0.1 # Update simulation
t_max = 30 # total simulation duration in seconds

# Define Field size for plotting (should be in tuple)
field_x = (-3.0, 3.0)
field_y = (-3.0, 3.0)

# general stuff
IS_SHOWING_2DVISUALIZATION = True
OBSTACLE_RADIUS = 0.3
RSI = 0.51              # Rsi for obstacles
RSI2 = math.pow(RSI, 2)  # Rsi²
ROBOT_RADIUS = 0.21

# Maximum velocity of robot
MAX_VELOCITY = 0.5          # m/s
MAX_ANGULAR_VELOCITY = 5.0  # rad/s
OBSTACLE_1 = np.array([1.25, .7])       # obstacle [x,y] 

# MAIN SIMULATION COMPUTATION
#---------------------------------------------------------------------
def simulate_control():
    sim_iter = round(t_max/Ts) # Total Step for simulation

    # Initialize robot's state (Single Integrator)
    robot_state = np.array([0., 0., 0.])  # px, py, theta

    # Values below change based on the inputs to simulate robot movement
    desired_state = np.array([2.0, 2.0, 0.]) # [px, py, theta]
    obstacle_state = np.array([1.25, .7])     # [x, y]
    current_input = np.array([0., 0., 0.]) # [vx, vy, omega]

    if IS_SHOWING_2DVISUALIZATION: # Initialize Plot
        sim_visualizer = sim_mobile_robot( 'omnidirectional' ) # Omnidirectional Icon
        sim_visualizer.set_field(field_x, field_y) # set plot area
        sim_visualizer.show_goal(desired_state)
        sim_visualizer.show_obstacle(obstacle_state, OBSTACLE_RADIUS, RSI)
        
    for it in range(sim_iter):
        # Go to goal controller 
        k = 0.1
        u_gtg = k * ( desired_state - robot_state )

        # TODO: QP-BASED controller
        #  Use only the x and y values
        # https://courses.csail.mit.edu/6.867/wiki/images/a/a7/Qp-cvxopt.pdf

        # 2 x 2
        Q = cvx.matrix( np.array([[2, 0], [0,2]]), tc="d") # P
        # 2 x 1
        c = -2 * cvx.matrix( np.array([u_gtg[0], u_gtg[1]]), tc="d") # q

        # Fill H and b based on specs - First parameter in array definition is number of constraints / specification
        # n x 2 where row is respect to ux,uy in form: H * u <= b ->  dh/dX * u <= b (NOTE: x != X due to similarity)
        H = cvx.matrix(
            np.array([[ -2 * robot_state[0] - obstacle_state[0], -2 * robot_state[1] - obstacle_state[1] ]]), tc="d" ) # G

        # Constraints which are used with gamma function to determine how much is u_gtg is altered from the original
        ho1 = np.matmul(np.transpose(robot_state[:2] - obstacle_state), robot_state[:2] - obstacle_state) - RSI2

        gamma_1 = 0.2 * ho1
        #gamma_1 = 10 * ho1
        #gamma_1 = 10 * math.pow(ho1, 3)

        # 1 x 1
        # Resize the h and b into matrices to do optimization
        b = cvx.matrix(np.array([gamma_1]), tc="d") # h

        # Solve the optimization problem
        cvx.solvers.options["show_progress"] = False
        solution = cvx.solvers.qp(Q, c, H, b, verbose=False)
        current_input = np.array([solution['x'][0], solution['x'][1], 0])

        # Limit the velocity to max if necessary
        velocity = np.linalg.norm(current_input[:2])
        if velocity > MAX_VELOCITY:
            # Scale to unit vector by dividing by vectors length and scale to max speed
            current_input[:2] = current_input[:2] / velocity * MAX_VELOCITY


        if IS_SHOWING_2DVISUALIZATION: # Update Plot
            sim_visualizer.update_time_stamp( it*Ts )
            sim_visualizer.update_goal( desired_state )
            sim_visualizer.update_obstacle( obstacle_state, OBSTACLE_RADIUS, RSI )

        #--------------------------------------------------------------------------------
        # Update new state of the obstacle / goal
        obstacle_state = obstacle_state - Ts * current_input[:2] # will be used in the next iteration
        desired_state = desired_state - Ts * current_input

if __name__ == '__main__':
    simulate_control()
