import uuid
from functools import partial

import geopandas as gpd
import mesa
import mesa_geo as mg
import pandas as pd
from shapely.geometry import Point

from src.agent.building import Building
from src.agent.commuter import Commuter
from src.agent.geo_agents import Driveway, LakeAndRiver, Walkway
from src.space.campus import Campus
from src.space.road_network import CampusWalkway


def get_time(model) -> pd.Timedelta:
    return pd.Timedelta(days=model.day, hours=model.hour, minutes=model.minute)


def get_num_commuters_by_status(model, status: str) -> int:
    commuters = [
        commuter for commuter in model.schedule.agents if commuter.status == status
    ]
    return len(commuters)




class AgentsAndNetworks(mesa.Model):
    running: bool
    schedule: mesa.time.RandomActivation
    show_walkway: bool
    show_lakes_and_rivers: bool
    current_id: int
    space: Campus
    walkway: CampusWalkway
    world_size: gpd.geodataframe.GeoDataFrame
    got_to_destination: int  # count the total number of arrivals
    num_commuters: int
    step_duration: int
    day: int
    hour: int
    minute: int
    datacollector: mesa.DataCollector

    def __init__(
        self,
        region: str,
        data_crs: str,
        buildings_file: str,
        walkway_file: str,
        lakes_file: str,
        rivers_file: str,
        driveway_file: str,
        num_commuters,
        step_duration,
        commuter_speed=1.0,
        model_crs="epsg:3857",
        show_walkway=False,
        show_lakes_and_rivers=False,
        show_driveway=False,
    ) -> None:
        super().__init__()
        self.schedule = mesa.time.RandomActivation(self)
        self.show_walkway = show_walkway
        self.show_lakes_and_rivers = show_lakes_and_rivers
        self.data_crs = data_crs
        self.space = Campus(crs=model_crs)
        self.num_commuters = num_commuters

        Commuter.SPEED = commuter_speed * 300.0  # meters per tick (5 minutes)

        self._load_buildings_from_file(buildings_file, crs=model_crs, region=region)
        self._load_road_vertices_from_file(walkway_file, crs=model_crs, region=region)
        self._set_building_entrance()
        self.got_to_destination = 0
        self._create_commuters()
        self.day = 0
        self.hour = 5
        self.minute = 55
        self.step_duration = step_duration
        if show_driveway:
            self._load_driveway_from_file(driveway_file, crs=model_crs)
        if show_lakes_and_rivers:
            self._load_lakes_and_rivers_from_file(lakes_file, crs=model_crs)
            self._load_lakes_and_rivers_from_file(rivers_file, crs=model_crs)

        self.datacollector = mesa.DataCollector(
            model_reporters={
                "time": get_time,
                "status_home": partial(get_num_commuters_by_status, status="home"),
                "status_work": partial(get_num_commuters_by_status, status="work"),
                "status_traveling": partial(
                    get_num_commuters_by_status, status="transport"
                ),
            }
        )
        self.datacollector.collect(self)

    def _create_commuters(self) -> None:
        for _ in range(self.num_commuters):
            random_home = self.space.get_random_home()
            random_work = self.space.get_random_work()
            commuter = Commuter(
                unique_id=uuid.uuid4().int,
                model=self,
                geometry=Point(random_home.centroid),
                crs=self.space.crs,
            )
            commuter.set_home(random_home)
            commuter.set_work(random_work)
            commuter.status = "home"
            self.space.add_commuter(commuter)
            self.schedule.add(commuter)

    def _load_buildings_from_file(
        self, buildings_file: str, crs: str, region: str
    ) -> None:

        buildings_df = gpd.read_file(buildings_file)
        buildings_df.index.name = "unique_id"
        buildings_df = buildings_df.set_crs(self.data_crs, allow_override=True).to_crs(
            crs
        )
        buildings_df["centroid"] = [
            (x, y) for x, y in zip(buildings_df.centroid.x, buildings_df.centroid.y)
        ]
        building_creator = mg.AgentCreator(Building, model=self)
        buildings = building_creator.from_GeoDataFrame(buildings_df)
        self.space.add_buildings(buildings)

    def _load_road_vertices_from_file(
        self, walkway_file: str, crs: str, region: str
    ) -> None:
        walkway_df = (
            gpd.read_file(walkway_file)
            .set_crs(self.data_crs, allow_override=True)
            .to_crs(crs)
        )
        self.walkway = CampusWalkway(region=region, lines=walkway_df["geometry"])
        if self.show_walkway:
            walkway_creator = mg.AgentCreator(Walkway, model=self)
            walkway = walkway_creator.from_GeoDataFrame(walkway_df)
            self.space.add_agents(walkway)

    def _load_driveway_from_file(self, driveway_file: str, crs: str) -> None:
        driveway_df = (
            gpd.read_file(driveway_file)
            .set_index("osm_id")
            #.set_index("Id")
            .set_crs(self.data_crs, allow_override=True)
            .to_crs(crs)
        )
        driveway_creator = mg.AgentCreator(Driveway, model=self)
        driveway = driveway_creator.from_GeoDataFrame(driveway_df)
        self.space.add_agents(driveway)

    def _load_lakes_and_rivers_from_file(self, lake_river_file: str, crs: str) -> None:
        lake_river_df = (
            gpd.read_file(lake_river_file)
            .set_crs(self.data_crs, allow_override=True)
            .to_crs(crs)
        )
        lake_river_df.index.names = ["Id"]
        lake_river_creator = mg.AgentCreator(LakeAndRiver, model=self)
        gmu_lake_river = lake_river_creator.from_GeoDataFrame(lake_river_df)
        self.space.add_agents(gmu_lake_river)

    def _set_building_entrance(self) -> None:
        for building in (
            *self.space.homes,
            *self.space.works,
            *self.space.other_buildings,
        ):
            building.entrance_pos = self.walkway.get_nearest_node(building.centroid)

    def step(self) -> None:
        self.__update_clock()
        self.schedule.step()
        self.datacollector.collect(self)

    def __update_clock(self) -> None:
        self.minute += self.step_duration
        print(self.step_duration)
        if self.minute == 60:
            if self.hour == 23:
                self.hour = 0
                self.day += 1
            else:
                self.hour += 1
            self.minute = 0