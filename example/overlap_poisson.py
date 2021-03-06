""" Plot overlap of dispersal units calculated with Poisson law as a function of diameter. """
import numpy
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

diameter = numpy.arange(0.,5.,0.1)
impact_surface = numpy.pi * diameter**2 / 4.0
nb_dus = numpy.logspace(0,4,50)
impact_surface, nb_du = numpy.meshgrid(impact_surface, nb_dus)
diameter, nb_du = numpy.meshgrid(diameter, nb_dus)
fraction_area_impacted = 1-numpy.exp(-nb_du * impact_surface / 1e5)
fraction_area_impacted[fraction_area_impacted>1.] = 1.

fig = plt.figure()
ax = fig.add_subplot(1, 1, 1, projection='3d')
ax.plot_surface(diameter, nb_du, fraction_area_impacted, rstride=1, cstride=1, color='b', alpha=0.5)
ax.set_xlabel("Diameter of each droplet (mm)")
ax.set_ylabel("Number of DU on leaf of 10cm2")
ax.set_zlabel("Fraction Area Impacted")
plt.show(False)