#!/usr/bin/env python

# Copyright (c) 2018, DIANA-HEP
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

import awkward.array.base
import awkward.persist
import awkward.type
import awkward.util

class ChunkedArray(awkward.array.base.AwkwardArray):
    def __init__(self, chunks, counts=[]):
        self.chunks = chunks
        self.counts = counts
        
    def copy(self, chunks=None, counts=None):
        out = self.__class__.__new__(self.__class__)
        out._chunks = list(self._chunks)
        out._counts = list(self._counts)
        out._types = list(self._types)
        out._offsets = self._offsets
        if chunks is not None:
            out.chunks = chunks
            out._counts = []
        if counts is not None:
            out.counts = counts
        return out

    def deepcopy(self, chunks=None, counts=None):
        out = self.copy(chunks=chunks, counts=counts)
        out._chunks = [awkward.util.deepcopy(out._chunks) for x in out._chunks]
        return out

    def _mine(self, overrides):
        return {}

    def empty_like(self, **overrides):
        self.knowcounts()
        self._valid()
        mine = self._mine(overrides)
        return self.copy([awkward.util.numpy.empty_like(x) if isinstance(x, awkward.util.numpy.ndarray) else x.empty_like(**overrides) for x in self._chunks], counts=list(self._counts), **mine)

    def zeros_like(self, **overrides):
        self.knowcounts()
        self._valid()
        mine = self._mine(overrides)
        return self.copy([awkward.util.numpy.zeros_like(x) if isinstance(x, awkward.util.numpy.ndarray) else x.zeros_like(**overrides) for x in self._chunks], counts=list(self._counts), **mine)

    def ones_like(self, **overrides):
        self.knowcounts()
        self._valid()
        mine = self._mine(overrides)
        return self.copy([awkward.util.numpy.ones_like(x) if isinstance(x, awkward.util.numpy.ndarray) else x.ones_like(**overrides) for x in self._chunks], counts=list(self._counts), **mine)

    def __awkward_persist__(self, ident, fill, **kwargs):
        self.knowcounts()
        self._valid()
        n = self.__class__.__name__
        return {"id": ident,
                "call": ["awkward", n],
                "args": [{"list": [fill(x, n + ".chunk", **kwargs) for c, x in zip(self._counts, self._chunks) if c > 0]},
                         fill(awkward.util.numpy.array([c for c in self._counts if c > 0]), n + ".counts", **kwargs)]}

    @property
    def chunks(self):
        return self._chunks

    @chunks.setter
    def chunks(self, value):
        try:
            iter(value)
        except TypeError:
            raise TypeError("chunks must be iterable")
        self._chunks = [awkward.util.toarray(x, awkward.util.DEFAULTTYPE) for x in value]
        self._types = [None] * len(self._chunks)

    @property
    def counts(self):
        return self._counts

    @counts.setter
    def counts(self, value):
        try:
            if not all(isinstance(x, awkward.util.integer) and x >= 0 for x in value):
                raise ValueError("counts must contain only non-negative integers")
        except TypeError:
            raise TypeError("counts must be iterable")
        self._counts = list(value)
        self._offsets = None

    @property
    def offsets(self):
        import awkward.array.jagged
        if self._offsets is None or len(self._offsets) != len(self._counts) + 1:
            self._offsets = awkward.array.jagged.counts2offsets(self._counts)
        return self._offsets

    @property
    def countsknown(self):
        return len(self._counts) == len(self._chunks)

    @property
    def typesknown(self):
        return all(x is not None for x in self._types)

    def knowcounts(self, until=None):
        if until is None:
            until = len(self._chunks)
        if not 0 <= until <= len(self._chunks):
            raise ValueError("cannot knowcounts until chunkid {0} with {1} chunks".format(until, len(self._chunks)))
        for i in range(len(self._counts), until):
            self._counts.append(len(self._chunks[i]))

    def knowtype(self, at):
        if not 0 <= at < len(self._chunks):
            raise ValueError("cannot knowtype at chunkid {0} with {1} chunks".format(at, len(self._chunks)))
        chunk = self._chunks[at]
        if len(chunk) == 0:
            self._types[at] = ()
        else:
            self._types[at] = awkward.type.fromarray(chunk).to
        return self._types[at]

    def global2chunkid(self, index, return_normalized=False):
        self._valid()

        if isinstance(index, awkward.util.integer):
            original_index = index
            if index < 0:
                index += len(self)
            if index < 0:
                raise IndexError("index {0} out of bounds for length {1}".format(original_index, len(self)))

            cumulative = self.offsets[-1]
            while index >= cumulative:
                if self.countsknown:
                    raise IndexError("index {0} out of bounds for length {1}".format(original_index, len(self)))
                count = len(self._chunks[len(self._counts)])
                cumulative += count
                self._counts.append(count)

            out = awkward.util.numpy.searchsorted(self.offsets, index, "right") - 1

        else:
            index = awkward.util.numpy.array(index, copy=False)
            if len(index.shape) == 1 and issubclass(index.dtype.type, awkward.util.numpy.integer):
                if len(index) == 0:
                    out = awkward.util.numpy.empty(0, dtype=awkward.util.INDEXTYPE)

                else:
                    mask = (index < 0)
                    if mask.any():
                        index = awkward.util.deepcopy(index)
                        index[mask] += len(self)
                    if (index < 0).any():
                        raise IndexError("index out of bounds for length {0}".format(len(self)))

                    self.global2chunkid(index.max())    # make sure all the counts we need are known
                    out = awkward.util.numpy.searchsorted(self.offsets, index, "right") - 1

            else:
                raise TypeError("global2chunkid requires an integer or an array of integers")

        if return_normalized:
            return out, index
        else:
            return out

    def global2local(self, index):
        chunkid, index = self.global2chunkid(index, return_normalized=True)

        if isinstance(index, awkward.util.integer):
            return self._chunks[chunkid], index - self.offsets[chunkid]
        else:
            return awkward.util.numpy.array(self._chunks, dtype=awkward.util.numpy.object)[chunkid], index - self.offsets[chunkid]

    def local2global(self, index, chunkid):
        if isinstance(chunkid, awkward.util.integer):
            self.knowcounts(chunkid + 1)
            self._valid()
            original_index = index
            if index < 0:
                index += self._counts[chunkid]
            if not 0 <= index < self._counts[chunkid]:
                raise IndexError("local index {0} is out of bounds in chunk {1}, which has length {2}".format(original_index, chunkid, self._counts[chunkid]))
            return self.offsets[chunkid] + index

        else:
            index = awkward.util.numpy.array(index, copy=False)
            chunkid = awkward.util.numpy.array(chunkid, copy=False)
            if len(index.shape) == 1 and issubclass(index.dtype.type, awkward.util.numpy.integer) and len(chunkid.shape) == 1 and issubclass(chunkid.dtype.type, awkward.util.numpy.integer):
                if len(index) != len(chunkid):
                    raise ValueError("len(index) is {0} and len(chunkid) is {1}, but they should be equal".format(len(index), len(chunkid)))

                self.knowcounts(chunkid.max() + 1)
                self._valid()
                counts = numpy.array(self._counts, dtype=awkward.util.INDEXTYPE)
                mask = (index < 0)
                index[mask] += counts[mask]
                if not ((0 <= index) & (index < counts)).all():
                    raise IndexError("some local indexes are out of bounds")
                return counts[chunkid] + index

            else:
                raise TypeError("local2global requires index and chunkid to be integers or arrays of integers")

    def _gettype(self, seen):
        for tpe in self._types:
            if tpe is not None and tpe is not ():
                break
        else:
            for i in range(len(self._types)):
                tpe = self.knowtype(i)
                if tpe is not None and tpe is not ():
                    break
            else:
                tpe = awkward.util.DEFAULTTYPE

        for i in range(len(self._types)):
            if self._types[i] is None or self._types[i] is () or self._types[i] is tpe:
                pass
            elif self._types[i] == tpe:       # valid if all chunks have the same high-level type
                self._types[i] = tpe          # once checked, make them identically equal for faster checking next time
            else:
                raise TypeError("chunks do not have matching types:\n\n{0}\n\nversus\n\n{1}".format(awkward.type._str(tpe, indent="    "), awkward.type._str(self._types[i], indent="    ")))

        return tpe

    def _getshape(self):
        return (len(self),)

    def __len__(self):
        self.knowcounts()
        return self.offsets[-1]

    def _slices(self):
        # perhaps this should be a (public) @staticmethod that finds the largest possible slices to serve no more than one chunk each from a set of ChunkedArrays
        self.knowcounts()
        offsets = self.offsets
        return [slice(start, stop) for start, stop in zip(offsets[:-1], offsets[1:])]

    def _valid(self):
        if len(self._counts) > len(self._chunks):
            raise ValueError("ChunkArray has more counts than chunks")
        for i, count in enumerate(self._counts):
            if count != len(self._chunks[i]):
                raise ValueError("count[{0}] does not agree with len(chunk[{0}])".format(i))
        self._gettype({})

    def __str__(self):
        if self.countsknown:
            return super(ChunkedArray, self).__str__()
        else:
            strs = [awkward.util.array_str(x) for x in self[:7]]
            if len(strs) < 7:
                return super(ChunkedArray, self).__str__()
            else:
                return "[{0} ...]".format(" ".join(strs))
            
    def __iter__(self):
        for i, chunk in enumerate(self._chunks):
            if i >= len(self._counts):
                self._counts.append(len(chunk))
            for x in chunk[:self._counts[i]]:
                yield x

    def __array__(self, *args, **kwargs):
        if isinstance(self.type.to, awkward.util.numpy.dtype):
            if len(self) == 0:
                return awkward.util.numpy.empty(0, dtype=awkward.util.DEFAULTTYPE)
            else:
                out = awkward.util.numpy.empty(self.shape, dtype=self.dtype)
                for chunk, slc in zip(self._chunks, self._slices()):
                    out[slc] = chunk
                return out
        else:
            return super(ChunkedArray, self).__array__(*args, **kwargs)

    def __getitem__(self, where):
        import awkward.array.indexed
        self._valid()

        if awkward.util.isstringslice(where):
            if isinstance(where, awkward.util.string):
                if not self.type.hascolumn(where):
                    raise ValueError("no column named {0}".format(repr(where)))
            else:
                for x in where:
                    if not self.type.hascolumn(x):
                        raise ValueError("no column named {0}".format(repr(x)))
            chunks = []
            counts = []
            for chunk in self._chunks:
                chunks.append(chunk[where])
                counts.append(len(chunks[-1]))
            return ChunkedArray(chunks, counts=counts)

        if isinstance(where, tuple) and len(where) == 0:
            return self
        if not isinstance(where, tuple):
            where = (where,)
        head, tail = where[0], where[1:]

        if isinstance(head, awkward.util.integer):
            chunk, localhead = self.global2local(head)
            return chunk[(localhead,) + tail]

        elif isinstance(head, slice):
            if head.step == 0:
                raise ValueError("slice step cannot be zero")
            elif (head.start is None or head.start >= 0) and (head.stop is not None and head.stop >= 0) and (head.step is None or head.step > 0):
                # case A
                start, stop, step = head.start, head.stop, head.step
                if start is None:
                    start = 0
                if step is None:
                    step = 1
            elif (head.start is not None and head.start >= 0) and (head.stop is None or head.stop >= 0) and (head.step is not None and head.step < 0):
                # case B
                start, stop, step = head.start, head.stop, head.step
                if stop is None:
                    stop = -1
            else:
                # case C (requires potentially expensive len(self))
                start, stop, step = head.indices(len(self))

            # if step > 0, stop can be len(self)
            # if step < 0, stop can be -1 (not a Python "negative index", but an indicator to go all the way to 0)

            if start == -1:
                # case C start below 0
                start_chunkid = -1
            else:
                try:
                    start_chunkid = self.global2chunkid(start)
                except IndexError:
                    if start > 0:
                        # case A or B start was set beyond len(self), clamp it
                        start, start_chunkid = len(self), len(self._chunks)
                    if step < 0:
                        start -= 1
                        start_chunkid -= 1

            if stop == -1:
                # case B or C stop not set with step < 0; go all the way to 0
                stop_chunkid = -1
            else:
                try:
                    stop_chunkid = self.global2chunkid(stop)
                except IndexError:
                    # stop is at or beyond len(self), clamp it
                    stop = len(self)
                if step > 0:
                    # we want the chunkid at or to the right of stop (no -1)
                    stop_chunkid = min(awkward.util.numpy.searchsorted(self.offsets, stop, "right"), len(self._chunks))
                else:
                    # we want the chunkid to the left of stop
                    stop_chunkid = max(awkward.util.numpy.searchsorted(self.offsets, stop, "right") - 2, -1)

            offsets = self.offsets
            chunks = []
            skip = 0
            for chunkid in range(start_chunkid, stop_chunkid, 1 if step > 0 else -1):
                # set the local_start
                if chunkid == start_chunkid:
                    local_start = start - offsets[chunkid]
                else:
                    if step > 0:
                        local_start = skip
                    else:
                        local_start = self._counts[chunkid] - 1 - skip

                if local_start < 0:
                    # skip is bigger than this entire chunk
                    skip -= self._counts[chunkid]
                    continue

                # set the local_stop and new skip
                if chunkid == stop_chunkid - (1 if step > 0 else -1):
                    if stop == -1:
                        local_stop = None
                    else:
                        local_stop = stop - offsets[chunkid]
                else:
                    local_stop = None
                    if step > 0:
                        skip = (local_start - self._counts[chunkid]) % step
                    else:
                        skip = (-1 - local_start) % -step

                # add a sliced chunk
                chunk = self._chunks[chunkid][(slice(local_start, local_stop, step),)]
                if len(chunk) > 0:
                    chunk = chunk[(slice(None),) + tail]
                    if len(chunk) > 0:
                        chunks.append(chunk)

            if len(chunks) == 0 and len(self._chunks) > 0:
                chunks.append(self._chunks[0][(slice(0, 0),) + tail])   # so that sliced.type == self.type

            return self.__class__(chunks)

        else:
            head = awkward.util.numpy.array(head, copy=False)
            if len(head.shape) == 1 and issubclass(head.dtype.type, awkward.util.numpy.integer):
                if len(head) == 0 and len(self._chunks) == 0:
                    return self.__class__([])[tail]
                elif len(head) == 0:
                    return self.__class__([self._chunks[0][(slice(0, 0),) + tail]])

                chunkid, head = self.global2chunkid(head, return_normalized=True)

                diff = (chunkid[1:] - chunkid[:-1])
                if (diff >= 0).all():
                    diff2 = awkward.util.numpy.empty(len(chunkid), dtype=awkward.util.INDEXTYPE)
                    diff2[0] = 1
                    diff2[1:] = diff
                    mask = (diff2 > 0)
                    offsets = list(awkward.util.numpy.nonzero(mask)[0]) + [len(chunkid)]
                    chunks = []
                    for i, cid in enumerate(chunkid[mask]):
                        localindex = head[offsets[i]:offsets[i + 1]] - self.offsets[cid]
                        chunks.append(self._chunks[cid][localindex])
                    return self.__class__(chunks)

                elif awkward.util.isnumpy(self.type):
                    out = awkward.util.numpy.empty((len(head),) + self.type.shape[1:], dtype=self.type.dtype)
                    self.knowcounts(chunkid.max())
                    offsets = self.offsets

                    for cid in awkward.util.numpy.unique(chunkid):
                        mask = (chunkid == cid)
                        out[mask] = self._chunks[cid][head[mask] - offsets[cid]]

                    if tail == ():
                        return out
                    else:
                        return out[(slice(None),) + tail]

                elif tail == ():
                    return awkward.array.indexed.IndexedArray(head, self)

                else:
                    raise NotImplementedError

            elif len(head.shape) == 1 and issubclass(head.dtype.type, (awkward.util.numpy.bool, awkward.util.numpy.bool_)):
                if len(self) != len(head):
                    raise IndexError("boolean index did not match indexed array along dimension 0; dimension is {0} but corresponding boolean dimension is {1}".format(len(self), len(head)))

                chunks = []
                for chunk, slc in zip(self._chunks, self._slices()):
                    x = chunk[head[slc]]
                    if len(x) > 0:
                        x = x[(slice(None),) + tail]
                        if len(x) > 0:
                            chunks.append(x)

                return self.__class__(chunks)

            else:
                raise TypeError("cannot interpret shape {0}, dtype {1} as a fancy index or mask".format(head.shape, head.dtype))

    def _aligned(self, what):
        self.knowcounts()
        what.knowcounts()
        return self._counts == what._counts

    def __setitem__(self, where, what):
        if isinstance(what, ChunkedArray) and self._aligned(what):
            for mine, theirs in zip(self._chunks, what._chunks):
                mine[where] = theirs
        else:
            raise ValueError("only ChunkedArrays with the same chunk sizes can be assigned to columns of a ChunkedArray")

    def __delitem__(self, where):
        if isinstance(where, awkward.util.string):
            for chunk in self._chunks:
                del chunk[where]
        elif awkward.util.isstringslice(where):
            for chunk in self._chunks:
                for x in where:
                    del chunk[x]
        else:
            raise TypeError("invalid index for removing column from Table: {0}".format(where))

    def __array_ufunc__(self, ufunc, method, *inputs, **kwargs):
        import awkward.array.objects

        if method != "__call__":
            return NotImplemented

        first = None
        rest = []
        for x in inputs:
            if isinstance(x, ChunkedArray):
                x._valid()
                if first is None:
                    first = x
                else:
                    rest.append(x)

        assert first is not None
        if not all(first._aligned(x) for x in rest):
            # FIXME: we may need to handle a more general case if ChunkedArrays are inside other awkward types
            # perhaps split at the largest possible slices such that all of them are one chunk each, and then unpack the single chunk after slicing
            raise ValueError("ChunkedArrays can only be combined if they have the same chunk sizes")

        batches = []
        for i, slc in enumerate(first._slices()):
            batch = []
            for x in inputs:
                if isinstance(x, ChunkedArray):
                    batch.append(x._chunks[i])
                elif isinstance(x, (awkward.util.numpy.ndarray, awkward.array.base.AwkwardArray)):
                    batch.append(x[slc])
                else:
                    batch.append(x)
            batches.append(batch)
        
        out = None
        chunks = {}
        types = {}
        for batch in batches:
            result = getattr(ufunc, method)(*batch, **kwargs)

            if isinstance(result, tuple):
                if out is None:
                    out = list(result)
                for i, x in enumerate(result):
                    if isinstance(x, (awkward.util.numpy.ndarray, awkward.array.base.AwkwardArray)):
                        if i not in chunks:
                            chunks[i] = []
                        chunks[i].append(x)
                        types[i] = type(x)

            elif method == "at":
                pass

            else:
                if isinstance(result, (awkward.util.numpy.ndarray, awkward.array.base.AwkwardArray)):
                    if None not in chunks:
                        chunks[None] = []
                    chunks[None].append(result)
                    types[None] = type(result)

        if out is None:
            if None in chunks:
                return awkward.array.objects.Methods.maybemixin(types[None], ChunkedArray)(chunks[None])
            else:
                return None
        else:
            for i in range(len(out)):
                if i in chunks:
                    out[i] = awkward.array.objects.Methods.maybemixin(types[i], ChunkedArray)(chunks[i])
            return tuple(out)

    def any(self):
        return any(x.any() for x in self._chunks)

    def all(self):
        return all(x.all() for x in self._chunks)

    @classmethod
    def concat(cls, first, *rest):
        raise NotImplementedError

    @property
    def base(self):
        raise TypeError("ChunkedArray has no base")

    @property
    def columns(self):
        if len(self._chunks) == 0 or isinstance(self.type.to, awkward.util.numpy.dtype):
            return []
        else:
            return self._chunks[0].columns

    @property
    def allcolumns(self):
        if len(self._chunks) == 0 or isinstance(self.type.to, awkward.util.numpy.dtype):
            return []
        else:
            return self._chunks[0].allcolumns

    def pandas(self):
        raise NotImplementedError

class AppendableArray(ChunkedArray):
    def __init__(self, chunkshape, dtype, chunks=[]):
        self.chunkshape = chunkshape
        self.dtype = dtype
        self.chunks = chunks

    def copy(self, chunkshape=None, dtype=None, chunks=None):
        out = self.__class__.__new__(self.__class__)
        out._chunkshape = chunkshape
        out._dtype = dtype
        out._chunks = list(self._chunks)
        out._counts = list(self._counts)
        out._types = list(self._types)
        if chunks is not None:
            out.chunks = chunks
        return out

    def _mine(self, overrides):
        mine = {}
        mine["chunkshape"] = overrides.pop("chunkshape", self._chunkshape)
        mine["dtype"] = overrides.pop("dtype", self._dtype)
        return mine

    def __awkward_persist__(self, ident, fill, **kwargs):
        self._valid()
        n = self.__class__.__name__
        return {"id": ident,
                "call": ["awkward", n],
                "args": [self._chunkshape,
                         {"call": ["awkward.persist", "json2dtype"], "args": [awkward.persist.dtype2json(self._dtype)]},
                         {"list": [fill(x, n + ".chunk", **kwargs) for c, x in zip(self._counts, self._chunks) if c > 0]}]}

    @property
    def chunkshape(self):
        return self._chunkshape

    @chunkshape.setter
    def chunkshape(self, value):
        if isinstance(value, awkward.util.integer) and value > 0:
            self._chunkshape = (value,)
        else:
            try:
                for x in value:
                    assert isinstance(x, awkward.util.integer) and value > 0
            except TypeError:
                raise TypeError("chunkshape must be an integer or a tuple of integers")
            except AssertionError:
                raise ValueError("chunkshape must be a positive integer or tuple of positive integers")
            else:
                self._chunkshape = tuple(value)

    @property
    def dtype(self):
        return self._dtype

    @dtype.setter
    def dtype(self, value):
        self._dtype = awkward.util.numpy.dtype(value)

    @property
    def chunks(self):
        return self._chunks

    @chunks.setter
    def chunks(self, value):
        try:
            iter(value)
        except TypeError:
            raise TypeError("chunks must be iterable")
        chunks = [awkward.util.toarray(x, awkward.util.DEFAULTTYPE, awkward.util.numpy.ndarray) for x in value]
        for chunk in chunks:
            if chunk.dtype != self._dtype:
                raise ValueError("cannot assign chunk with dtype ({0}) to an AppendableArray with dtype ({1})".format(chunk.dtype, self._dtype))
            if chunk.shape[1:] != self._chunkshape[1:]:
                raise ValueError("cannot assign chunk with dimensionality ({0}) to an AppendableArray with dimensionality ({1}), where dimensionality is shape[1:]".format(chunk.shape[1:], self._chunkshape[1:]))
        self._chunks = chunks
        self._counts = [len(x) for x in self._chunks]
        self._types = [None] * len(self._chunks)

    @property
    def counts(self):
        return self._counts

    @counts.setter
    def counts(self, value):
        raise AttributeError("cannot assign to counts in AppendableArray")

    def knowcounts(self, until=None):
        pass

    @property
    def offsets(self):
        import awkward.array.jagged
        return awkward.array.jagged.counts2offsets(self._counts)

    def _gettype(self, seen):
        return self._dtype

    def _getshape(self):
        return sum(self._counts)

    def _valid(self):
        pass

    def __setitem__(self, where, what):
        raise TypeError("array has no Table, cannot assign columns")

    def __delitem__(self, where):
        raise TypeError("array has no Table, cannot remove columns")

    def append(self, value):
        if len(self._chunks) == 0 or self._counts[-1] == len(self._chunks[-1]):
            self._types.append(None)
            self._counts.append(0)
            self._chunks.append(awkward.util.numpy.empty(self._chunkshape, dtype=self._dtype))

        self._chunks[-1][self._counts[-1]] = value
        self._counts[-1] += 1

    def extend(self, values):
        while len(values) > 0:
            if len(self._chunks) == 0 or self._counts[-1] == len(self._chunks[-1]):
                self._types.append(None)
                self._counts.append(0)
                self._chunks.append(awkward.util.numpy.empty(self._chunkshape, dtype=self._dtype))

            howmany = min(len(values), len(self._chunks[-1]) - self._counts[-1])
            self._chunks[-1][self._counts[-1] : self._counts[-1] + howmany] = values[:howmany]
            self._counts[-1] += howmany
            values = values[howmany:]
