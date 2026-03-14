def generate_fixtures(teams):
    fixtures=[]
    for i in range(len(teams)):
        for j in range(i+1,len(teams)):
            fixtures.append((teams[i],teams[j]))
    return fixtures
