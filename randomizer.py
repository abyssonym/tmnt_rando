from randomtools.tablereader import (
    TableObject, get_global_label, tblpath, addresses, get_random_degree,
    mutate_normal, shuffle_normal)
from randomtools.utils import (
    classproperty, get_snes_palette_transformer, cached_property,
    read_multi, write_multi, utilrandom as random)
from randomtools.interface import (
    get_outfile, get_seed, get_flags, get_activated_codes,
    run_interface, rewrite_snes_meta, clean_and_write, finish_interface)
from randomtools.itemrouter import ItemRouter
from itertools import groupby
from collections import defaultdict
from os import path
from time import time
from collections import Counter


VERSION = 1
ALL_OBJECTS = None
DEBUG_MODE = False


class ItemObject(TableObject):
    flag = 'i'
    flag_description = "item pickups"
    randomselect_attributes = ["item_type"]

    @property
    def intershuffle_valid(self):
        '''
        01 - whole pizza
        02 - half pizza
        03 - quarter pizza
        05 - shuriken
        06 - 3x shuriken
        07 - boomerang
        08 - ninja scroll
        0b - invincibility
        0c - missile
        0d - ropes
        '''
        if 'e' in get_flags():
            return 0x1 <= self.item_type <= 0xf
        else:
            # omit missiles and ropes
            return 0x1 <= self.item_type <= 0xb

    @classmethod
    def full_cleanup(cls):
        if 'e' in get_flags():
            rope_candidates = [i for i in ItemObject.every
                               if 0x12d7a <= i.pointer <= 0x12da6]
            if not any([i.item_type == 0xd for i in rope_candidates]):
                chosen = random.choice(rope_candidates)
                chosen.item_type = 0xd
            else:
                chosen = random.choice([i for i in rope_candidates
                                        if i.item_type == 0xd])
            rope_candidates.remove(chosen)
            if not any([i.item_type == 0xc for i in rope_candidates]):
                chosen = random.choice(rope_candidates)
                chosen.item_type = 0xc
        super(ItemObject, cls).full_cleanup()


class EnemyObject(TableObject):
    flag = 'm'
    flag_description = "enemies"
    randomselect_attributes = ["enemy_type"]


class EntranceObject(TableObject):
    flag = 'e'
    flag_description = "entrances/exits - unsafe"
    relink_attributes = [
         "underworld",
         "area_index",
         "dest_x", "dest_y",
         "pan_x_low", "pan_y_low",
         "pan_x_high", "pan_y_high",
         ]

    @property
    def pan_x(self):
        return (self.old_data['pan_x_high'] << 8) | self.old_data['pan_x_low']

    @property
    def pan_y(self):
        return (self.old_data['pan_y_high'] << 8) | self.old_data['pan_y_low']

    @property
    def full_dest_x(self):
        return self.pan_x + self.old_data['dest_x']

    @property
    def full_dest_y(self):
        return self.pan_y + self.old_data['dest_y']

    @property
    def num_zones_width(self):
        if self.is_overworld:
            return {
                0: 2,
                1: 2,
                2: 5,
                3: 4,
                4: 3,
                }[self.hierarchy_index[1]]
        return 999

    @property
    def full_loc_x(self):
        zone_x = self.zone % self.num_zones_width
        return (zone_x << 8) | self.tile_x

    @property
    def full_loc_y(self):
        zone_y = self.zone / self.num_zones_width
        return (zone_y << 8) | self.tile_y

    @property
    def intershuffle_valid(self):
        return False

    @property
    def hierarchy_index(self):
        if hasattr(self, "_hierarchy_index"):
            return self._hierarchy_index

        f = open(path.join(tblpath, "entrance_hierarchy.txt"))
        areas, zones = {}, []
        pointers = {}
        for line in f:
            if not line.strip() or line[0] == '#':
                continue

            pointer, area, zone = [int(w, 0x10) for w in line.strip().split()]
            if zone not in zones:
                zones.append(zone)
                areas[zone] = []
            if area not in areas[zone]:
                areas[zone].append(area)
            pair = (areas[zone].index(area), zones.index(zone))
            if pointer in pointers and pointers[pointer] != pair:
                import pdb; pdb.set_trace()
                pointers[pointer] = (-1, -1)
                continue
            pointers[pointer] = (zones.index(zone), areas[zone].index(area))

        for e in EntranceObject.every:
            e._hierarchy_index = pointers[e.pointer]

        return self.hierarchy_index

    @classproperty
    def overworld_clusters(cls):
        if hasattr(EntranceObject, "_overworld_clusters"):
            return EntranceObject._overworld_clusters

        EntranceObject.overworld_clusters = []
        for line in open(path.join(tblpath, "entrance_clusters.txt")):
            if not line.strip():
                continue
            indexes = [int(i, 0x10) for i in line.strip().split(',')]
            EntranceObject.overworld_clusters.append(tuple(indexes))

        return EntranceObject.overworld_clusters

    @property
    def is_overworld(self):
        return self.hierarchy_index[0] == 6

    @cached_property
    def reverse_entrance(self):
        if self.is_overworld:
            candidates = [
                e for e in self.every
                if e.hierarchy_index[0] == self.hierarchy_index[1]
                and e.hierarchy_index[1] == self.old_data['area_index']
                and e.old_data['area_index'] == self.hierarchy_index[1]]
        elif self.hierarchy_index[0] != self.area_index:
            return None
        else:
            candidates = [
                e for e in self.every if e.hierarchy_index[0] == 6
                and e.hierarchy_index[1] == self.hierarchy_index[0]
                and e.old_data['area_index'] == self.hierarchy_index[1]]

        if not candidates:
            import pdb; pdb.set_trace()
            return None

        if len(candidates) == 1:
            return candidates[0]

        def distance(e1, e2):
            ow = [e for e in (e1, e2) if e.is_overworld][0]
            uw = [e for e in (e1, e2) if not e.is_overworld][0]
            d = (((uw.full_dest_x - ow.full_loc_x)**2) +
                 ((uw.full_dest_y - ow.full_loc_y)**2)) ** 0.5
            return d

        chosen = min(candidates, key=lambda c: distance(self, c))
        d = distance(self, chosen)
        if d > 32:
            import pdb; pdb.set_trace()
            return None

        return chosen

    def link_other(self, other):
        r = other.reverse_entrance
        for attr in EntranceObject.relink_attributes:
            setattr(self, attr, r.old_data[attr])

    @classmethod
    def intershuffle(cls, candidates=None, random_degree=None):
        if random_degree is None:
            random_degree = cls.random_degree

        cls.class_reseed("inter")
        [e.reverse_entrance for e in EntranceObject.every]
        for i in xrange(0, 5):
            ents_ungrouped = [e for e in EntranceObject.every
                              if e.hierarchy_index[0] == i
                              and e.area_index == i]
            ow_ents_ungrouped = [e for e in EntranceObject.every
                                 if e.hierarchy_index == (6, i)]
            ow_entrances = []
            for indexes in EntranceObject.overworld_clusters:
                my_ow_entrances = [owe for owe in ow_ents_ungrouped
                                   if owe.index in indexes]
                assert len(my_ow_entrances) in (0, len(indexes))
                if my_ow_entrances:
                    ow_entrances.append(my_ow_entrances)

            try:
                assert len(ents_ungrouped) == len(ow_ents_ungrouped)
            except:
                import pdb; pdb.set_trace()

            entrances = groupby(ents_ungrouped,
                                key=lambda e: e.hierarchy_index[1])
            entrances = [sorted(v) for (k, v) in entrances]
            to_assign = set(random.choice(entrances + ow_entrances))
            assignments = {}
            entrances[0][0].reverse_entrance
            while True:
                chosen = random.choice(sorted(to_assign))
                if chosen.is_overworld:
                    candidates = list(ents_ungrouped)
                else:
                    candidates = list(ow_ents_ungrouped)

                valid_ents = set([])
                for egroup in entrances + ow_entrances:
                    unassigned = set([
                        e for e in egroup
                        if e not in assignments and e not in to_assign])
                    if (len(unassigned) > 1 or len(to_assign) > 1
                            or len(assignments) >= len(ents_ungrouped
                                                       + ow_ents_ungrouped)-2):
                        valid_ents |= unassigned

                candidates = [c for c in candidates if c in valid_ents]
                if not candidates:
                    assert len(to_assign) >= 2
                    candidates = [c for c in sorted(to_assign)
                                  if c.is_overworld != chosen.is_overworld]
                    assert chosen not in candidates
                else:
                    assert not to_assign & set(candidates)

                other = random.choice(sorted(candidates))
                assert chosen not in assignments
                assert other not in assignments
                assert chosen in to_assign
                assert other in candidates
                assignments[chosen] = other
                assignments[other] = chosen
                for egroup in entrances + ow_entrances:
                    if chosen in egroup or other in egroup:
                        to_assign |= set(egroup)
                to_assign -= set(assignments.keys())
                if not to_assign:
                    break

            assert (len(assignments) == len(set(assignments.values()))
                == len(ents_ungrouped + ow_ents_ungrouped))
            for a, b in assignments.items():
                a.link_other(b)


if __name__ == "__main__":
    try:
        print ("You are using the Teenage Mutant Ninja Turtles "
               "randomizer version %s." % VERSION)
        print

        ALL_OBJECTS = [g for g in globals().values()
                       if isinstance(g, type) and issubclass(g, TableObject)
                       and g not in [TableObject]]

        run_interface(ALL_OBJECTS, snes=False)

        clean_and_write(ALL_OBJECTS)
        finish_interface()

    except Exception, e:
        print "ERROR: %s" % e
        raw_input("Press Enter to close this program.")
