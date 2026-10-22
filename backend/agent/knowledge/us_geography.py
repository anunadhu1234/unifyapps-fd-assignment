"""US geography reference data.

Shared by the data generator (where customers and employees live) and the
knowledge-graph builder (mapping "California" -> 'CA', "the Northeast" -> a
list of state codes). Keeping one source means the agent's value grounding can
never disagree with what was actually generated.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    code: str
    name: str
    region: str  # US Census Bureau region
    population_m: float  # approximate, used only as a sampling weight
    cities: tuple[str, ...]
    aliases: tuple[str, ...] = ()


STATES: tuple[State, ...] = (
    State("AL", "Alabama", "South", 5.1, ("Birmingham", "Montgomery", "Huntsville")),
    State("AK", "Alaska", "West", 0.7, ("Anchorage", "Fairbanks")),
    State("AZ", "Arizona", "West", 7.4, ("Phoenix", "Tucson", "Mesa", "Scottsdale")),
    State("AR", "Arkansas", "South", 3.1, ("Little Rock", "Fayetteville")),
    State("CA", "California", "West", 39.0,
          ("Los Angeles", "San Francisco", "San Diego", "San Jose", "Sacramento", "Oakland", "Irvine"),
          ("cali",)),
    State("CO", "Colorado", "West", 5.9, ("Denver", "Colorado Springs", "Boulder", "Aurora")),
    State("CT", "Connecticut", "Northeast", 3.6, ("Hartford", "New Haven", "Stamford")),
    State("DE", "Delaware", "South", 1.0, ("Wilmington", "Dover")),
    State("DC", "District of Columbia", "South", 0.7, ("Washington",), ("washington dc", "washington d.c.")),
    State("FL", "Florida", "South", 22.6, ("Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale")),
    State("GA", "Georgia", "South", 11.0, ("Atlanta", "Savannah", "Augusta")),
    State("HI", "Hawaii", "West", 1.4, ("Honolulu", "Hilo")),
    State("ID", "Idaho", "West", 1.9, ("Boise", "Idaho Falls")),
    State("IL", "Illinois", "Midwest", 12.5, ("Chicago", "Naperville", "Springfield", "Peoria")),
    State("IN", "Indiana", "Midwest", 6.8, ("Indianapolis", "Fort Wayne", "Bloomington")),
    State("IA", "Iowa", "Midwest", 3.2, ("Des Moines", "Cedar Rapids")),
    State("KS", "Kansas", "Midwest", 2.9, ("Wichita", "Overland Park", "Topeka")),
    State("KY", "Kentucky", "South", 4.5, ("Louisville", "Lexington")),
    State("LA", "Louisiana", "South", 4.6, ("New Orleans", "Baton Rouge")),
    State("ME", "Maine", "Northeast", 1.4, ("Portland", "Bangor")),
    State("MD", "Maryland", "South", 6.2, ("Baltimore", "Bethesda", "Annapolis")),
    State("MA", "Massachusetts", "Northeast", 7.0, ("Boston", "Cambridge", "Worcester")),
    State("MI", "Michigan", "Midwest", 10.0, ("Detroit", "Grand Rapids", "Ann Arbor")),
    State("MN", "Minnesota", "Midwest", 5.7, ("Minneapolis", "Saint Paul", "Rochester")),
    State("MS", "Mississippi", "South", 2.9, ("Jackson", "Gulfport")),
    State("MO", "Missouri", "Midwest", 6.2, ("Kansas City", "St. Louis", "Springfield")),
    State("MT", "Montana", "West", 1.1, ("Billings", "Missoula")),
    State("NE", "Nebraska", "Midwest", 2.0, ("Omaha", "Lincoln")),
    State("NV", "Nevada", "West", 3.2, ("Las Vegas", "Reno", "Henderson")),
    State("NH", "New Hampshire", "Northeast", 1.4, ("Manchester", "Nashua")),
    State("NJ", "New Jersey", "Northeast", 9.3, ("Newark", "Jersey City", "Princeton")),
    State("NM", "New Mexico", "West", 2.1, ("Albuquerque", "Santa Fe")),
    State("NY", "New York", "Northeast", 19.6, ("New York", "Brooklyn", "Buffalo", "Rochester", "Albany")),
    State("NC", "North Carolina", "South", 10.8, ("Charlotte", "Raleigh", "Durham", "Greensboro")),
    State("ND", "North Dakota", "Midwest", 0.8, ("Fargo", "Bismarck")),
    State("OH", "Ohio", "Midwest", 11.8, ("Columbus", "Cleveland", "Cincinnati")),
    State("OK", "Oklahoma", "South", 4.0, ("Oklahoma City", "Tulsa")),
    State("OR", "Oregon", "West", 4.2, ("Portland", "Eugene", "Salem")),
    State("PA", "Pennsylvania", "Northeast", 13.0, ("Philadelphia", "Pittsburgh", "Harrisburg")),
    State("RI", "Rhode Island", "Northeast", 1.1, ("Providence", "Warwick")),
    State("SC", "South Carolina", "South", 5.4, ("Charleston", "Columbia", "Greenville")),
    State("SD", "South Dakota", "Midwest", 0.9, ("Sioux Falls", "Rapid City")),
    State("TN", "Tennessee", "South", 7.1, ("Nashville", "Memphis", "Knoxville")),
    State("TX", "Texas", "South", 30.5, ("Houston", "Austin", "Dallas", "San Antonio", "Fort Worth")),
    State("UT", "Utah", "West", 3.4, ("Salt Lake City", "Provo")),
    State("VT", "Vermont", "Northeast", 0.6, ("Burlington", "Montpelier")),
    State("VA", "Virginia", "South", 8.7, ("Richmond", "Virginia Beach", "Arlington")),
    State("WA", "Washington", "West", 7.8, ("Seattle", "Spokane", "Tacoma", "Bellevue"), ("washington state",)),
    State("WV", "West Virginia", "South", 1.8, ("Charleston", "Morgantown")),
    State("WI", "Wisconsin", "Midwest", 5.9, ("Milwaukee", "Madison", "Green Bay")),
    State("WY", "Wyoming", "West", 0.6, ("Cheyenne", "Casper")),
)

STATES_BY_CODE: dict[str, State] = {s.code: s for s in STATES}

# Named groups of states users commonly refer to. Census regions are derived
# from STATES; the rest are informal but unambiguous enough to ground.
STATE_GROUPS: dict[str, tuple[str, ...]] = {
    "Northeast": tuple(s.code for s in STATES if s.region == "Northeast"),
    "Midwest": tuple(s.code for s in STATES if s.region == "Midwest"),
    "South": tuple(s.code for s in STATES if s.region == "South"),
    "West": tuple(s.code for s in STATES if s.region == "West"),
    "West Coast": ("CA", "OR", "WA"),
    "East Coast": ("ME", "NH", "MA", "RI", "CT", "NY", "NJ", "DE", "MD", "VA", "NC", "SC", "GA", "FL"),
    "Pacific Northwest": ("WA", "OR"),
    "New England": ("ME", "NH", "VT", "MA", "RI", "CT"),
}

STATE_GROUP_ALIASES: dict[str, tuple[str, ...]] = {
    "Northeast": ("north east", "northeastern"),
    "Midwest": ("mid west", "midwestern"),
    "South": ("southern states", "the south"),
    "West": ("western states", "the west"),
    "West Coast": ("west coast", "pacific coast"),
    "East Coast": ("east coast", "atlantic coast", "eastern seaboard"),
    "Pacific Northwest": ("pnw",),
    "New England": (),
}
