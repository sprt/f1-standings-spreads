import collections
import copy
import operator

import requests


def object_hook(d: dict):
    if d.get('Driver'):
        d['Driver'] = Driver.from_json(d['Driver'])
    elif d.get('DriverStandings'):
        standings = DriverStandings()
        for s in d['DriverStandings']:
            standings.append(DriverStanding.from_json(s))
        d['DriverStandings'] = standings
    return d


class Driver:
    def __init__(self, *, id, code, lastname):
        self.id = id
        self.code = code
        self.lastname = lastname

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return self.code

    @classmethod
    def from_json(cls, d):
        return cls(id=d['driverId'], code=d['code'], lastname=d['familyName'])


class DriverStanding:
    def __init__(self, *, driver, points):
        self.driver = driver
        self.points = points

    def __str__(self):
        return '%s   %2d pts' % (self.driver.code, self.points)

    @classmethod
    def from_json(cls, d):
        return cls(driver=d['Driver'], points=int(d['points']))


class DriverStandings(collections.UserList):
    def __str__(self):
        s = []
        for pos, standing in enumerate(self, 1):
            s.append('%2d. %s' % (pos, standing))
        return '\n'.join(s)

    def sort_by_points(self):
        self.sort(key=operator.attrgetter('points'), reverse=True)

    def index_driver(self, driver):
        return [standing.driver for standing in self].index(driver)

    def get_driver_pos(self, driver):
        return self.index_driver(driver) + 1


class PositionSpread:
    def __init__(self, current, *, low=None, high=None):
        self.current = current
        self.low = low
        self.high = high


URL = 'http://ergast.com/api/f1/current/driverStandings.json'
r = requests.get(URL)
data = r.json(object_hook=object_hook)

standings = data['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']  # type: DriverStandings
standings.sort_by_points()

# drivers who won't race
IGNORED = ['VAN']

spreads = collections.OrderedDict()

for i, standing in enumerate(standings):
    standings_copy = copy.deepcopy(standings)  # type: DriverStandings
    temp_standings = copy.deepcopy(standings)  # type: DriverStandings

    is_ignored = standing.driver.code in IGNORED
    points = [1, 2, 4, 6, 8, 10, 12, 15, 18]

    temp_standings[i].points += 25 if not is_ignored else 0
    temp_standings.sort_by_points()
    temp_i = temp_standings.index_driver(standing.driver)

    def do_behind():
        global points
        j = len(standings_copy) - 1
        while j > i and points:
            if standings_copy[j].driver.code not in IGNORED:
                standings_copy[j].points += points.pop()
            j -= 1

    if not is_ignored:
        standings_copy[i].points += 25
        do_behind()

    j = 0
    while j < temp_i and points:
        if standings_copy[j].driver.code not in IGNORED:
            standings_copy[j].points += points.pop()
        j += 1

    if is_ignored:
        do_behind()

    j = i - 1
    while j >= temp_i and points:
        if standings_copy[j].driver.code not in IGNORED:
            standings_copy[j].points += points.pop()
        j -= 1

    standings_copy.sort_by_points()
    high_pos = standings_copy.get_driver_pos(standing.driver)
    spreads[standing.driver] = PositionSpread(i + 1, high=high_pos)

for i, standing in enumerate(standings):
    standings_copy = copy.deepcopy(standings)  # type: DriverStandings
    points = [1, 2, 4, 6, 8, 10, 12, 15, 18, 25]

    j = i + 1
    while j < len(standings_copy) and points:
        if standings_copy[j].driver.code not in IGNORED:
            standings_copy[j].points += points.pop()
        j += 1

    standings_copy.sort_by_points()
    low_pos = standings_copy.get_driver_pos(standing.driver)
    spreads[standing.driver].low = low_pos

for driver, spread in spreads.items():
    print('%2d. %s %2d %2d' % (spread.current, driver.code, spread.high, spread.low))
