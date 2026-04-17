from app.database.models import TournamentGroup, GroupTeam

def create_groups(db, tournament_id, teams, group_count):
    n = len(teams)

    if n < 2:
        return None

    groups = []

    # create groups
    for i in range(group_count):
        g = TournamentGroup(
            tournament_id=tournament_id,
            name=f"Group {chr(65+i)}"
        )
        db.add(g)
        db.commit()
        db.refresh(g)
        groups.append(g)

    # 🔥 sequential distribution (CORRECT)
    chunk_size = n // group_count
    remainder = n % group_count

    start = 0

    for i, group in enumerate(groups):
        extra = 1 if i < remainder else 0
        end = start + chunk_size + extra

        group_slice = teams[start:end]

        for t in group_slice:
            db.add(GroupTeam(
                group_id=group.id,
                team_id=t.team_id
            ))

        start = end

    db.commit()
    return groups
def round_robin(team_ids):
    fixtures = []

    for i in range(len(team_ids)):
        for j in range(i + 1, len(team_ids)):
            fixtures.append((team_ids[i], team_ids[j]))

    return fixtures


import math

def generate_knockout(team_ids):
    n = len(team_ids)
    power = 2 ** math.ceil(math.log2(n))

    byes = power - n
    teams = team_ids.copy()

    for _ in range(byes):
        teams.append(None)

    fixtures = []

    for i in range(0, len(teams), 2):
        fixtures.append((teams[i], teams[i+1]))

    return fixtures

def calculate_nrr(p):
    if p.overs_faced == 0 or p.overs_bowled == 0:
        return 0

    return (p.runs_scored / p.overs_faced) - (
        p.runs_conceded / p.overs_bowled
    )


def paired_rounds(team_ids):
    matches = []

    # Round 1: (1 vs 2), (3 vs 4)
    for i in range(0, len(team_ids), 2):
        if i + 1 < len(team_ids):
            matches.append((team_ids[i], team_ids[i+1]))

    # Round 2: cross matches
    if len(team_ids) >= 4:
        matches.append((team_ids[0], team_ids[2]))
        matches.append((team_ids[1], team_ids[3]))

    return matches


def get_match_duration(overs):
    if overs <= 6:
        return 45
    elif overs <= 8:
        return 60
    elif overs <= 10:
        return 75
    elif overs <= 15:
        return 110
    elif overs <= 20:
        return 160
    else:
        return overs * 8