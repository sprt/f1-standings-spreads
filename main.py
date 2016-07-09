import collections
import copy
import functools
import operator

import requests


def standings_object_hook(d: dict):
    if d.get('Driver'):
        d['Driver'] = Driver.from_json(d['Driver'])
    elif d.get('DriverStandings'):
        standings = DriverStandings()
        for s in d['DriverStandings']:
            standings.append(DriverStanding.from_json(s))
        d['DriverStandings'] = standings
    return d


def results_object_hook(d: dict):
    if d.get('Driver'):
        d['Driver'] = Driver.from_json(d['Driver'])
    elif d.get('Results'):
        results = []
        for res in d['Results']:
            try:
                int(res['positionText'])
            except ValueError:
                continue
            results.append(RaceResult.from_json(res))
        d['Results'] = results
    return d


class Driver:
    def __init__(self, *, id, code, lastname):
        self.id = id
        self.code = code
        self.lastname = lastname
        self.finishes = {}

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return self.code

    @classmethod
    def from_json(cls, d):
        return cls(id=d['driverId'], code=d['code'], lastname=d['familyName'])


@functools.total_ordering
class DriverStanding:
    def __init__(self, *, driver, points):
        self.driver = driver
        self.points = points

    def __lt__(self, other):
        if self.points != other.points:
            return self.points < other.points
        for pos, count in self.driver.finishes.items():
            if count != other.driver.finishes[pos]:
                return count < other.driver.finishes[pos]
        return False

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
        self.sort(reverse=True)

    def index_driver(self, driver):
        return [standing.driver for standing in self].index(driver)

    def get_driver_pos(self, driver):
        return self.index_driver(driver) + 1


class PositionSpread:
    def __init__(self, current, *, low=None, high=None):
        self.current = current
        self.low = low
        self.high = high


class RaceResult:
    def __init__(self, *, driver, position):
        self.driver = driver
        self.position = position

    @classmethod
    def from_json(cls, d):
        return cls(driver=d['Driver'], position=int(d['position']))


STANDINGS_URL = 'http://ergast.com/api/f1/current/driverStandings.json'
RESULTS_URL = 'http://ergast.com/api/f1/current/results.json'

standings_resp = requests.get(STANDINGS_URL)
standings_data = standings_resp.json(object_hook=standings_object_hook)

results_resp = requests.get(RESULTS_URL, params={'limit': 1000})
results_data = results_resp.json(object_hook=results_object_hook)

standings = standings_data['MRData']['StandingsTable']['StandingsLists'][0]['DriverStandings']  # type: DriverStandings
standings.sort_by_points()

race_results = []
for race in results_data['MRData']['RaceTable']['Races']:
    race_results.extend(race['Results'])

# drivers who won't race
IGNORED = ['VAN']

for i, standing in enumerate(standings):
    for i in range(1, len(standings) - len(IGNORED) + 1):
        standing.driver.finishes[i] = 0
    for result in race_results:
        if standing.driver == result.driver:
            standing.driver.finishes[result.position] += 1
    standings[i].driver.finishes = collections.OrderedDict(sorted(standing.driver.finishes.items()))

spreads = collections.OrderedDict()

for i, standing in enumerate(standings):
    standings_copy = copy.deepcopy(standings)  # type: DriverStandings
    temp_standings = copy.deepcopy(standings)  # type: DriverStandings

    is_ignored = standing.driver.code in IGNORED
    points = [1, 2, 4, 6, 8, 10, 12, 15, 18]
    pos = 2

    temp_standings[i].points += 25 if not is_ignored else 0
    temp_standings[i].driver.finishes[1] += 1
    temp_standings.sort_by_points()
    temp_i = temp_standings.index_driver(standing.driver)

    def do_behind():
        global points, pos
        j = len(standings_copy) - 1
        while j > i and points:
            if standings_copy[j].driver.code not in IGNORED:
                standings_copy[j].points += points.pop()
                standings_copy[j].driver.finishes[pos] += 1
                pos += 1
            j -= 1

    if not is_ignored:
        standings_copy[i].points += 25
        standings_copy[i].driver.finishes[1] += 1
        do_behind()

    j = 0
    while j < temp_i and points:
        if standings_copy[j].driver.code not in IGNORED:
            standings_copy[j].points += points.pop()
            standings_copy[j].driver.finishes[pos] += 1
            pos += 1
        j += 1

    if is_ignored:
        do_behind()

    j = i - 1
    while j >= temp_i and points:
        if standings_copy[j].driver.code not in IGNORED:
            standings_copy[j].points += points.pop()
            standings_copy[j].driver.finishes[pos] += 1
            pos += 1
        j -= 1

    standings_copy.sort_by_points()
    high_pos = standings_copy.get_driver_pos(standing.driver)
    spreads[standing.driver] = PositionSpread(i + 1, high=high_pos)

for i, standing in enumerate(standings):
    standings_copy = copy.deepcopy(standings)  # type: DriverStandings
    points = {1: 25, 2: 18, 3: 15, 4: 12, 5: 10, 6: 8, 7: 6, 8: 4, 9: 2, 10: 1}

    last_pos = len(standings) - len(IGNORED)
    standings_copy[i].driver.finishes.setdefault(last_pos, 0)
    standings_copy[i].driver.finishes[last_pos] += 1

    j = len(standings) - 1
    while j > i and points:
        if standings_copy[j].driver.code not in IGNORED:
            for k, score in points.items():
                standings_copy2 = copy.deepcopy(standings_copy)
                standings_copy2[j].points += score
                standings_copy2[j].driver.finishes.setdefault(k, 0)
                standings_copy2[j].driver.finishes[k] += 1

                if standings_copy[i] < standings_copy2[j]:
                    standings_copy[j] = copy.deepcopy(standings_copy2[j])
                    points.pop(k)
                    break
        j -= 1

    standings_copy.sort_by_points()
    low_pos = standings_copy.get_driver_pos(standing.driver)
    spreads[standing.driver].low = low_pos

for driver, spread in spreads.items():
    print('%2d. %s %2d %2d' % (spread.current, driver.code, spread.high, spread.low))
