#!/usr/bin/env python

# BSD 3-Clause License; see https://github.com/scikit-hep/uproot/blob/master/LICENSE

import numba

class AwkwardType(numba.types.Type):
    pass

class JaggedArrayType(AwkwardType):
    pass
