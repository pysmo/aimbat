from pysmo import SAC

my_sac = SAC.from_file("no_station.sac")
print(f"{my_sac.kstnm}")
my_sac.kstnm
print(f"{my_sac.station.name}")
my_sac.station.name
