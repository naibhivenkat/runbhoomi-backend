def generate_scorecard(balls):
    total=0
    wickets=0
    for b in balls:
        total+=b.runs
        if b.is_wicket:
            wickets+=1
    return {"runs":total,"wickets":wickets}
