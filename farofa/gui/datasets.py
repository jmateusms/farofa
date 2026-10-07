"""Published failure records offered by the GUI's estimation view.

Same values as ``examples/repairable_data_fit.py`` (a test keeps them in
sync): cumulative operating hours at each unscheduled maintenance action of
two main-propulsion diesel engines, as distributed in the data sets
``halfbeak`` and ``grampus`` of the R package SMRD (companion of Meeker and
Escobar, 1998, Statistical Methods for Reliability Data), converted from
thousands of hours to hours.
"""

HALFBEAK = [
    1382, 2990, 4124, 6827, 7472, 7567, 8845, 9450, 9794, 10848, 11993, 12300,
    15413, 16497, 17352, 17632, 18122, 19067, 19172, 19299, 19360, 19686, 19940,
    19944, 20121, 20132, 20431, 20525, 21057, 21061, 21309, 21310, 21378, 21391,
    21456, 21461, 21603, 21658, 21688, 21750, 21815, 21820, 21822, 21888, 21930,
    21943, 21946, 22181, 22311, 22634, 22635, 22669, 22691, 22846, 22947, 23149,
    23305, 23491, 23526, 23774, 23791, 23822, 24006, 24286, 25000, 25010, 25048,
    25268, 25400, 25500, 25518,
]
GRAMPUS = [
    860, 1258, 1317, 1442, 1897, 2011, 2122, 2439, 3203, 3298, 3902, 3910, 4000,
    4247, 4411, 4456, 4517, 4899, 4910, 5676, 5755, 6137, 6221, 6311, 6613, 6975,
    7335, 8158, 8498, 8690, 9042, 9330, 9394, 9426, 9872, 10191, 11511, 11575,
    12100, 12126, 12368, 12681, 12795, 13399, 13668, 13780, 13877, 14007, 14028,
    14035, 14173, 14173, 14449, 14587, 14610, 15070,
]
GRAMPUS_END = 16000.0

DATASETS = [
    {
        'key': 'halfbeak',
        'name': 'USS Halfbeak',
        'times': HALFBEAK,
        'end_time': None,
        'source': 'Ascher, H. and Feingold, H. (1984), Repairable Systems Reliability, Marcel Dekker.',
    },
    {
        'key': 'grampus',
        'name': 'USS Grampus',
        'times': GRAMPUS,
        'end_time': GRAMPUS_END,
        'source': ('Lee, L. (1980), Testing adequacy of the Weibull and log linear rate models '
                   'for a Poisson process, Technometrics 22(2), 195-199.'),
    },
]
