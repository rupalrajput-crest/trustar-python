# python 2 backwards compatibility
from __future__ import print_function
from builtins import object, super
from future import standard_library
from six import string_types

# package imports
from .base import ModelBase
from .enum import *
from .tag import Tag


class Indicator(ModelBase):
    """
    Models an |Indicator_resource|.

    :ivar value: The indicator value; i.e. "www.evil.com"
    :ivar type: The type of indicator; i.e. "URL"
    :ivar priority_level: The priority level of the indicator
    :ivar correlation_count: The number of other indicators that are correlated with this indicator.
    :ivar whitelisted: Whether the indicator is whitelisted or not.
    :ivar weight: see |Indicator_resource| for details.
    :ivar reason: see |Indicator_resource| for details.
    :ivar first_seen: the first time this indicator was sighted
    :ivar last_seen: the last time this indicator was sighted
    :ivar sightings: the number of times this indicator has been sighted
    :ivar source: the source that the indicator was observed from
    :ivar notes: a string containing notes about the indicator
    :ivar tags: a list containing tag objects associated with the indicator
    :ivar enclave_ids: a list of enclaves that the indicator is found in

    :cvar TYPES: A list of all valid indicator types.
    """

    TYPES = IndicatorType.values()

    def __init__(self,
                 value,
                 type=None,
                 priority_level=None,
                 correlation_count=None,
                 whitelisted=None,
                 weight=None,
                 reason=None,
                 first_seen=None,
                 last_seen=None,
                 sightings=None,
                 source=None,
                 notes=None,
                 tags=None,
                 enclave_ids=None):

        self.value = value
        self.type = type
        self.priority_level = priority_level
        self.correlation_count = correlation_count
        self.whitelisted = whitelisted
        self.weight = weight
        self.reason = reason

        # ioc management fields
        self.first_seen = first_seen
        self.last_seen = last_seen
        self.sightings = sightings
        self.source = source
        self.notes = notes
        self.tags = tags
        self.enclave_ids = enclave_ids

    @classmethod
    def from_dict(cls, indicator):
        """
        Create an indicator object from a dictionary.

        :param indicator: The dictionary.
        :return: The indicator object.
        """

        tags = indicator.get('tags')
        if tags is not None:
            tags = [Tag.from_dict(tag) for tag in tags]

        return Indicator(value=indicator.get('value'),
                         type=indicator.get('indicatorType'),
                         priority_level=indicator.get('priorityLevel'),
                         correlation_count=indicator.get('correlationCount'),
                         whitelisted=indicator.get('whitelisted'),
                         weight=indicator.get('weight'),
                         reason=indicator.get('reason'),
                         first_seen=indicator.get('firstSeen'),
                         last_seen=indicator.get('lastSeen'),
                         source=indicator.get('source'),
                         notes=indicator.get('notes'),
                         tags=tags,
                         enclave_ids=indicator.get('enclaveIds'))

    def to_dict(self, remove_nones=False):
        """
        Creates a dictionary representation of the indicator.

        :param remove_nones: Whether ``None`` values should be filtered out of the dictionary.  Defaults to ``False``.
        :return: A dictionary representation of the indicator.
        """

        if remove_nones:
            return super().to_dict(remove_nones=True)

        tags = None
        if self.tags is not None:
            tags = [tag.to_dict(remove_nones=remove_nones) for tag in self.tags]

        return {
            'value': self.value,
            'indicatorType': self.type,
            'priorityLevel': self.priority_level,
            'correlationCount': self.correlation_count,
            'whitelisted': self.whitelisted,
            'weight': self.weight,
            'reason': self.reason,
            'firstSeen': self.first_seen,
            'lastSeen': self.last_seen,
            'source': self.source,
            'notes': self.notes,
            'tags': tags,
            'enclaveIds': self.enclave_ids
        }
