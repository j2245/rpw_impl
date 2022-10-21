#!/usr/bin/env python
import rospy
from sensor_msgs.msg import LaserScan
import tf, math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from matplotlib.animation import FuncAnimation
from sklearn.cluster import DBSCAN # LINUX pip install: pip3 install -U scikit-learn
from sklearn import metrics
import seaborn as sns
from collections import Counter

"""
THIS MAY BE DELETED LATER ON.

INFORMATION RELATED TO sensor_msgs/LaserScan Message

# Single scan from a planar laser range-finder
#
# If you have another ranging device with different behavior (e.g. a sonar
# array), please find or create a different message, since applications
# will make fairly laser-specific assumptions about this data

Header header            # timestamp in the header is the acquisition time of 
                         # the first ray in the scan.
                         #
                         # in frame frame_id, angles are measured around 
                         # the positive Z axis (counterclockwise, if Z is up)
                         # with zero angle being forward along the x axis
                         
float32 angle_min        # start angle of the scan [rad]
float32 angle_max        # end angle of the scan [rad]
float32 angle_increment  # angular distance between measurements [rad]

float32 time_increment   # time between measurements [seconds] - if your scanner
                         # is moving, this will be used in interpolating position
                         # of 3d points
float32 scan_time        # time between scans [seconds]

float32 range_min        # minimum range value [m]
float32 range_max        # maximum range value [m]

float32[] ranges         # range data [m] (Note: values < range_min or > range_max should be discarded)
float32[] intensities    # intensity data [device-specific units].  If your
                         # device does not provide intensities, please leave
                         # the array empty.
"""

# Store here so that they may used after ctrl + C in main
labels          = 0
data_points_ext = 0
objects = {}

def callback(data):
    # Global definitions if these are needed AND changed during execution
    global labels, data_points_ext

    # Get the values from the data object received
    angle_increment_rad = data.angle_increment
    angle_min = data.angle_min
    angle_max = data.angle_max
    # Values between range limits should be considered
    range_min = data.range_min
    range_max = data.range_max

    # Convert data to numpy array to insert into DBSCAN clustering algorithm
    data_points = []
    # Form (x,y) with polar -> cartesian conversion
    for index, range in enumerate(data.ranges):
        # Discard smaller / greater than the corresponding range values for the sensor
        if range < range_min or range_max < range:
            continue
        theta = angle_increment_rad * index # float as default from int * float
        data_points.append([range * math.cos(theta), range * math.sin(theta)])
    data_points_ext = np.asarray(data_points)

    # Currently just for testing purposes using a example from to visualize:
    # https://scikit-learn.org/stable/auto_examples/cluster/plot_dbscan.html
    # Minimum distance between points 
    db = DBSCAN(eps=0.5, min_samples=5).fit(data_points_ext)
    labels = db.labels_ # Non unique values (e.g. all points)

    # Calculate the amount of clusters found excluding noise!
    n_clusters_ = len(set(labels)) - (1 if -1 in labels else 0)
    # How many were labeled as -1 e.g. noise
    n_noise_ = list(labels).count(-1)
    print("Clusters found: %d" % n_clusters_)
    print("Points classified as noise: %d" % n_noise_)
    print("Silhouette Coefficient: %0.3f" % metrics.silhouette_score(data_points_ext, labels))

    clusters = points_to_clusters(data_points)
    update_objects(clusters)


def points_to_clusters(data_points):
    clusters = {}
    for pnt, label in zip(data_points,labels):
        if label == -1:
            continue
        if label in clusters:
            clusters[label].append(pnt)
        else:
            clusters[label] = [pnt]
    return clusters


def update_objects(clusters):
    global objects
    objects = {}
    for label, cluster in clusters.items():
        center = np.mean(cluster, axis=0)
        dists = np.linalg.norm(cluster-center, axis=1)
        radius = np.max(dists)
        objects[label] = (center, radius)


def detect_incoming_lidar_data():
    rospy.init_node('lidar_node', anonymous=True)
    plot = ObstaclePlot()
    scan = rospy.Subscriber("/scan", LaserScan, plot.scan_callback) # frame_id: /base_scan as in real tb3 it's tb3_1/base_scan (?)
    rospy.loginfo("Started the node")

    ani = FuncAnimation(plot.fig, plot.update_plot)#, init_func=plot.plot_init)
    plt.show(block=True) 

    # spin() simply keeps python from exiting until this node is stopped
    rospy.spin()


class ObstaclePlot:
    def __init__(self,AxisLimits=[-5,5,-5,5]):
        self.al = AxisLimits
        self.fig, self.ax = plt.subplots()
        self.ax.set_aspect('equal')
        self.ax.set_xlim(self.al[0],self.al[1])
        self.ax.set_ylim(self.al[2],self.al[3])
        self.ax.set_xlabel("X")
        self.ax.set_ylabel("Y", rotation="horizontal")
        self.ax.plot(0,0, color='gray', marker='o',markersize=10)
        self.ax.plot(0.4,0, color='gray', marker='>',markersize=4)


    def update_plot(self,frame):
        if len(objects) == 0:
            return
        self.clear_patches()

        closest_dist = 1e5
        closest_obj = Circle(0,0)
        for lbl, object in objects.items():
            r = object[1]
            dist_from_bot = np.linalg.norm(object[0])
            if r > dist_from_bot: # Inside the approximated circle (-> bad approximation)
                continue
            obj = Circle(xy=object[0], radius=r, color='red', fill=False, label=lbl)
            self.ax.add_patch(obj)
            if dist_from_bot+r < closest_dist:
                closest_dist = dist_from_bot+r
                closest_obj = obj
        
        closest_obj.set_fill(True)
        self.ax.set_title(f"Objects: {len(objects)}, closest: {closest_obj.get_label()}")
    
    def clear_patches(self):
        [p.remove() for p in reversed(self.ax.patches)]


    def scan_callback(self, data):
        callback(data)


# Main script is 
if __name__ == '__main__':
    detect_incoming_lidar_data()
    print(f'program ended by user action: CTRL + C')

    print(f"Collections of the found clusters:\n{Counter(labels)}")

    # Create scatter plot - note that cluster category -1 == noise
    plot = sns.scatterplot(data=data_points_ext, x=data_points_ext[:, 0], y=data_points_ext[:, 1], 
        hue=labels, legend="full", palette="deep")

    sns.move_legend(plot, "center right", bbox_to_anchor=(1.0, 1.0), title='Clusters')
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)

    # Display the objects as circles
    for lbl, object in objects.items():
        obj = plt.Circle(xy=object[0], radius=object[1], color='red', fill=False, label=lbl)
        plot.add_patch(obj)

    plt.title(f"Estimated number of clusters: {n_clusters}")
    plt.show()

    
    plt.show()