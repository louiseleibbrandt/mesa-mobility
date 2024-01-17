import random
from collections import defaultdict
from typing import DefaultDict, Dict, Optional, Set, Tuple

import mesa
import mesa_geo as mg
from shapely.geometry import Point

from src.agent.building import Building
from src.agent.commuter import Commuter

class Netherlands(mg.GeoSpace):
    buildings: Tuple[Building]
    buildings_trip: Tuple[Building]
    home_counter: DefaultDict[mesa.space.FloatCoordinate, int]
    commuters: list[Commuter]
    number_commuters: int
    _buildings: Dict[int, Building]
    _commuters_pos_map: DefaultDict[mesa.space.FloatCoordinate, Set[Commuter]]
    _commuter_id_map: Dict[int, Commuter]

    def __init__(self, crs: str) -> None:
        super().__init__(crs=crs)
        self.buildings = ()
        self.buildings_trip = ()
        self.home_counter = defaultdict(int)
        self._buildings = {}
        self._commuters_pos_map = defaultdict(set)
        self._commuter_id_map = {}
        self.commuters = []

    # def get_random_home(self) -> Building:
    #     return random.choice(self.homes)

    # def get_random_work(self) -> Building:
    #     return random.choice(self.works)
    def get_random_building(self) -> Building:
        return random.choice(self.buildings)

    def get_random_building_trip(self) -> Building:
        return random.choice(self.buildings_trip)

    def get_building_by_id(self, unique_id: int) -> Building:
        return self._buildings[unique_id]
    
    def get_nearest_building (
        self, float_pos: mesa.space.FloatCoordinate, visited_locations: list,trip: bool
    ) -> Building:
        if (trip == True):
            search = [x for x in self.buildings_trip if x not in visited_locations]
            min_building = min(search,key=lambda x:x.geometry.distance(float_pos))
        else:
            search = [x for x in self.buildings if x not in visited_locations]
            min_building = min(search,key=lambda x:x.geometry.distance(float_pos))
        return min_building



    # def add_buildings(self, agents, types) -> None:
    def add_buildings(self, agents, types) -> None:
        # super().add_agents(agents)
        buildings, buildings_trip = [], []
        for (agent,type) in zip(agents,types):
            if isinstance(agent, Building):
                self._buildings[agent.unique_id] = agent
                if  type == 0:
                    agent.function = 0
                    buildings.append(agent)
                elif type == 1:
                    agent.function = 1
                    buildings_trip.append(agent)
        self.buildings = self.buildings + tuple(buildings)
        self.buildings_trip = self.buildings_trip + tuple(buildings_trip)

    def get_commuters_by_pos(
        self, float_pos: mesa.space.FloatCoordinate
    ) -> Set[Commuter]:
        return self._commuters_pos_map[float_pos]

    def get_commuter_by_id(self, commuter_id: int) -> Commuter:
        return self._commuter_id_map[commuter_id]

    def add_commuter(self, agent: Commuter, update_idx: bool) -> None:
        if (update_idx):
            super().add_agents([agent])
        self._commuters_pos_map[(agent.geometry.x, agent.geometry.y)].add(agent)
        self._commuter_id_map[agent.unique_id] = agent

    def update_home_counter(
        self,
        old_home_pos: Optional[mesa.space.FloatCoordinate],
        new_home_pos: mesa.space.FloatCoordinate,
    ) -> None:
        if old_home_pos is not None:
            self.home_counter[old_home_pos] -= 1
        self.home_counter[new_home_pos] += 1

    def move_commuter(
        self, commuter: Commuter, pos: mesa.space.FloatCoordinate, update_idx: bool
    ) -> None:
        self.__remove_commuter(commuter,update_idx)
        commuter.geometry = Point(pos)
        self.add_commuter(commuter,update_idx)
        

    def __remove_commuter(self, commuter: Commuter,update_idx: bool) -> None:
        if (update_idx):
            super().remove_agent(commuter)
        del self._commuter_id_map[commuter.unique_id]
        self._commuters_pos_map[(commuter.geometry.x, commuter.geometry.y)].remove(
            commuter
        )
