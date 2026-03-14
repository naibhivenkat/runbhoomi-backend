def detect(ball):
    if ball.runs==6:
        return "six"
    if ball.runs==4:
        return "four"
    if ball.is_wicket:
        return "wicket"
