from randomtools.tablereader import (
    TableObject, get_global_label, tblpath, addresses, get_random_degree,
    mutate_normal, shuffle_normal)
from randomtools.utils import (
    classproperty, get_snes_palette_transformer,
    read_multi, write_multi, utilrandom as random)
from randomtools.interface import (
    get_outfile, get_seed, get_flags, get_activated_codes,
    run_interface, rewrite_snes_meta, clean_and_write, finish_interface)
from randomtools.itemrouter import ItemRouter
from collections import defaultdict
from os import path
from time import time
from collections import Counter


VERSION = 1
ALL_OBJECTS = None
DEBUG_MODE = False


class EntranceObjectMixin(object):
    intershuffle_attributes = [(
         "underworld",
         "area_index",
         "dest_x", "dest_y",
         "pan_x", "pan_y",
         )]

    @property
    def intershuffle_valid(self):
        return self.groupindex in [0, 2]


class EntranceObjectA(EntranceObjectMixin, TableObject): pass
class EntranceObjectB(EntranceObjectMixin, TableObject): pass
class EntranceObjectC(EntranceObjectMixin, TableObject): pass
class EntranceObjectD(EntranceObjectMixin, TableObject): pass
class EntranceObjectE(EntranceObjectMixin, TableObject): pass
class EntranceObjectF(EntranceObjectMixin, TableObject): pass
class OverworldEntranceObject(EntranceObjectMixin, TableObject): pass


if __name__ == "__main__":
    try:
        print ("You are using the Teenage Mutant Ninja Turtles "
               "randomizer version %s." % VERSION)
        print

        ALL_OBJECTS = [g for g in globals().values()
                       if isinstance(g, type) and issubclass(g, TableObject)
                       and g not in [TableObject]]

        run_interface(ALL_OBJECTS, snes=False)
        #for e in EntranceObject.every:
        #    print e.index, e.area_index, e.pan_x, e.pan_y
        import pdb; pdb.set_trace()

        clean_and_write(ALL_OBJECTS)
        finish_interface()

    except Exception, e:
        print "ERROR: %s" % e
        raw_input("Press Enter to close this program.")
