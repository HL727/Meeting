
def tempfix(*args):
    "tempfix for sqlite. python stdlib statistics is shadowed by this."
    raise NotImplementedError()

stdev = pstdev = pvariance = variance = tempfix
