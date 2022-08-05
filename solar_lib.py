from pvlib import pvsystem, modelchain, location
from typing import Union, List
from sympy import ceiling 
import pandas as pd

def clamp(n, min_val, max_val):
    return max(min(max_val, n), min_val)

def array_factory(
    name: str,
    tilt: float,
    azimuth: float,
    panel_pow: float,
    num_panels: Union[int, None] = None,
    array_pow: Union[float, None] = None,
) -> pvsystem.Array:
    """
    name: human readable name
    tilt: angle relative to horizontal that the panels will be facing towards azimuth
    azimuth: angle of panel relative to north (azimuth 0)
    panel_pow: power of a single panel being considered in watts
    num_panels: optional - numbner of panels you want in your array
    array_pow: optional - desired output of entire array in kW
    """

    #check to make sure num_panels and array_pow are mutually exclusive

    if array_pow is not None:
        num_panels = int(ceiling(array_pow * 1000 / panel_pow))

    # temperature_model_parameters from glass-glass from https://pvlib-python.readthedocs.io/en/stable/_modules/pvlib/temperature.html?highlight=deltaT#
    return pvsystem.Array(
        pvsystem.FixedMount(tilt, azimuth),
        strings=1,
        modules_per_string=num_panels,
        name=name,
        module_parameters=dict(pdc0=panel_pow, gamma_pdc=-0.0036),
        temperature_model_parameters={"a": -3.47, "b": -0.0594, "deltaT": 3},
    )


def system_factory(arrays: List[pvsystem.Array], inverter_power: float):
    return pvsystem.PVSystem(
        arrays=arrays, inverter_parameters=dict(pdc0=inverter_power)
    )


def model_factory(
    system: pvsystem.PVSystem, sys_location: location.Location
) -> modelchain.ModelChain:
    return modelchain.ModelChain(
        system, sys_location, aoi_model="physical", spectral_model="no_loss"
    )

class SimpleSystem(object):
    def __init__(self,name: str, arrays: List[pvsystem.Array], inverter_power: float, lat: float, lon: float, alt: float, timezone: str, consumption: List[float], times:pd.DatetimeIndex):
        self.system = system_factory(arrays=arrays, inverter_power=inverter_power)
        self.location = location.Location(lat, lon, timezone, alt)
        self.model = model_factory(self.system, self.location)
        self.consumption = consumption
        self.times = times
        self.weather = None
        #dc
        self.dc_output = None
        self.dc_output_kw = None
        #ac
        self.ac_output = None
        self.ac_output_kw = None
        #net
        self.net_energy_produced = None

        self.timestep = self.times.freq.nanos/3600000000000

        self.dirty = True

    def update_weather(self):
        self.weather = self.location.get_clearsky(self.times)
        self.dirty = True

    def run_model(self):
        if self.weather is None:
            raise Exception("the system needs weather data.")
        self.model.run_model(self.weather)
        self.dc_output = self.model.results.dc
        self.dc_output_kw = [dc / 1000 for dc in self.dc_output]  # type:ignore

        self.ac_output = self.model.results.ac
        self.ac_output_kw = [ac / 1000 for ac in self.ac_output]  # type:ignore

        self.ac_production = self.calculate_ac_production(self.ac_output_kw)

        self.net_energy_produced = [produced - consumed for produced, consumed in zip(self.ac_production, self.consumption)]  # type: ignore

        self.dirty = False

    def get_ac_output(self):
        if self.ac_output_kw is None:
            self.run_model()
        return self.ac_output_kw

    def get_dc_output(self):
        if self.dc_output_kw is None:
            self.run_model()
        return self.dc_output_kw

    def get_net_energy_produced(self):
        if self.net_energy_produced is None:
            self.run_model()
        return self.net_energy_produced

    def get_ac_production(self):
        if self.ac_production is None:
            self.run_model()
        return self.ac_production

    def calculate_ac_production(self, ac_output):
        production = []
        for i, val in enumerate(ac_output):
            if i!=0:
                output_kw =  ((1) * self.timestep) * (1/2) * (val + ac_output[i-1])
                production.append(output_kw)
        production.insert(0, 0.0)
        return production

    def calculate_zero_feed(self):
        if self.net_energy_produced is None:
            self.run_model()
        return [clamp(production, float('-inf'),0) for production in self.net_energy_produced] #type: ignore

    def calculate_battery_levels(self, initial_soc, capacity_kwh):
        starting_energy = capacity_kwh * initial_soc
        remaining_energy = []
        for i, production in enumerate(self.net_energy_produced): #type: ignore
            if i == 0:
                new_energy = starting_energy + self.net_energy_produced[i] #type: ignore
            else:
                new_energy = remaining_energy[i - 1] + self.net_energy_produced[i] #type: ignore

            new_energy = clamp(new_energy, 0, capacity_kwh)
            remaining_energy.append(new_energy)

        #remaining_energy.insert(0, starting_energy)

        return remaining_energy

    def total_energy(self, vals, timestep):
        '''
        the trapezoidal rule for integration is as follows:
        (b-a)*(1/2)*(f(a) + f(b))
        a and b will be the "x" values on our graph
        f(a) and f(b) will be the y values

        we will provide the entire list of values, as well as the
        timestep between values to get the area of each time step.
        '''
        total = 0
        for i, val in enumerate(vals):
            if i!=0:
                output_kw =  ((1) * timestep) * (1/2) * (val + vals[i-1])
                total += output_kw
        return total

