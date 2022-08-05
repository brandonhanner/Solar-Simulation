import pandas as pd
import matplotlib.pyplot as plt

import solar_lib

#define your consumption
consumption = [  # old construction large
    5.73144,  # 0-1
    3.99126,  # 1-2
    4.14622,  # 2-3
    3.86373,  # 3-4
    3.4606,  # 4-5
    2.84037,  # 5-6
    1.74005,  # 6-7
    1.43156,  # 7-8
    2.93826,  # 8-9
    2.12459,  # 9-10
    1.15414,  # 10-11
    1.9591,  # 11-12
    3.76012,  # 12-1
    5.97077,  # 1-2
    6.57592,  # 2-3
    7.85603,  # 3-4
    7.97576,  # 4-5
    8.05428,  # 5-6
    8.37083,  # 6-7
    8.31181,  # 7-8
    7.70328,  # 8=9
    7.3307,  # 9-10
    7.31016,  # 10-11
    7.04873,  # 11-12
]

#define our system
electric_cost = .15 #cost per kWh in dollars
array_pow = 18 #solar system size in kW

#define a solar array with: array_pow kW output, 15deg tilt from horizontal, facing 180deg from north (south)
south_array = solar_lib.array_factory(
    "South Array", tilt=15, azimuth=180, panel_pow=370, array_pow=array_pow
)
#define our system
system = solar_lib.SimpleSystem(
    name="Home",
    arrays=[south_array],
    inverter_power=20000, #watts
    lat=32.856388,
    lon=-97.241586,
    alt=160,
    timezone="America/Chicago",
    consumption=consumption,
    times=pd.date_range(
        "2022-07-19 00:00", "2022-07-19 23:59", freq="1h", tz="America/Chicago"
    ),
)

#run the model
system.update_weather()
system.run_model()

#calculate some stats
zero_feed = system.calculate_zero_feed() #zero feed means your system output is capped at your consumption
costs = [electric_cost * -1 * consumption for consumption in zero_feed]
consumption = [-1 * consumption for consumption in system.consumption]
ac_production = system.get_ac_production()
capped_production = [solar_lib.clamp(production, 0, -1 * consumption) for production, consumption in zip(ac_production,consumption)]

#prepare the charts
fig, axs = plt.subplots(2)
fig.suptitle(f"Solar Calculator - {array_pow}kW array")

#set up consumption charts
axs[0].set_title("Energy Flow")  # type: ignore
axs[0].set_ylabel('kWh')
axs[0].set_xlabel("date")
axs[0].bar(system.times, capped_production, label="Usable Production", width=.03, color='blue') # type: ignore
axs[0].bar(system.times, zero_feed, label="Net Consumption w/ Zero Feed", width=.03, color='red')  # type: ignore
axs[0].bar(system.times, consumption, label="Consumption", width=.02, color='black')  # type: ignore
axs[0].bar(system.times, ac_production, label="Unbound Production", width=.02, color='orange')  # type: ignore
axs[0].legend()  # type: ignore

# size_battery = 50  # kWh
# soc_at_midnight = 0.50  # %charge # type:ignore
# battery_levels = system.calculate_battery_levels(soc_at_midnight, size_battery)

# axs[1].set_title("Battery")
# axs[1].plot(system.times, battery_levels, label="Battery kWh levels") 

#set up info table
table = [
    ["Total Energy Consumption Per Day", f"{-1 * sum(consumption):.2f}"],
    ["Total Energy Consumption Per Month", f"{-1 * sum(consumption) * 30:.2f}"],

    ["Total Net Energy Consumed Per Day", f"{-1 * sum(zero_feed):.2f} kWh" ],
    ["Total Net Energy Consumed Per Month", f"{(-1 * sum(zero_feed) * 30):.2f} kWh"],

    ["Total kWh Saved Per Day", f"{sum(capped_production):.2f} kWh"],
    ["Total kWh Saved Per Month", f"{(sum(capped_production) * 30):.2f} kWh"],

    ["Total Net Cost Per Day", f"${sum(costs):.2f}"],
    ["Total Net Cost Per Month", f"${(sum(costs) * 30):.2f}"],

    ["Total Money Saved Per Day", f"${(sum(capped_production) * electric_cost):.2f}"],
    ["Total Money Saved Per Month", f"${(sum(capped_production) * 30 * electric_cost):.2f}"]
]
# hide axes
axs[1].axis('off')
axs[1].axis('tight')
axs[1].set_title("Info")
axs[1].table(table, loc='center')

plt.show()
