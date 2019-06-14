#!/usr/bin/env python

# Copyright (c) 2019, IRIS-HEP
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
# 
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
# 
# * Neither the name of the copyright holder nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys

import unittest

import numpy
import pytest

import awkward
awkward_cpp = pytest.importorskip("awkward.cpp")

class Test(unittest.TestCase):
    def runTest(self):
        pass

    def test_cpp_offsets2parents_pos(self):
        offsets = numpy.array([0, 2, 4, 4, 7], dtype=numpy.int64)
        parents = awkward_cpp.JaggedArray.offsets2parents(offsets)
        assert parents.tolist() == [0, 0, 1, 1, 3, 3, 3]

    def test_cpp_offsets2parents_neg(self):
        offsets = numpy.array([], dtype=numpy.int64)
        thrown = False
        try:
            parents = awkward_cpp.JaggedArray.offsets2parents(offsets)
        except ValueError:
            thrown = True
        assert thrown

    def test_cpp_counts2offsets_pos(self):
        counts = numpy.array([4, 0, 3, 4, 1], dtype=numpy.int64)
        offsets = awkward_cpp.JaggedArray.counts2offsets(counts)
        assert offsets.tolist() == [0, 4, 4, 7, 11, 12]

    def test_cpp_startsstops2parents_pos(self):
        starts = numpy.array([0, 4, 5, 9], dtype=numpy.int64)
        stops = numpy.array([1, 6, 7, 10], dtype=numpy.int64)
        parents = awkward_cpp.JaggedArray.startsstops2parents(starts, stops)
        assert parents.tolist() == [0, -1, -1, -1, 1, 2, 2, -1, -1, 3]

    def test_cpp_parents2startsstops_pos(self):
        parents = numpy.array([-1, 0, 0, -1, 2, 2, 2, 3], dtype=numpy.int64)
        startsstops = awkward_cpp.JaggedArray.parents2startsstops(parents)
        starts = startsstops[0]
        stops = startsstops[1]
        assert starts.tolist() == [1, 0, 4, 7] and stops.tolist() == [3, 0, 7, 8]

    def test_cpp_uniques2offsetsparents_pos(self):
        uniques = numpy.array([0, 3, 4, 6, 8, 8, 9], dtype=numpy.int64)
        offsetsparents = awkward_cpp.JaggedArray.uniques2offsetsparents(uniques)
        offsets = offsetsparents[0]
        parents = offsetsparents[1]
        assert offsets.tolist() == [0, 1, 2, 3, 4, 6, 7] and parents.tolist() == [0, 1, 2, 3, 4, 4, 5]

