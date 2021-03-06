#
# Licensed to the Apache Software Foundation (ASF) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import

import inspect

from apache_beam import pvalue
from apache_beam.dataframe import expressions
from apache_beam.dataframe import frame_base
from apache_beam.dataframe import transforms


# TODO: Or should this be called as_dataframe?
def to_dataframe(
    pcoll,  # type: pvalue.PCollection
    proxy,  # type: pandas.core.generic.NDFrame
):
  # type: (...) -> frame_base.DeferredFrame

  """Convers a PCollection to a deferred dataframe-like object, which can
  manipulated with pandas methods like `filter` and `groupby`.

  For example, one might write::

    pcoll = ...
    df = to_dataframe(pcoll, proxy=...)
    result = df.groupby('col').sum()
    pcoll_result = to_pcollection(result)

  A proxy object must be given if the schema for the PCollection is not known.
  """
  return frame_base.DeferredFrame.wrap(
      expressions.PlaceholderExpression(proxy, pcoll))


# TODO: Or should this be called from_dataframe?
def to_pcollection(
    *dataframes,  # type: Tuple[frame_base.DeferredFrame]
    **kwargs):
  # type: (...) -> Union[pvalue.PCollection, Tuple[pvalue.PCollection]]

  """Converts one or more deferred dataframe-like objects back to a PCollection.

  This method creates and applies the actual Beam operations that compute
  the given deferred dataframes, returning a PCollection of their results.

  If more than one (related) result is desired, it can be more efficient to
  pass them all at the same time to this method.
  """
  label = kwargs.pop('label', None)
  always_return_tuple = kwargs.pop('always_return_tuple', False)
  assert not kwargs  # TODO(Py3): Use PEP 3102
  if label is None:
    # Attempt to come up with a reasonable, stable label by retrieving the name
    # of these variables in the calling context.
    previous_frame = inspect.currentframe().f_back

    def name(obj):
      for key, value in previous_frame.f_locals.items():
        if obj is value:
          return key
      for key, value in previous_frame.f_globals.items():
        if obj is value:
          return key
      return '...'

    label = 'ToDataframe(%s)' % ', '.join(name(e) for e in dataframes)

  def extract_input(placeholder):
    if not isinstance(placeholder._reference, pvalue.PCollection):
      raise TypeError(
          'Expression roots must have been created with to_dataframe.')
    return placeholder._reference

  placeholders = frozenset.union(
      frozenset(), *[df._expr.placeholders() for df in dataframes])
  results = {p: extract_input(p)
             for p in placeholders
             } | label >> transforms._DataframeExpressionsTransform(
                 dict((ix, df._expr) for ix, df in enumerate(dataframes)))
  if len(results) == 1 and not always_return_tuple:
    return results[0]
  else:
    return tuple(value for key, value in sorted(results.items()))
