def wagonwheel(balls):
    zones={}
    for b in balls:
        zones[b.shot_zone]=zones.get(b.shot_zone,0)+b.runs
    return zones
