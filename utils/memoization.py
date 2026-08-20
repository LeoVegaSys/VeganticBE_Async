from datetime import timedelta

from memoize.wrapper import memoize
from memoize.configuration import MutableCacheConfiguration, DefaultInMemoryCacheConfiguration
from memoize.storage import LocalInMemoryCacheStorage
from memoize.key import EncodedMethodNameAndArgsKeyExtractor
from memoize.eviction import LeastRecentlyUpdatedEvictionStrategy
from memoize.entrybuilder import ProvidedLifeSpanCacheEntryBuilder


memoization_configuration = MutableCacheConfiguration.initialized_with(
    DefaultInMemoryCacheConfiguration()).set_method_timeout(
        timedelta(minutes=5)).set_eviction_strategy(
            LeastRecentlyUpdatedEvictionStrategy(
                capacity=20)).set_key_extractor(
                    EncodedMethodNameAndArgsKeyExtractor(
                        skip_first_arg_as_self=True)).set_storage(
                            LocalInMemoryCacheStorage()).set_entry_builder(
                                ProvidedLifeSpanCacheEntryBuilder(
                                    update_after=timedelta(minutes=5),
                                    expire_after=timedelta(minutes=10)))