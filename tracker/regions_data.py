"""The four US Census Bureau regions, used for the region cards on phones.

Source: the Census Bureau's official "Census Regions and Divisions of the
United States". Washington, D.C. (part of the South) is left out, like
everywhere else in the app.
"""

REGIONS = [
    ("Northeast", ["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"]),
    ("Midwest", ["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"]),
    ("South", ["DE", "FL", "GA", "MD", "NC", "SC", "VA", "WV",
               "AL", "KY", "MS", "TN", "AR", "LA", "OK", "TX"]),
    ("West", ["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"]),
]
