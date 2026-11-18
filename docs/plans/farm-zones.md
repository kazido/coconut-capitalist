Status: IN PROGRESS on `design` (not merged). Delete this file when it merges; trim the Farming line in docs/STATUS.md.

# Farm zones

One set of plots, a ZONE picker (dropdown) on the Farm page. Zone N = the Nth `[farming]` location (14), opened by `areas.open_locations`.

- Seeds: zone N can plant `field_seeds[0..N-1]` (its own seed and cheaper). Seeds not in `field_seeds` plant anywhere. Shop gating unchanged (reached fields).
- Byproducts: `farming.toml zone_materials[N-1]` = the materials Tend (and harvest extras) roll in that zone: one NEW signature material per zone
  (`material_zone_<n>_...`, placeholder emoji, TODO(balance)) plus a tier subset of the 5 old farming materials. One roll of any zone's table is worth ~618 bits.
- Stars: depth = the PLANTED zone (not the seed). Crop value already climbs with the seed ladder, so zone N's best seed is worth more.
- A plot remembers the zone it was planted in (`Plot.zone`; 0 = old plots, derived from the seed). Switching zones never wastes a growing crop.
- Tend/harvest pay from each plot's own zone table.
- `byproduct_max_cycles` stays small (3) so one Tend is never huge.
