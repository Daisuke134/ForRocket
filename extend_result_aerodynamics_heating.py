import sys
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import interpolate

import Simulator.environment as env

# =====↓↓↓↓ USER INPUT ↓↓↓↓====
T_surface_init = 298.15  # Initial Surface Temperature [K]
R_nosetip = 0.0086  # Blunt Radius Tip [m]
thickness = 0.002  # Thickness Tip [m]
rho_nosetip = 1270.0  # Material Dencity [kg/m^3]
c = 1592.0  # Material Specific Heat [J/kg-K]
epsilon = 0.8  # Matrial Surface Emissivity
T_ablation = 600.0  # Ablation Temperature [K]
h_vaporization = 9288.48  # Vaporization Heat [kJ/kg]
# =====↑↑↑↑ USER INPUT ↑↑↑↑====

# config file arg
argv = sys.argv
if len(argv) < 3:
    print('Error!! argument is missing')
    print('Usage: python extend_result_aerodynamics_heating.py configFileName.json ResultDirectory')
    sys.exit()   
if '.json' in argv[1]: 
    config_file = argv[1]
    result_dir = argv[2]
elif '.json' in argv[2]:
    config_file = argv[2]
    result_dir = argv[1]


class NoseCone:
    def __init__(self):
        self.T_surface_init = 15.0 + 273.15  # [K] initial temperature
        self.R_nosetip = 0.2  # [m] blunt radius
        self.thickness = 0.03  # [m] thickness at stagnation point
        self.rho = 1270.0  # [kg/m^3] material density
        self.c = 1592.0  # [J/kg-K] specific heat
        self.epsilon = 0.8  # [-] surface emissivity

        self.T_ablation = 300.0 + 273.15  # [K] abation temperature
        self.h_vaporization = 9288.48 * 1000.0  # [J/kg] vaporization heat

class FlightHeating:
    '''
    Calculate the object surface tempreture by aerodynamic heating at the time of reentry into the earth, ablation progression during ablation cooling.
    Surface Temperature Model: The sum of the heat flux given from the flow and the re-radiation heat is equal to the surface temperature.
    Ablation Model: Determine the ablation thickness so that the difference in surface temperature with respect to the set ablation temperature can be eliminaterd by vaporization heat.
    Ref.
    * 宇宙飛行体の熱気体力学
    * Heat Transfer to Satellite Vehicles Re-entering the Atomosphere
    * 超軌道速度飛行体の輻射加熱環境に関する研究
    '''
    def __init__(self, time_array, vel_array, altitude_array):
        self.time = time_array
        self.vel = vel_array
        self.altitude = altitude_array
        self.array_length = len(self.time)

    def heating(self, obj):
        Re = 6371000  #[m] earth surface
        cp = 1006.0  # [J/kg-K] specific heat at pressure constant of air
        sigma = 5.669 * 10**(-8)  # Stefan-Boltzmann constant
        g0 = env.gravity(0.0)  # [m/s^2]

        self.q_conv = np.empty(self.array_length)
        self.q_conv[0] = 0.0
        self.q_rad = np.empty(self.array_length)
        self.q_rad[0] = 0.0
        self.T_surface = np.empty(self.array_length)
        self.T_surface[0] = obj.T_surface_init
        self.thickness = np.empty(self.array_length)
        self.thickness[0] = obj.thickness

        vel_array = np.array([9.0, 9.25, 9.5, 9.75, 10.0, 10.25, 10.5, 10.75, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 14.0, 14.5, 15.0, 15.5, 16.0])
        func_array = np.array([1.5, 4.3, 9.7, 18.5, 35.0, 55.0, 81.0, 115.0, 151.0, 238.0, 359.0, 495.0, 660.0, 850.0, 1065.0, 1313.0, 1550.0, 1780.0, 2040.0])
        radiative_vel_func = interpolate.interp1d(vel_array, func_array, bounds_error = False, fill_value = (func_array[0], func_array[-1]))


        for i in range(1, self.array_length):
            dt = self.time[i] - self.time[i-1]
            rho_air = env.get_std_density(self.altitude[i])
            g = env.gravity(self.altitude[i])
            R = Re + self.altitude[i]  # [m] distance from center of earth
            uc = np.sqrt(g0 * Re**2 / Re)  # [m/s] circular velocity

            # ref. Detra-Kemp-Riddell
            self.q_conv[i] = 11030.0 / np.sqrt(obj.R_nosetip) * (rho_air / env.get_std_density(0.0))**0.5 * (np.abs(self.vel[i]) / uc)**3.05 * 10**4  # [W/m^2]
            # ref. Tauber
            def exp_n(R_nose, vel, rho):
                # input:[m, m/s, kg/m^3]
                n = 1.072 * 10.0**6 * np.abs(vel)**(-1.88) * rho**(-0.325)
                if R_nose <= 1.0:
                    return n
                elif R_nose >= 2.0:
                    return min(0.5, n)
                else:
                    return min(0.6, n)
            self.q_rad[i] = 4.736 * 10**4 * obj.R_nosetip**exp_n(obj.R_nosetip, self.vel[i], rho_air) * rho_air**1.22 * radiative_vel_func(self.vel[i]/1000.0) * 10**4  # [W/m^2]
            self.T_surface[i] = self.T_surface[i-1] + dt * (self.q_conv[i] + self.q_rad[i] - sigma * obj.epsilon * self.T_surface[i-1]**4) / (obj.c * obj.rho * obj.thickness)  # [K]
            if self.T_surface[i] < obj.T_ablation:
                self.thickness[i] = self.thickness[i-1]
            else:
                self.thickness[i] = self.thickness[i-1] - (self.T_surface[i] - obj.T_ablation) * obj.c * self.thickness[i-1] / obj.h_vaporization  # [m]
                self.T_surface[i] = obj.T_ablation


# config file to json
json = json.load(open(config_file))

heat_obj = NoseCone()
heat_obj.T_surface_init = T_surface_init
heat_obj.R_nosetip = R_nosetip
heat_obj.thickness = thickness
heat_obj.rho = rho_nosetip
heat_obj.c = c
heat_obj.epsilon = epsilon
heat_obj.T_ablation = T_ablation
heat_obj.h_vaporization = h_vaporization / 1e3

df = pd.read_csv(result_dir+'/log.csv', index_col=False)

heater = FlightHeating(df['time'], df['vel_air_abs'], df['pos_LLH_z'])
heater.heating(heat_obj)
q_conv_log = heater.q_conv
q_rad_log = heater.q_rad
q_heat_log = q_conv_log + q_rad_log
T_surface_log = heater.T_surface
thickness_log = heater.thickness

plt.figure('Aerodynamics Heating')
plt.plot(df['time'], q_conv_log / 10**6, label='convection heat')
plt.plot(df['time'], q_rad_log / 10**6, label='radiation heat')
plt.plot(df['time'], q_heat_log / 10**6, label='total heat')
plt.xlabel('Time [sec]')
plt.ylabel('q dot [MW/m^2]')
plt.xlim(left=0.0)
plt.grid()
plt.legend()
plt.savefig(result_dir + '/AerodynamicsHeating.png')

plt.figure('Surface Temperature')
plt.plot(df['time'], T_surface_log, label='Surface Temperature')
plt.xlabel('Time [sec]')
plt.ylabel('Surface Temperature [K]')
plt.xlim(left=0.0)
plt.grid()
plt.legend()
plt.savefig(result_dir + '/SurfaceTemperature.png')